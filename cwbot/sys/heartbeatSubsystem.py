import weakref
import Queue
import time
import logging
import uuid
from collections import deque
import cwbot.util.DebugThreading as threading
from cwbot.util.ExceptionThread import ExceptionThread
from cwbot.util.emptyObject import EmptyObject


class HeartbeatSubsystem(object):
    """ The class that handles the heartbeat (simple threading) subsystem.
    
    To use the heartbeat subsystem in your class, derive from 
    HeartbeatSubsystem.HeartbeatCapable. See full documentation in that class.
    """
    
    _lock = threading.RLock()
    class DuplicateObjectException(Exception):
        pass
    
    class HeartbeatException(Exception):
        pass

    
    class _HeartbeatObject(object):
        def __init__(self, obj, callback):
            self.obj = weakref.ref(obj)
            self.callback = callback
            self.done = threading.Event()
            self.stop = threading.Event()
            self.lock = threading.RLock()

    
    class HeartbeatCapable(EmptyObject):
        """An heartbeat-capable class has a _heartbeat() method, which is 
        called periodically in a separate thread. The frequency of this method
        call is configurable when constructing the HeartbeatSubsystem. 
        
        To enable the heartbeat, use the heartbeatRegister() method with
        the HeartbeatSubsystem object to which the object is bound. Each
        object may be registered to only one HeartbeatSubsystem. To stop
        the heartbeat, use the heartbeatUnregister() method.


        """

        def __init__(self, hbSys=None, **kwargs):
            self.__hb = None
            self.__registered = threading.Lock()
            self.__lock = threading.RLock()
            if hbSys is not None:
                self.heartbeatRegister(hbSys)
            super(HeartbeatSubsystem.HeartbeatCapable, self).__init__(**kwargs)
                
        
        def __del__(self):
            self.heartbeatUnregister()
                
                
        def __heartbeat(self):
            # a lock is unnecessary here, since the task thread has a lock
            # already
            self._heartbeat()

        
        @property
        def heartbeatSubsystem(self):
            return self.__hb
                
            
        def heartbeatRegister(self, hbSubsystem):
            if not self.__registered.acquire(False):
                raise HeartbeatSubsystem.HeartbeatException(
                        "Object {} ({}) is already assigned"
                        " to an event subsystem."
                        .format(self.__id, self.__type))
            with self.__lock:
                hbSubsystem.registerObject(self, self.__heartbeat)
                self.__hb = hbSubsystem
            
            
        def heartbeatUnregister(self):
            with self.__lock:
                if self.__hb is not None:
                    self.__hb.unregisterObject(self)
                    self.__hb = None
                    try:
                        self.__registered.release()
                    except threading.ThreadError:
                        pass
            
            
        def _heartbeat(self):
            pass
    
    
    class _HeartbeatTaskThread(ExceptionThread):
        def __init__(self, queue):
            self._log = logging.getLogger("heartbeat")
            self.queue = queue
            self._stopEvent = threading.Event()
            self.id = str(uuid.uuid4())
            super(HeartbeatSubsystem._HeartbeatTaskThread, self).__init__(
                                                    name="Heartbeat-Task")
            
        def stop(self):
            self._stopEvent.set()
            
        def _run(self):
            self._log.debug("Heartbeat task thread {} started."
                            .format(self.id))
            while not self._stopEvent.is_set():
                task = None
                try:
                    task = self.queue.get(True, 0.1)
                except Queue.Empty:
                    pass
                if task is not None:
                    with task.lock:
                        if not task.stop.is_set():
                            obj = task.obj()
                            if obj is not None:
                                task.callback()
                                task.done.set()
                            self.queue.task_done()
        
    
    class _HeartbeatMainThread(ExceptionThread):
        def __init__(self, numThreads, period, stopEvent):
            self._log = logging.getLogger("heartbeat")
            self._n = numThreads
            self._t = period
            self._stopEvent = stopEvent
            self.queue = Queue.Queue()
            self._objs = []
            self._lock = threading.RLock()
            self._threads = []
            super(HeartbeatSubsystem._HeartbeatMainThread, self).__init__(
                    name="Heartbeat-Main")
            
        def _run(self):
            self._initialize()
            reAddList = deque()
            try:
                while not self._stopEvent.is_set():
                    #time.sleep(0.001)
                    time.sleep(1)
                    self._checkThreadExceptions()
                    self._clearDead()
                    with self._lock:
                        curTime = time.time()
                        for obj in self._objs:
                            o = obj.obj()
                            if o is not None:
                                if obj.done.is_set():
                                    obj.done.clear()
                                    reAddList.append((curTime, obj))
                        while (reAddList 
                                and reAddList[0][0] + self._t < curTime):
                            self._enqueue(reAddList[0][1])
                            reAddList.popleft()
            finally:
                for th in self._threads:
                    th.stop()
                for th in self._threads:
                    self._log.debug("Joining thread {}...".format(th.id))
                    th.join()
                             

        def registerObject(self, obj, callback):
            with self._lock:
                self._clearDead()
                newHO = HeartbeatSubsystem._HeartbeatObject(obj, callback)
                if any(True for ho in self._objs
                       if obj is ho.obj() and obj is not None):
                    raise HeartbeatSubsystem.DuplicateObjectException(
                            "Object {!s} is already registered."
                            .format(obj))
                self._objs.append(newHO)
                self._enqueue(newHO)

                
        def unregisterObject(self, obj):
            with self._lock:
                self._clearDead()
                oldSize = len(self._objs)
                matches = [ho for ho in self._objs
                           if ho.obj() is obj
                           and obj is not None]
                self._objs = [ho for ho in self._objs
                               if ho.obj() is not obj
                               and obj is not None]
                sizeDiff = oldSize - len(self._objs)
                if sizeDiff == 0:
                    raise ValueError("Object {!s} is not registered."
                                     .format(obj))
                elif sizeDiff > 1:
                    raise Exception(
                          "Internal error: duplicate objects {!s} "
                          "detected in event registry.".format(obj))
                elif len(matches) != 1:
                    raise Exception(
                          "Internal error: More than one match "
                          "for object {!s}.".format(obj))
                o = matches[0]
                with o.lock:
                    o.stop.set()
                                
                                
        def _initialize(self):
            for _i in range(self._n):
                newThread = HeartbeatSubsystem._HeartbeatTaskThread(self.queue)
                newThread.start()
                self._threads.append(newThread)

                            
        def _checkThreadExceptions(self):
            for thread_ in self._threads:
                if thread_.exception.is_set():
                    # this will cause an exception
                    thread_.join()

                    
        def _clearDead(self):
            with self._lock:
                self._objs = [o for o in self._objs if o.obj() is not None]

                
        def _enqueue(self, obj):
            self.queue.put_nowait(obj)
            
    
    def __init__(self, numThreads, period, stopEvent=threading.Event()):
        self._log = logging.getLogger("heartbeat")
        self._thread = self._HeartbeatMainThread(numThreads, period, stopEvent)
        self._thread.start()

    
    @property
    def exception(self):
        return self._thread.exception.is_set()

    
    def registerObject(self, obj, callback):
        self._thread.registerObject(obj, callback)
        

    def unregisterObject(self, obj):
        self._thread.unregisterObject(obj)
    
    
    def raiseException(self):
        if self.exception:
            self._thread.join()
        else:
            raise Exception("Tried to get heartbeat exception, but there "
                            "is none.")
        
    
    def join(self):
        self._log.info("Joining heartbeat threads...")
        self._thread.join()
        self._log.info("All threads joined.")
        