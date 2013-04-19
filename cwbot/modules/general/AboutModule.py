import time
import random
import re
import urllib2
import socket
from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.common.kmailContainer import Kmail


_url = "http://sourceforge.net/projects/cwbot/"
_ranks = {'major': 1, 'minor': 2, 'bugfix': 3}

def _versionGreater(new, old, rank):
    if new is None:
        return False
    elif old is None:
        return True
 
    if rank not in _ranks:
        raise KeyError("invalid rank")
    newSeries = map(int, new.split("."))
    oldSeries = map(int, old.split("."))
    for i in range(_ranks[rank]):
        if newSeries[i] > oldSeries[i]:
            return True
    return False


class AboutModule(BaseChatModule):
    """ A module that shows version information with the !about command and
    notifies players and admins when there is a software update. 
    
    NOTE: To get PMs about updates, you need the update_notify permission!
    
    Configuration options:
    chat_interval: number of seconds between public notification of new
                   version (default: 86000)
    channel: default channel to show message (default: DEFAULT)
    notify_on: show message for what kind of updates: choose from
               "bugfix", "minor", "major" (default: bugfix)
    """
    
    requiredCapabilities = ['chat']
    _name = "about"
    
    def __init__(self, *args, **kwargs):
        self._lastCheck = None
        self._lastChatNotify = None
        self._lastAvailableVersion = None
        self._kmailed = {}
        self._privateMessaged = {}
        self._chatEvery = None
        self._notifyOn = "bugfix"
        self._channel = None
        self._firstcheck = None
        super(AboutModule, self).__init__(*args, **kwargs)
        
        
    def _configure(self, config):
        self._chatEvery = int(config.setdefault('chat_interval', '86000'))
        self._channel = config.setdefault('channel', "DEFAULT")
        self._lastChatNotify = (time.time() 
                                - random.randint(0, self._chatEvery))
        self._notifyOn = config.setdefault('notify_on', 'bugfix')
        if self._notifyOn not in _ranks:
            raise KeyError("Invalid notify_on specification. Valid "
                           " values are: {}"
                           .format(', '.join(_ranks.keys())))
        
        
    def initialize(self, state, initData):
        self._firstcheck = True
        self._lastCheck = state['last_check']
        self._lastAvailableVersion = state['available']
        kmailed = state['kmailed']
        pmed = state['pm']
        self._kmailed = dict((int(k), v) for k,v in kmailed.items())
        self._privateMessaged = dict((int(k), v) for k,v in pmed.items())
        oldVersion = state['version']
        if oldVersion != self.properties.version:
            self._resetNotified()

            
    def _resetNotified(self):
        self._kmailed = {}
        self._privateMessaged = {}
        
        
    @property
    def initialState(self):
        return {'last_check': None,
                'available': None,
                'version': self.properties.version,
                'kmailed': {},
                'pm': {}}
    
    
    @property
    def state(self):
        return {'last_check': self._lastCheck,
                'available': self._lastAvailableVersion,
                'version': self.properties.version,
                'kmailed': self._kmailed,
                'pm': self._privateMessaged}
                
        
    def _availableCommands(self):
        return {'about': '!about: show version information.'}
        
    
    def _processCommand(self, message, cmd, args):
        if cmd == "about":
            return ("cwbot version {}. {}"
                    .format(self.properties.version, _url))

                    
    def _heartbeat(self):
        now = time.time()
        if (self._lastCheck is None or
            now - self._lastCheck > 60 * 60 * 24):
            self._checkNew()
        if _versionGreater(self._lastAvailableVersion,
                           self.properties.version,
                           self._notifyOn):
            if self._chatEvery > 0:
                if now - self._lastChatNotify > self._chatEvery:
                    self.chat("New version available: {}".format(_url))
                    self._lastChatNotify = now
            if self._firstcheck:
                self._firstcheck = False
                updateAdmins = self.properties.getAdmins('update_notify')
                for uid in updateAdmins:
                    lastKmail = self._kmailed.get(uid, 0)
                    if now - lastKmail >= 14 * 24 * 60 * 60:
                        k = Kmail(uid, "New cwbot version ({}) available: {}"
                                       .format(self._lastAvailableVersion, _url))
                        self.sendKmail(k)
                        self._kmailed[uid] = now
                    else:
                        self.log('Already kmailed {} about update.'.format(uid))
                    lastPm = self._privateMessaged.get(uid, 0)
                    if now - lastPm >= 7 * 24 * 60 * 60:
                        self.whisper(uid, "New cwbot version available: {}"
                                          .format(_url))
                        self._privateMessaged[uid] = now
                    else:
                        self.log('Already pm\'ed {} about update.'.format(uid))
        
            
    def _checkNew(self):
        self.log("Checking for new version...")
        try:
            txt = urllib2.urlopen(
                    'http://sourceforge.net/projects/cwbot/files/').read()
            m = re.search(r'Download cwbot_(\d+\.\d+\.\d+)\.zip \(', txt)
            if m is not None:
                available = m.group(1)
                self.log("Current version: {}; new version {}"
                         .format(self.properties.version, available))
                if _versionGreater(available, 
                                   self._lastAvailableVersion,
                                   self._notifyOn):
                    self.log("New version available.")
                    self._lastAvailableVersion = available
                    self._resetNotified()
                elif available != self.properties.version:
                    self.log("New version available, but we have already "
                             "notified admins.")
            else:
                self.log("Could not check for new version...")
            self._lastCheck = time.time()
        except (urllib2.URLError, socket.timeout):
            self.log("Error loading site for update")
            self._lastAvailableVersion = None
            
            
    def _eventCallback(self, eData):
        if eData.subject == 'state':
            self._eventReply(self.state)
