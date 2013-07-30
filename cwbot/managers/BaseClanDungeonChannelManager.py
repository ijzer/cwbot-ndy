import abc
import time
import copy
import cwbot.util.DebugThreading as threading
from cwbot.util.tryRequest import tryRequest
from cwbot.kolextra.request.ClanRaidLogRequest import ClanRaidLogRequest
from cwbot.managers.MultiChannelManager import MultiChannelManager


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
    
    __eventLock = threading.RLock() # lock for reading events
    __lastEvents = None
    _lastEventCheck = 0
    _lastChatNum = None
    __eventsInitialized = threading.Event()
    delay = 300
    
    def __init__(self, parent, identity, iData, config):
        """ Initialize the BaseClanDungeonChannelManager """
        super(BaseClanDungeonChannelManager, self).__init__(parent, 
                                                            identity, 
                                                            iData, 
                                                            config)
    
    def _initialize(self):
        with self.__eventLock:
            if not self.__eventsInitialized.is_set():
                self._getRaidLog(noThrow=False, force=True)
                self.__eventsInitialized.set()
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

    
    def _processorInitData(self):
        """ The initData here is the last read raid log events. """
        return {'events': self.lastEvents}

    
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
        with self.__eventLock:
            if not self.__eventsInitialized.is_set() and not force:
                return self.lastEvents
            self._log.debug("Reading clan raid logs...")   
            rl = ClanRaidLogRequest(self.session)
            result = tryRequest(rl, nothrow=noThrow, numTries=5, 
                                initialDelay=0.5, scaleFactor=2)
            if result is None:
                self._log.warning("Could not read clan raid logs.")
                return self.lastEvents
            self.lastEvents = result
            self._lastEventCheck = time.time()
            self._handleNewRaidlog(result)
            return result


    def _updateLogs(self, force=False):
        """ Read new logs and parse them if it is time. Then call the
        process_log extended call of each module. """
        checked = False
        with self.__eventLock:
            if time.time() - self._lastEventCheck >= self.delay or force:
                result = self._getRaidLog()
                checked = True
            
            # it's important not to process the log while responding
            # to chat, so we need a lock here.
        if checked:
            with self._syncLock:
                for m in self._modules:
                    mod = m.module
                    mod.extendedCall('process_log', self._filterEvents(result))
                self._syncState()
        



    def _processDungeonChat(self, msg, checkNum):
        """
        This function is called when messages are received from Dungeon. 
        Like parseChat, the value checkNum is identical for chats received 
        at the same time.
        """
        replies = []
        if self._lastChatNum != checkNum:
            # get new events
            self._lastChatNum = checkNum
            self._updateLogs()
        events = self._filterEvents(self.lastEvents)        
        with self._syncLock:
            txt = msg['text']
            for m in self._modules:
                mod = m.module
                printStr = mod.extendedCall('process_dungeon', txt, events)
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
            self.__eventsInitialized.clear()
            MultiChannelManager.cleanup(self)

            
    def _heartbeat(self):
        """ Update logs in heartbeat """
        if self.__eventsInitialized.is_set():
            self._updateLogs()
            super(BaseClanDungeonChannelManager, self)._heartbeat()
            
            
            
############# Override the following:

    def _filterEvents(self, events):
        """ This function is used by subclasses to remove unrelated event
        information. """
        return events['events']


    def _handleNewRaidlog(self, raidlog):
        """ This function is called when new raidlogs are downloaded. """
        pass
    