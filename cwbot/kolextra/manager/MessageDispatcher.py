import logging
import Queue
import threading
from cwbot.util.tryRequest import tryRequest
from kol.request.SendChatRequest import SendChatRequest
import time
from time import sleep
import copy
import uuid


class MessageThread(threading.Thread):
    """ 
    A thread that throttles chat/PM transmissions. Used by the 
    MessageDispatcher.
    The MessageThread will automatically close itself when there is no
    activity for a certain time. It is also possible to request a stop by
    calling the stop() method, but it will not actually stop until it
    has finished sending the messages in its queue. Attempting to add something 
    to a MessageThread's messageQueue after the thread is closed will raise 
    a ReferenceError exception.
    """
    
    
    def __init__(self, session, timeout, targetName=uuid.uuid4()):
        self._session = session
        self._log = logging.getLogger("chat")
        self._open = True
        self._timeout = timeout
        self._stopEvent = threading.Event()
        self.__lock = threading.RLock()
        self.__messageQueue = Queue.Queue()
        self._lastTarget = None
        self.throttleSeconds = 1.75
        uid = "MessageThread-{}".format(targetName)
        super(MessageThread, self).__init__(name=uid)
        
    
    def stop(self):
        """ Call this to stop the thread's execution. """
        self._stopEvent.set()
    
    @property
    def messageQueue(self):
        """ External interface to message queue. Throws an exception if the
        thread is closed. """
        with self.__lock:
            if self._open:
                return self.__messageQueue
            raise ReferenceError("Thread closed.")


    def _getFromQueue(self):
        """ Internal method to get the next message from the queue. A tuple
        of (target, newChat) is returned if a message is present, with
        target used for logging purposes and newMessage holding the actual
        pyKol chat object. If no message is present after the timeout, 
        or if stop() is called, the function returns (None, None). """
        startTime = time.time()
        loopStart = True
        inc = 0.5
        
        while loopStart or time.time() - startTime < self._timeout:
            loopStart = False
            try:
                (target, newChat) = self.__messageQueue.get(True, inc)
                return (target, newChat)
            except Queue.Empty:
                if self._stopEvent.is_set():
                    return (None, None)
        return (None, None)
            

    def run(self):
        running = True
        while running:
            target = None
            replyQueue = None
            try:
                # read new chats
                (target, newChat) = self._getFromQueue()
                if newChat is not None:
                    self._lastTarget = target if target is not None else "MAIN"
                    try:
                        # check if we need to return the reply
                        replyQueue = newChat.get("replyQueue", None) 
                        
                        r = SendChatRequest(self._session, newChat["text"])
                        data = tryRequest(r, numTries=8, 
                                          initialDelay=1, scaleFactor=1.25)


                        self._log.debug("({})> {}"
                                        .format(target, newChat["text"]))
                        chats = []
                        tmpChats = data["chatMessages"]
                        for chat in tmpChats:
                            chats.append(chat)
                        if replyQueue is not None:
                            replyQueue.put(chats)
                    except:
                        self._log.exception("E({})> {}"
                                        .format(target, newChat["text"]))
                        if replyQueue is not None:
                            replyQueue.put([])
                        raise Exception(
                                "Target {} unreachable.".format(target))
                    finally:
                        if replyQueue is not None:
                            replyQueue.put([])
                        self.__messageQueue.task_done()
            
                else: # newChat is None (meaning this thread needs to stop)
                    with self.__lock:
                        # no longer accept new chats
                        self._open = False
            except Exception:
                self._log.exception("Error in MessageThread to target {}" 
                                    .format(target))
                r = SendChatRequest(self._session, 
                                    "Error sending chat/PM to {}, "
                                    "see error log".format(target))
                tryRequest(r, nothrow=True, numTries=2, initialDelay=1)
                self._open = False
                # give up on enqueued messasges
                return
            sleep(self.throttleSeconds)
            with self.__lock:
                running = ((self._open or 
                                not self.__messageQueue.empty()) and 
                           self._session.isConnected)
        self._log.debug("Closed chat thread for target {}."
                        .format(self._lastTarget))


class MessageDispatcher(threading.Thread):
    """ A special thread that dispatches chats to different users.
    It MUST be run as a daemon. """
    maxThreads = 100 # will block if this many threads are open
    
    def __init__(self, session):
        """ Initialize the dispatcher """
        self._session = session
        self._messageQueue = Queue.Queue()
        self._chatThreads = {}
        self._log = logging.getLogger("chat")
        self._stopEvent = threading.Event()
        super(MessageDispatcher, self).__init__(name="MessageDispatcher")


    def close(self):
        """ Stop the dispatcher and its child threads. This MUST be called
        before shutdown or the bot will hang. """
        self._log.info("Stopping chat threads...")
        while len(self._chatThreads) > 0:
            for thr in self._chatThreads.values():
                thr.stop()
            sleep(1)
            self._removeDeadThreads()
            self._log.debug("Waiting for chat threads to close: {}"
                            .format(self._chatThreads))
        self._stopEvent.set()
        
        
    def run(self):
        while not self._stopEvent.is_set():
            try:
                # get new chat
                newChat = self._messageQueue.get(True, 3600)
                target = self._getTarget(newChat)
                
                # check if thread is alive...
                threadExists = (target in self._chatThreads and 
                                self._chatThreads[target].is_alive())
                
                if threadExists:
                    try:
                        # add new chat to thread
                        self._chatThreads[target].messageQueue.put(
                                                            (target, newChat))
                    except ReferenceError:
                        self._log.warning("dispatch failed; thread closed...")
                        threadExists = False
                    
                if not threadExists:
                    self._log.debug("Opening new thread for target {}."
                                    .format(target))
                    self._chatThreads[target] = self._startNewThread(target, 
                                                                     newChat)
            except Queue.Empty:
                pass
            except Exception:
                self._log.exception("Error in MessageDispatcher")
                r = SendChatRequest(self._session, 
                                    "Error sending chat/PM, see error log")
                tryRequest(r, nothrow=True)
            finally:
                self._messageQueue.task_done()
                self._removeDeadThreads()
                
    
    def _getTarget(self, chat):
        """ Get a string/integer that represents the chat/PM target. """
        if self._isPM(chat):
            return chat.get("recipient", None)
        return chat.get("channel", None)
    
    
    def _startNewThread(self, target, initialChat):
        """ Start a new thread to a new channel/recipient. """
        timeout = 5 if self._isPM(initialChat) else 300
        t = MessageThread(self._session, timeout, target)
        t.daemon = True
        t.messageQueue.put((target, initialChat))
        if len(self._chatThreads) >= self.maxThreads:
            self._log.info("Too many threads ({}/{}); blocking until "
                           "one is free.")
            while len(self._chatThreads) >= self.maxThreads:
                sleep(1)
                self._removeDeadThreads()
        t.start()
        return t

    
    def _isPM(self, chat):
        return "recipient" in chat

                
    def _removeDeadThreads(self):
        threadList = self._chatThreads.keys()
        for target in threadList:
            if not self._chatThreads[target].is_alive():
                del self._chatThreads[target]
    
        
    def dispatch(self, chat, replyQueue=None):
        """ 
        Send a chat. It is possible to obtain the return value of a 
        chat by supplying a Queue.Queue object as the replyQueue. When the 
        chat is sent, the return value will be placed in the replyQueue.
        """
        
        newChat = copy.deepcopy(chat)
        newChat["replyQueue"] = replyQueue
        self._messageQueue.put(newChat)        
        
        