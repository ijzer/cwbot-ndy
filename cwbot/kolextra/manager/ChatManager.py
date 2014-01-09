import logging
import re
from unidecode import unidecode
from HTMLParser import HTMLParser
from kol.request.GetChatMessagesRequest import GetChatMessagesRequest
from kol.request.OpenChatRequest import OpenChatRequest
from kol.util import ChatUtils
from cwbot.util.tryRequest import tryRequest
import Queue
from MessageDispatcher import MessageDispatcher

MAX_CHAT_LENGTH = 200

class ChatManager(object):
    """
    This class can be used as an interface for KoL chat.
    
    Improved to have threaded chat: each channel gets its own thread by
    using MessageDispatcher.
    
    Improved to use "Emote style": Chats with emote style use a distinctive
    chat style to make bot chats more noticible. Also fix a small kol entity
    bug in chat.
    
    Improved to have asynchronous chat: to send a chat with "fire-and-forget", 
    use sendChatMessage with waitForReply=False. The function will immediately
    return an empty list and the chat will be added to the chat queue. If you
    need the return value (to get KoL responses, e.g., for a /who chat), use
    waitForReply=True. The function will block until the chat is sent and
    return the response chats in a list (normal pyKol operation). 
    """

    _entityRegex = re.compile(r'&#(\d+);?')
    _parser = HTMLParser()

    def __init__(self, session):
        """Initializes the ChatManager with a particular KoL session and 
        then connects to chat."""
        self.session = session
        session.chatManager = self
        self.lastRequestTimestamp = 0
        r = OpenChatRequest(self.session)
        data = tryRequest(r)
        self.currentChannel = data["currentChannel"]
        self._dispatcher = MessageDispatcher(session)
        self._dispatcher.daemon = True
        self._dispatcher.start()


    def close(self):
        """ Close the chat manager and its child threads. This is REQUIRED
        or the bot will hang when you try to quit. It's the price you pay
        for multithreaded chats... """
        if self.session is not None:
            log = logging.getLogger()
            log.info("closing dispatcher")
            self._dispatcher.close()
            log.info("closed dispatcher")
            self.session = None


    def __del__(self):
        self.close()


    def getNewChatMessages(self):
        "Gets a list of new chat messages and returns them."
        r = GetChatMessagesRequest(self.session, self.lastRequestTimestamp)
        data = tryRequest(r, True, 3, 0.5, 1.5)
        if data is None:
            return []
        self.lastRequestTimestamp = data["lastSeen"]
        chats = data["chatMessages"]

        # Set the channel in each channel-less chat to be the current channel.
        for chat in chats:
            # fix a little entity bug in kol
            if "text" in chat:
                txt = chat["text"]
                txt = self._entityRegex.sub(r'&#\1;', txt)
                
                # convert to unicode (KoL/pykol has weird encoding)
                txtUnicode = u''.join(unichr(ord(c)) for c in txt)
                txtUnicode = self._parser.unescape(txtUnicode)
                if txtUnicode:
                    if any(c in txtUnicode[0] for c in [u"\xbf", u"\xa1"]):
                        txtUnicode = txtUnicode[1:]
                chat["text"] = unidecode(txtUnicode)
            
            t = chat["type"]
            if t == "normal" or t == "emote":
                if "channel" not in chat:
                    chat["channel"] = self.currentChannel

        return chats


    def sendChatMessage(self, text, waitForReply=False, useEmoteFormat=False):
        """
        Sends a chat message. This method will throttle chats sent to the 
        same channel or person. Otherwise the KoL server could display them 
        out-of-order to other users.
        """
        messages = []

        # Clean the text.
        text = ChatUtils.cleanChatMessageToSend(text)

        # Get information about the chat.
        chatInfo = ChatUtils.parseChatMessageToSend(text)

        # remove commands from beginning of text
        if useEmoteFormat and chatInfo.get("type", None) != "private":

            # get text, not counting /commands at beginning
            arr = text.split(' ')
            while len(arr) > 0 and arr[0][0] == "/":
                del arr[0]
            text = ' '.join(arr)

            if "channel" in chatInfo:
                text = "/%s /me : %s" % (chatInfo["channel"], text)
            else:
                text = "/me : %s" % (text)
            chatInfo["isEmote"] = True


        if len(text) > MAX_CHAT_LENGTH:

            # Figure out the prefix that should be appended to every message.
            prefix = ''
            if "type" in chatInfo:
                if chatInfo["type"] == "private":
                    prefix = "/w %s " % chatInfo["recipient"]
                elif chatInfo["type"] == "channel":
                        if "channel" in chatInfo:
                            prefix = "/%s " % chatInfo["channel"]
                        if "isEmote" in chatInfo:
                            prefix += "/me "

            # Construct the array of messages to send.
            while len(text) > (MAX_CHAT_LENGTH - len(prefix)):
                index = text.rfind(" ", 0, MAX_CHAT_LENGTH - len(prefix) - 6)
                if index == -1:
                    index = MAX_CHAT_LENGTH - len(prefix) - 6
                    msg = text[:index] + "..."
                    text = text[index:]
                else:
                    msg = text[:index] + "..."
                    text = text[index + 1:]

                if len(messages) > 0:
                    msg = "... " + msg
                    messages.append(prefix + msg)
                else:
                    messages.append(msg)

            if len(messages) > 0:
                messages.append(prefix + "... " + text)
            else:
                messages.append(text)
        else:
            messages.append(text)


        # Send the message(s).
        chats = []
        for message in messages:
            chatToSend = chatInfo
            chatToSend["text"] = message
            replyQueue = Queue.Queue()
            self._dispatcher.dispatch(chatToSend, replyQueue)

            if waitForReply:
                replies = replyQueue.get()
                chats.extend(replies)
                replyQueue.task_done()

        for chat in chats:
            if 'listen' in chat['type'] or 'channel' in chat['type']:
                if 'currentChannel' in chat:
                    self.currentChannel = chat['currentChannel']

        return chats
