from cwbot.modules.BaseChatModule import BaseChatModule
import time
import datetime
import pytz #@UnresolvedImport
import math
import logging, logging.handlers
import threading
from collections import defaultdict
from cwbot.util.textProcessing import stringToList, listToString
from cwbot.common.kmailContainer import Kmail


tz = pytz.timezone('America/Phoenix')
MAX_KMAIL = 1700

class ChatLogModule(BaseChatModule):
    """ 
    A basic chat logging module that logs chats to file and also allows users
    to query for the most recent chats in a Kmail. Only the last ~2000
    characters in each channel are held in memory. The chat_only_channels
    option in the config file .
    
    Configuration options:
    clan_only_channels - takes a comma-separated list of chat channels
                         for which only clan memebers can get logs 
                         [default = clan, hobopolis, slimetube]
    """
    
    requiredCapabilities = ['chat']
    _name = "chatlog"
    
    def __init__(self, manager, identity, config):
        self._clanOnly = []
        super(ChatLogModule, self).__init__(manager, identity, config)
        self._chatlog = []
        self._channels = set([])
        self._lock = threading.RLock()
        self._lastClean = time.time()
        tmp = logging.getLogger("_chatlog_")
        tmp.propagate = False
        tmp.setLevel(logging.INFO)


    def logChat(self, message, delaySeconds=0):
        # add a chat to the chatlog (both the file and the memory-log)
        channel = message['channel']
        logger = logging.getLogger("_chatlog_.{}".format(channel))
        if channel not in self._channels:
            # open new log
            self._channels.add(channel)
            fileHandler = logging.handlers.RotatingFileHandler(
                'log/chatlog-{}.log'.format(channel),
                maxBytes=5000000, backupCount=1)
            f = logging.Formatter('[%(asctime)s] %(message)s',
                                  '%m-%d %H:%M:%S')
            fileHandler.setFormatter(f)
            logger.handlers = []
            logger.addHandler(fileHandler)
            logger.info("-- Begin log --")
        
        uname = message.get('userName', "(somebody)")
        # write to file
        logger.info("{}: {}".format(uname, message['text']))
        now = datetime.datetime.now(tz)
        # write to memory 
        with self._lock:
            self._chatlog.append({'time': now, 
                                  'channel': channel, 
                                  'user': uname, 
                                  'text': message['text'], 
                                  'type': message.get('type', "")})


    def _configure(self, config):
        self._clanOnly = map(
                str.lower, stringToList(config.get('clan_only_channels', "")))
        self.log("Chat log clan only channels: {}"
                 .format(', '.join(self._clanOnly)))
        config['clan_only_channels'] = listToString(self._clanOnly)
        
        
    def reduceChatLog(self):
        """ remove old entries from chat log in memory """
        with self._lock:
            # remove old entries from chat log
            self._chatlog.sort(key=lambda x:x['time'])
    
            # minimum characters per line ( "[HH:MM:SS] NAM: T" )
            line_minlength = 17 
            maxlines = int(math.ceil(float(MAX_KMAIL) / line_minlength))
            
            # split into separate log for each channel
            sublogs = defaultdict(list)
            for line in self._chatlog:
                sublogs[line['channel']].append(line)
                
            # delete old lines and place back in log
            self._chatlog = []
            for slog in sublogs.values():
                self._chatlog.extend(slog[-maxlines:])
                
            # sort log
            self._chatlog.sort(key=lambda x:x['time'])
            self._lastClean = time.time()
        
        
    def sendChatLog(self, channel, uid):
        chars = 0
        messages = []
        with self._lock:
            self.reduceChatLog()
            for msg in (m for m in reversed(self._chatlog) 
                        if m['channel'] == channel):
                spacer = "" if msg['type'] == "emote" else ":"
                line = ("[{}] {}{} {}"
                        .format(msg['time'].strftime("%I:%M:%S"), 
                                msg['user'], spacer, msg['text']))
                chars += len(line) + 1
                if chars <= MAX_KMAIL:
                    messages.append(line)
                else:
                    break
        msgText = '\n'.join(reversed(messages))
        self.sendKmail(Kmail(uid=uid, text=msgText))
        return True
        

    def _processCommand(self, message, cmd, args):
        if message['type'] in ['normal', 'listen', 'emote']:
            self.logChat(message)

        if cmd == "chatlog":
            uid = message['userId']
            channel = args.lower().strip()
            if channel == "":
                channel = message.get('channel', "").lower()
                if channel == "" or message['type'] == "private":
                    return "Usage: '!chatlog CHANNELNAME'"
            if channel in self._channels:
                if channel in self._clanOnly:
                    if not self.parent.checkClan(uid):
                        return "That log is restricted to clan members only."
                result = self.sendChatLog(channel, uid)
                if result:
                    return "Log for channel /{} sent.".format(channel)
                else:
                    return "Error sending message to {}.".format(uid)
            else:
                return "I don't have a log for channel /{}.".format(channel)
        return None


    def _eventCallback(self, eData):
        s = eData.subject
        if s == "chat":
            if eData.data['text'][0] == "/":
                return
            msg = {'channel': eData.data['channel'], 
                   'text': eData.data['text'], 
                   'userName': self.parent.properties.userName}
            self.logChat(msg)
            
            
    def cleanup(self):
        for ch in self._channels:
            logger = logging.getLogger("_chatlog_.{}".format(ch))
            logger.info("-- End log --\n")

    
    def _availableCommands(self):
        return {"chatlog": "!chatlog: get a kmail with the recent "
                           "chat history for this channel."}


    def _heartbeat(self):
        with self._lock:
            if time.time() - self._lastClean > 30*60:
                self.reduceChatLog()
