import re
import time
from cwbot.managers.BaseClanDungeonChannelManager \
             import BaseClanDungeonChannelManager


class HoboError(Exception):
    pass


def killPercent(n):
    """ Return percent done for a Hobopolis side zone, given the number of
    hoboes killed """
    return int(min(99, 100*n / 500.0))
            
            
class HoboChannelManager(BaseClanDungeonChannelManager):
    """ Subclass of BaseClanDungeonChannelManager. 
    This manager monitors Hobopolis in specific, resetting all its modules
    when the hobopolis instance is reset.
    """

    capabilities = set(['chat', 'inventory', 'admin', 'hobopolis'])

    def __init__(self, parent, identity, iData, config):
        """ Initialize the HoboChannelManager """
        self.__initialized = False
        self._hoid = None
        self._active = None # TRUE if Hodgman is still alive
        super(HoboChannelManager, self).__init__(parent, identity, iData, 
                                                 config)
        if 'hobopolis' not in self._channelName:
            raise Exception("HoboChannelManager must be listening to "
                            "/hobopolis!")
        self.__initialized = True
            


    def _configure(self, config):
        """ Additional configuration for the log_check_interval option """
        super(HoboChannelManager, self)._configure(config)
        
        
    def _initialize(self):
        super(HoboChannelManager, self)._initialize()
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
        

    def _processorInitData(self):
        """ The initData here is the last read Hobopolis events. """
        return self._filterEvents(self.lastEvents)

        
    def _filterEvents(self, raidlog):
        relevant_keys = ['events', 'hoid']
        return dict((k,raidlog[k]) for k in relevant_keys if k in raidlog)
    
    
    def _syncState(self, force=False):
        '''Store persistent data for Hobo Modules. Here there is the 
        extra step of storing the old log and hoid. '''
        with self._syncLock:
            if self._persist is not None:
                self._persist['__log__'] = self._filterEvents(self.lastEvents)
                self._persist['__hoid__'] = self._hoid
            super(HoboChannelManager, self)._syncState(force)

    
    def _initializeFromLog(self):
        """ Initialize active status """
        raidlog = self._filterEvents(self.lastEvents)
        self._log.info("Initializing from Hobopolis log...")
        
        # is hodgman killed?
        self._active = not any(re.search(r'defeated\s+Hodgman', 
                                         item['event']) 
                               is not None for item in raidlog['events'])
        self._log.info("Hobopolis active = {}".format(self._active))


    def _handleNewRaidlog(self, raidlog):
        """ Get log events and update active state """
        if not self.__initialized:
            return
        events = raidlog['events']
        # search current log to see if hodgman is dead, if he's not
        # a new dungeon has started
        if not self._active:
            if not any(re.search(r'defeated\s+Hodgman', item['event'])
                       is not None for item in events):
                self._log.info("Dungeon reset... new instance should "
                               "appear soon.")
                self._active = True
        else:
            if any(re.search(r'defeated\s+Hodgman', item['event']) 
                   is not None for item in events):
                self._active = False
                self._log.info("Hodgman killed!")

        if raidlog.get('hoid', None) is not None:
            oldHoid = self._hoid
            self._hoid = raidlog['hoid']
            if self._hoid != oldHoid:
                self._log.info("Hobopolis instance number {} (old instance {})"
                               .format(self._hoid, oldHoid))
                if oldHoid is not None:
                    # oldHoid is only None upon first startup. So now it's
                    # time to reset!
                    self._resetDungeon()
        

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
            self.sendChatMessage("The dungeon has been reset!")
            self._log.info("---- DUNGEON RESET {} ----"
                                  .format(time.strftime(
                                                    '%c', time.localtime())))
            self._clearPersist()
            for m in self._modules:
                mod = m.module
                self._log.debug("Resetting {}".format(mod.id))
                mod.reset(self._processorInitData())

