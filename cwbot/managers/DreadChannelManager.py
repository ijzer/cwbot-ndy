import re
import time
from cwbot.managers.BaseClanDungeonChannelManager \
             import BaseClanDungeonChannelManager


class DreadError(Exception):
    pass
            
            
class DreadChannelManager(BaseClanDungeonChannelManager):
    """ Subclass of BaseClanDungeonChannelManager. 
    This manager monitors Dreadsylvania in specific, resetting all its modules
    when the instance is reset.
    """

    capabilities = set(['chat', 'inventory', 'admin', 'dread'])

    def __init__(self, parent, identity, iData, config):
        """ Initialize the DreadChannelManager """
        self.__initialized = False
        self._dvid = None
        self._active = None # TRUE if an area is still active
        super(DreadChannelManager, self).__init__(parent, identity, iData, 
                                                 config)
        if 'dread' not in self._channelName:
            raise Exception("HoboChannelManager must be listening to "
                            "/hobopolis!")
        self.__initialized = True
            


    def _configure(self, config):
        """ Additional configuration for the log_check_interval option """
        super(DreadChannelManager, self)._configure(config)
        
        
    def _initialize(self):
        super(DreadChannelManager, self)._initialize()
        """ This function initializes the processors with log data and 
        persistent state information. For the DreadChannelManager, old
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
            
        if '__dvid__' not in self._persist:
            # dread id number not in state! This should never happen
            # but if it does, delete the old state.
            self._log.warning("Dreadsylvania instance not present in state.")
            self._clearPersist()
            self._persist['__dvid__'] = self._dvid
        else:
            dvid_old = self._persist['__dvid__']
            dvid_new = self._dvid
            if dvid_old != dvid_new:
                self._log.info("New Dreadsylvania instance. Clearing state...")
                self._clearPersist()
            else:
                self._log.info("Same Dreadsylvania instance as last shutdown.")
        

    def _processorInitData(self):
        """ The initData here is the last read Dreadsylvania events. """
        return self._filterEvents(self.lastEvents)

        
    def _filterEvents(self, raidlog):
        relevant_keys = ['dvid', 'dread']
        relevant_event_categories = ['The Village', 
                                     'The Woods', 
                                     'The Castle', 
                                     'Miscellaneous']
        try:
            d = dict((k,raidlog[k]) for k in relevant_keys if k in raidlog)
            d['events'] = [e for e in raidlog['events'] 
                           if e['category'] in relevant_event_categories]
            return d
        except Exception:
            print(raidlog)
            raise
    
    
    def _syncState(self, force=False):
        '''Store persistent data for Hobo Modules. Here there is the 
        extra step of storing the old log and hoid. '''
        with self._syncLock:
            if self._persist is not None:
                self._persist['__log__'] = self._filterEvents(self.lastEvents)
                self._persist['__dvid__'] = self._dvid
            super(DreadChannelManager, self)._syncState(force)

    
    def _initializeFromLog(self):
        """ Initialize active status """
        raidlog = self._filterEvents(self.lastEvents)
        self._log.info("Initializing from Dreadsylvania log...")
        
        self._active = self._dungeonIsActive(raidlog)
        self._log.info("Dread active = {}".format(self._active))


    def _dungeonIsActive(self, raidlog):
        """ Check if dungeon is active """
        bossRegex = re.compile(r"""defeated\s+(The Great Wolf of the Air|The Unkillable Skeleton|the Zombie Homeowners' Association|Count Drunkula|Falls-From-Sky|Mayor Ghost)""", re.IGNORECASE)
        bossesKilled = [e for e in raidlog['events'] 
                        if bossRegex.search(e['event']) is not None]
        return len(bossesKilled) < 3
    

    def _handleNewRaidlog(self, raidlog):
        """ Get log events and update active state """
        if not self.__initialized:
            return
        # search current log to see if hodgman is dead, if he's not
        # a new dungeon has started
        if not self._active:
            if self._dungeonIsActive(raidlog):
                self._log.info("Dungeon reset... new instance should "
                               "appear soon.")
                self._active = True
        else:
            if not self._dungeonIsActive(raidlog):
                self._active = False
                self._log.info("Dread clear!")

        if raidlog.get('dvid', None) is not None:
            oldDvid = self._dvid
            self._dvid = raidlog['dvid']
            if self._dvid != oldDvid:
                self._log.info("Dread instance number {} (old instance {})"
                               .format(self._dvid, oldDvid))
                if oldDvid is not None:
                    # oldDvid is only None upon first startup. So now it's
                    # time to reset!
                    self._resetDungeon()
        

    def active(self):
        """ Are the bosses dead? """
        return self._active
    
    
    def _resetDungeon(self):
        """ 
        This function is called when a new Dreadsylvania instance is detected.
        """
        with self._syncLock:
            self._active = True
            self.sendChatMessage("The dungeon has been reset!")
            self._log.info("---- DUNGEON RESET {} ----"
                                  .format(time.strftime(
                                                    '%c', time.localtime())))
            self._clearPersist()
            for m in self._modules:
                mod = m.module
                self._log.debug("Resetting {}".format(mod.id))
                mod.reset(self._processorInitData())

