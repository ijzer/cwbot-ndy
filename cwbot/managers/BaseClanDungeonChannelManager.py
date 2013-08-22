import abc
import time
import copy
import cwbot.util.DebugThreading as threading
from cwbot.util.tryRequest import tryRequest
from cwbot.kolextra.request.ClanRaidLogRequest import ClanRaidLogRequest
from cwbot.managers.MultiChannelManager import MultiChannelManager


class LogDict(dict):
    """ A dict with supressed __str__ and __repr__ to prevent clogging up
    the CLI """
    
    def __str__(self):
        return "{Event Log}"
    
    def __repr__(self):
        return "{Event Log}"



class BaseClanDungeonChannelManager(MultiChannelManager):
    """ Subclass of MultiChannelManager that incorporates Dungeon chat 
    and Raid Logs. Subclasses of this manager should specialize these functions
    for individual channel. Modules under this manager are initialized with 
    event data from the clan raid log and also receive periodic updates.
    Dungeon chat is separated and passed to the process_dungeon extended call,
    and log data is passed there as well. Periodic log updates are processed
    as well. 
    """

    __metaclass__ = abc.ABCMeta
    
    capabilities = set(['chat', 'inventory', 'admin', 'hobopolis', 'dread'])
    
    __raidlogDownloadLock = threading.RLock()
    _lastChatNum = None
    delay = 300
    
    def __init__(self, parent, identity, iData, config):
        """ Initialize the BaseClanDungeonChannelManager """
        self.__eventLock = threading.RLock() # lock for reading events
                                            # LOCK THIS BEFORE 
                                            # LOCKING self._syncLock
        self.__initialized = False
        self.__lastEvents = None
        self._lastEventCheck = 0
        super(BaseClanDungeonChannelManager, self).__init__(parent, 
                                                            identity, 
                                                            iData, 
                                                            config)
        self.__initialized = True
        
    
    def _initialize(self):
        with self.__raidlogDownloadLock:
            replies = self._raiseEvent("request_raid_log", None)
            if replies:
                self._log.info("Using previously acquired raid log...")
                self._raiseEvent("new_raid_log", 
                                 "__" + self.identity + "__", 
                                 replies[0].data)
            else:
                self._getRaidLog(noThrow=False, force=True)
        super(BaseClanDungeonChannelManager, self)._initialize()


    def _configure(self, config):
        """ Additional configuration for the log_check_interval option """
        super(BaseClanDungeonChannelManager, self)._configure(config)
        try:
            
            self.delay = min(self.delay, 
                             int(config.setdefault('log_check_interval', 15)))
        except ValueError:
            raise Exception("Error in module config: "
                            "(BaseClanDungeonChannelManager) "
                            "log_check_interval must be integral")

    
    def _moduleInitData(self):
        """ The initData here is the last read raid log events. """
        return self._filterEvents(self.lastEvents)

    
    @property
    def lastEvents(self):
        """ get the last-read events """
        with self.__eventLock:
            return copy.deepcopy(self.__lastEvents)
    
    
    @lastEvents.setter
    def lastEvents(self, val):
        with self.__eventLock:
            self.__lastEvents = copy.deepcopy(val)
    
            
    @lastEvents.deleter
    def lastEvents(self):
        with self.__eventLock:
            del self.__lastEvents


    def _getRaidLog(self, noThrow=True, force=False):
        """ Access the raid log and store it locally """
        with self.__raidlogDownloadLock:
            if not self.__initialized and not force:
                return self.lastEvents
            self._log.debug("Reading clan raid logs...")   
            rl = ClanRaidLogRequest(self.session)
            result = tryRequest(rl, nothrow=noThrow, numTries=5, 
                                initialDelay=0.5, scaleFactor=2)
            if result is None:
                self._log.warning("Could not read clan raid logs.")
                return self.lastEvents
            with self._syncLock:
                self._raiseEvent("new_raid_log", None, LogDict(result))
            return result


    def _updateLogs(self, force=False):
        """ Read new logs and parse them if it is time. Then call the
        process_log extended call of each module. """
        with self.__raidlogDownloadLock:
            if time.time() - self._lastEventCheck >= self.delay or force:
                result = self._getRaidLog()
                return result
            return self.lastEvents


    def _processDungeonChat(self, msg, checkNum):
        """
        This function is called when messages are received from Dungeon. 
        Like parseChat, the value checkNum is identical for chats received 
        at the same time.
        """
        replies = []
        with self.__raidlogDownloadLock:
            if self._lastChatNum != checkNum:
                # get new events
                self._lastChatNum = checkNum
                evts = self._updateLogs(force=True)
            else:
                evts = self.lastEvents
            with self.__eventLock:
                raidlog = self._filterEvents(evts)        
                with self._syncLock:
                    txt = msg['text']
                    for m in self._modules:
                        mod = m.module
                        printStr = mod.extendedCall('process_dungeon', 
                                                    txt, raidlog)
                        if printStr is not None:
                            replies.extend(printStr.split("\n"))
                    self._syncState()
        return replies
                    
                    
    def parseChat(self, msg, checkNum):
        """ Override of parseChat to split dungeon chat off from "regular"
        chat """
        if self._chatApplies(msg, checkNum):
            if msg['userName'].lower() == 'dungeon' and msg['userId'] == -2:
                return self._processDungeonChat(msg, checkNum)
            else:
                return self._processChat(msg, checkNum)
        return []
                
                
    def cleanup(self):
        with self.__eventLock:
            self.__initialized = False
        MultiChannelManager.cleanup(self)

            
    def _heartbeat(self):
        """ Update logs in heartbeat """
        if self.__initialized:
            self._updateLogs()
            super(BaseClanDungeonChannelManager, self)._heartbeat()
    
    
    def _eventCallback(self, eData):
        MultiChannelManager._eventCallback(self, eData)
        if eData.subject == "new_raid_log":
            raidlog = dict((k,v) for k,v in eData.data.items())
            self.lastEvents = raidlog
            if not self.__initialized:
                return
            self._notifyModulesOfNewRaidLog(raidlog)
        elif eData.subject == "request_raid_log":
            if self.lastEvents is not None:
                self._eventReply(LogDict(self.lastEvents))

            
    def _notifyModulesOfNewRaidLog(self, raidlog):
        # it's important not to process the log while responding
        # to chat, so we need a lock here.
        if not self.__initialized:
            return
        
        # important to keep this ordering for the locks
        with self.__eventLock:
            with self._syncLock:
                self._log.debug("{} received new log".format(self.identity))
                self._lastEventCheck = time.time()
                filteredLog = self._filterEvents(raidlog)
                self._handleNewRaidlog(filteredLog)
                for m in self._modules:
                    mod = m.module
                    mod.extendedCall('process_log', filteredLog)
                self._syncState()

            
            
############# Override the following:

    def _filterEvents(self, raidlog):
        """ This function is used by subclasses to remove unrelated event
        information. """
        return raidlog


    def _handleNewRaidlog(self, raidlog):
        """ This function is called when new raidlogs are downloaded. """
        pass
    
    @abc.abstractmethod
    def active(self):
        pass
    