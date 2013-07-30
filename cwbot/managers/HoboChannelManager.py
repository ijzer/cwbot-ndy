import re
import time
import copy
import cwbot.util.DebugThreading as threading
from cwbot.util.tryRequest import tryRequest
from cwbot.kolextra.request.ClanRaidLogRequest import ClanRaidLogRequest
from cwbot.managers.MultiChannelManager import MultiChannelManager


class HoboError(Exception):
    pass


def killPercent(n):
    """ Return percent done for a Hobopolis side zone, given the number of
    hoboes killed """
    return int(min(99, 100*n / 500.0))
            
            
class HoboChannelManager(MultiChannelManager):
    """ Subclass of ChannelManager that incorporates Hobopolis Dungeon chat 
    and Raid Logs. Modules under this manager are initialized with event data
    from the Hobopolis log and also receive periodic updates. Dungeon chat is
    separated and passed to the process_dungeon extended call, and log data
    is passed there as well. Periodic log updates are processed as well.
    Additionally, the state of all modules is reset when the hobopolis instance
    is reset.
    """
    capabilities = set(['chat', 'inventory', 'admin', 'hobopolis'])
    
    __eventLock = threading.RLock() # lock for reading events
    __lastEvents = None
    _lastEventCheck = 0
    _lastChatNum = None
    __eventsInitialized = threading.Event()
    
    def __init__(self, parent, identity, iData, config):
        """ Initialize the HoboChannelManager """
        with self.__eventLock:
            self._dungeonLog = None
            self.__eventsInitialized.clear()
            self._active = None # TRUE if Hodgman is still alive
            self._hoid = None
            self.delay = None
            super(HoboChannelManager, self).__init__(parent, identity, iData, 
                                                     config)
            if 'hobopolis' not in self._channelName:
                raise Exception("HoboChannelManager must be listening to "
                                "/hobopolis!")
            self.__eventsInitialized.set()


    def _configure(self, config):
        """ Additional configuration for the log_check_interval option """
        self._dungeonLog = self._log.getChild("dungeon")
        super(HoboChannelManager, self)._configure(config)
        try:
            self.delay = int(config.setdefault('log_check_interval', 15))
        except ValueError:
            raise Exception("Error in module config: (HoboChannelManager) "
                            "log_check_interval must be integral")
        
        
    def _initialize(self):
        """ This function initializes the processors with log data and 
        persistent state information. For the HoboChannelManager, old
        persistent state is deleted if a new instance is detected. 
        """

        # unlike "normal" modules, Hobopolis modules' states are reset 
        # after a new instance is created.
        # so, there is an extra step: if a new hobopolis instance exists, 
        # the state is cleared.
        self._initializeFromLog()
        
        try:
            # check database integrity
            if len(self._persist) == 0:
                self._persist['__init__'] = ""
        except ValueError:
            self._clearPersist()
            
        if '__hoid__' not in self._persist:
            # hobopolis id number not in state! This should never happen
            # but if it does, delete the old state.
            self._log.warning("Hobopolis instance not present in state.")
            self._clearPersist()
            self._persist['__hoid__'] = self._hoid
        else:
            hoid_old = self._persist['__hoid__']
            hoid_new = self._hoid
            if hoid_old != hoid_new:
                self._log.info("New hobopolis instance. Clearing state...")
                self._clearPersist()
            else:
                self._log.info("Same hobopolis instance as last shutdown.")
        super(HoboChannelManager, self)._initialize()
        self._updateLogs(force=True)
        

    def _processorInitData(self):
        """ The initData here is the last read Hobopolis events. """
        return {'events': self.lastEvents}
    
    
    def _syncState(self, force=False):
        '''Store persistent data for Hobo Modules. Here there is the 
        extra step of storing the old log and hoid. '''
        myLog = self.lastEvents
        with self._syncLock:
            if self._persist is not None:
                self._persist['__log__'] = myLog
                self._persist['__hoid__'] = self._hoid
            super(HoboChannelManager, self)._syncState(force)

    
    def _initializeFromLog(self):
        """ Initialize active status """
        events = self._getRaidLog(force=True)
        self._log.info("Initializing from Hobopolis log...")
        
        # is hodgman killed?
        self._active = not any(re.search(r'defeated +Hodgman', 
                                         item['event']) 
                               is not None for item in events)
        self._log.info("Hobopolis active = {}".format(self._active))
        return events

    
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
            rl = ClanRaidLogRequest(self.session)
            result = tryRequest(rl, nothrow=noThrow, numTries=5, 
                                initialDelay=0.5, scaleFactor=2)
            if result is None:
                self._log.warning("Could not read Hobo logs.")
                return self.lastEvents
            events = result['events']
            oldHoid = self._hoid
            if result['hoid'] is None:
                return []
            self._hoid = result['hoid']
            if self._hoid != oldHoid:
                self._log.info("Hobopolis instance number {} (old instance {})"
                               .format(self._hoid, oldHoid))
                self._dungeonLog.info("--- Hobopolis instance number {} ---"
                                      .format(self._hoid))
                if oldHoid is not None:
                    # oldHoid is only None upon first startup. So now it's
                    # time to reset!
                    self._resetDungeon()
            self._log.debug("Reading Hobo logs...")   
            self.lastEvents = events
            self._lastEventCheck = time.time()
            return events


    def _updateLogs(self, force=False):
        """ Read new logs and parse them if it is time. Then call the
        process_log extended call of each module. """
        if time.time() - self._lastEventCheck >= self.delay or force:
            events = self._processLogData()
            
            # it's important not to process the log while responding
            # to chat, so we need a lock here.
            with self._syncLock:
                for m in self._modules:
                    mod = m.module
                    mod.extendedCall('process_log', events)
                self._syncState()


    def _processLogData(self, events=None):
        """ Get log events and update active state """
        if events is None:
            events = self._getRaidLog()
        # search current log to see if hodgman is dead, if he's not
        # a new dungeon has started
        if self._active is not None:
            if not self._active:
                if not any(re.search(r'defeated +Hodgman', item['event'])
                           is not None for item in events):
                    self._log.info("Dungeon reset... new instance should "
                                   "appear soon.")
                    self._active = True
            else:
                if any(re.search(r'defeated +Hodgman', item['event']) 
                       is not None for item in events):
                    self._active = False
                    self._log.info("Hodgman killed!")
        return events
        

    def active(self):
        """ Is hodgman dead? """
        return self._active
    
    
    def _resetDungeon(self):
        """ 
        This function is called when a new Hobopolis instance is detected.
        """
        
        events = self._getRaidLog()
        with self._syncLock:
            self._active = True
            self.lastEvents = []
            self.sendChatMessage("The dungeon has been reset!")
            self._dungeonLog.info("---- DUNGEON RESET {} ----"
                                  .format(time.strftime(
                                                    '%c', time.localtime())))
            self._clearPersist()
            for m in self._modules:
                mod = m.module
                self._log.debug("Resetting {}".format(mod.id))
                mod.reset(self._processorInitData())
            self._processLogData(events)
        
    
    def _processDungeonChat(self, msg, checkNum):
        """
        This function is called when messages are received from Dungeon. 
        Like parseChat, the value checkNum is identical for chats received 
        at the same time.
        """
        replies = []
        events = None
        if self._lastChatNum != checkNum:
            # get new events
            self._lastChatNum = checkNum
            events = self._processLogData()
        else:
            events = self.lastEvents        
        with self._syncLock:
            txt = msg['text']
            self._dungeonLog.info("DUNGEON: {}".format(txt))
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
            super(HoboChannelManager, self)._heartbeat()
