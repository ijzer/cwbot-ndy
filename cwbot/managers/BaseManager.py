import weakref
import time
import abc
import logging
from cwbot import logConfig
import cwbot.util.DebugThreading as threading
from cwbot.util.textProcessing import toTypeOrNone
from cwbot.common.objectContainer import ModuleEntry
from cwbot.common.exceptions import FatalError
from cwbot.util.importClass import easyImportClass
from kol.request.UserProfileRequest import UserProfileRequest
from cwbot.util.tryRequest import tryRequest
from cwbot.sys.eventSubsystem import EventSubsystem
from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem
from cwbot.sys.database import encode


class ManagerMetaClass(abc.ABCMeta):
    def __init__(cls, name, bases, attrs): #@NoSelf
        if 'capabilities' not in attrs:
            raise NotImplementedError(
                    "The '{}' class does not implement a"
                    " 'capabilities' attribute".format(name))
        super(ManagerMetaClass, cls).__init__(name, bases, attrs)
        
        
class BaseManager(EventSubsystem.EventCapable,
                  HeartbeatSubsystem.HeartbeatCapable):
    """
    Base class for all manager objects. Every subclass MUST impliment a
    capabilities attribute that is a list of strings.
    
    Managers are the middle tier of processing. The CommunicationDirector
    holds many managers, and each manager holds many modules.
    
    The job of a manager is to filter information. The CommunicationDirector
    passes every Kmail and Chat to every manager. Each manager filters this
    information, passing applicable Kmails/Chats to each of its
    modules. Manager filtering should be "all-or-nothing": Managers should
    decide if a Kmail/Chat is applicable, and if so, pass it to each of
    its modules. It is not the job of a manager to determine which of its
    modules should process which chat/kmail. 
    
    It is also the manager's job to handle permissions by checking if a user
    has the required permission before passing chats/kmails to modules. The
    same applies to checking in-clan status.
    
    A manager may also pass supplementary information to its modules,
    by both supplying information via the _processorInitData method and
    possibly through other methods.
    
    Managers are also in charge of syncing the state of their constituent
    modules by periodically calling _syncState(), which utilizes the sqlite3
    database. 
    """
    
    __metaclass__ = ManagerMetaClass
    capabilities = ['inventory', 'chat']
    
    __clanMembers = set([])
    __clanNonMembers = {}
    def __init__(self, parent, identity, iData, config):
        """ Initialize the BaseManager. When you call this from a
        derived class, the following occurs:
        
        1. The manager is linked to the Heartbeat and Event subsystems.
        2. Various variables are established.
        3. The _configure() method is called.
        4. The modules in the config map are added to self._modules.
        5. The _initialize() method is called.
        """
        
        self._initialized = False
        super(BaseManager, self).__init__(name="sys.{}".format(identity), 
                                          identity=identity, 
                                          evSys=parent.eventSubsystem,
                                          hbSys=parent.heartbeatSubsystem)
        self._syncLock = threading.RLock() # lock for syncing state
        self.__configureOnline = False
        self.__initializeOnline = False
        self._s = iData.session
        self._c = iData.chatManager
        logConfig.setFileHandler(identity, "log/{}.log".format(identity))
        self._log = logging.getLogger(identity)
        self._log.info("----- Manager {} startup -----".format(identity))
        self._invMan = iData.inventoryManager
        self._props = iData.properties
        self._db = iData.database
        self.identity = identity
        self.syncTime = 300
        self._lastSync = time.time()
        
        self._db.createStateTable()
        self._persist = self._db.loadStateTable(self.identity)

        self._modules = []
        self.__parent = weakref.ref(parent)

        self._configure(config)
        self._addModules(config)
        self._initialize()
        self._initialized = True
        
        
    def _configure(self, config):
        """ 
        Perform configuration of the Manager. This should be overridden in
        derived classes. But be sure to call its parent's _configure() method
        too. Otherwise, self.syncTime will be set to 300. """
        try:
            self.syncTime = config['sync_interval']
        except ValueError:
            raise Exception("sync_interval must be integral")
    

    def _addModules(self, config):
        """ Dynamically import the modules specified in modules.ini. This
        should not be overridden. """
        base = config['base']
        
        # loop through modules
        for k,v in config.items():
            if isinstance(v, dict):
                cfg = v
                perm = toTypeOrNone(v['permission'], str)
                priority = v['priority']
                clanOnly = v['clan_only']
                
                # import class
                try:
                    ModuleClass = easyImportClass(base, v['type'])
                except ImportError:
                    raise FatalError("Error importing module/class {0} "
                                     "from base {1}. Either the module does "
                                     "not exist, or there was an error. To "
                                     "check for errors, use the command line "
                                     "'python -m {1}.{0}'; the actual path "
                                     "may vary."
                                     .format(v['type'], base))
                
                self._modules.append(ModuleEntry(
                        ModuleClass, priority, perm, clanOnly, self, k, cfg))
                
        # sort by decreasing priority
        self._modules.sort(key=lambda x: -x.priority) 
        self._log.info("---- {} creating module instances... ----"
                 .format(self.identity))
        for m in self._modules:
            self._log.info("Creating {0.className} with priority "
                           "{0.priority}, permission {0.permission}."
                           .format(m))
            try:
                m.createInstance()
            except TypeError as e:
                self._log.exception("Error!")
                raise FatalError("Error instantiating class {}: {}"
                                 .format(m.className, e.args[0]))

        self._log.info("---- All modules created. ----")


    def _initialize(self):
        """ Runs after _addModules. If there is additional initialization
        to do, you should override this, but be sure to call the parent's
        _initialize() method to properly initialize the modules. """
        self._log.debug("Initializing...")
        d = self._processorInitData()
        self._log.debug("Loaded initialization data.")
        with self._syncLock:
            self._log.debug("Checking persistent state...")
            try:
                if len(self._persist) == 0:
                    self._persist['__init__'] = ""
            except ValueError:
                self._clearPersist()
            self._log.debug("Preparing to initialize modules...")
            self._initializeModules(d)
            self._log.debug("Performing initial state sync...")
            self._syncState(force=True)
            
            
    def _processorInitData(self):
        """ This is the initialization data that is passed when initializing
        each module. """
        return {}
                
    
    def _initializeModules(self, initData):
        """(Re)initialize processors. If persistent state is present, it is
        loaded and passed to the module's initialize() method; if absent, the
        module's initialState property is used instead. If an error occurs,
        the initialState is used as well and the old state is deleted.
        """
        hbSys = self.heartbeatSubsystem
        with self._syncLock:
            for m in self._modules:
                mod = m.module
                self._log.info("Initializing {} ({})."
                                .format(mod.id, mod.__class__.__name__))
                success = False
                if mod.id in self._persist:
                    try:
                        state = self._persist[mod.id]
                        if state is None:
                            self._log.info("Null state for module {}, using "
                                           "default...".format(mod.id))
                            state = mod.initialState
                        self._log.debug("Initializing module {} ({}) with "
                                        "state {}".format(
                                            mod.id, mod.__class__.__name__, 
                                            state))
                        mod.initialize(state, initData)
                        success = True
                    except (KeyboardInterrupt, SystemExit, SyntaxError):
                        raise
                    except Exception:
                        self._log.exception("ERROR initializing module "
                                            "with persistent state")
                        self._log.error("Reverting to unknown state...")
                if not success:
                    self._log.info("No state detected for module {0.id} "
                                   "({0.__class__.__name__}); using default "
                                   "state {0.initialState}".format(mod))
                    mod.initialize(mod.initialState, initData)
                mod.heartbeatRegister(hbSys)
            self._log.info("---- Finished initializing modules ----")


    def _clearPersist(self):
        """ Remove all persistent state data. Note that states are
        periodically synced, so if you don't also reset each module, this will
        essentially do nothing. """
        with self._syncLock:
            self._db.updateStateTable(self.identity, {}, purge=True)
            self._persist = self._db.loadStateTable(self.identity)
            
    
    def _syncState(self, force=False):
        ''' Store persistent data for Modules in the database. '''
        with self._syncLock:
            if self._persist is None:
                return
            for m in self._modules:
                mod = m.module
                self._persist[mod.id] = mod.state
            if time.time() - self._lastSync > self.syncTime or force:
                self._log.debug("Syncing state for {}".format(self.identity))
                try:
                    self._db.updateStateTable(self.identity, self._persist)
                except Exception as e:
                    for k,v in self._persist.items():
                        try:
                            encode([k,v]) # check if JSON error
                        except:
                            raise ValueError("Error encoding state {} for "
                                             "module {}: {}"
                                             .format(v, k, e.args))
                    raise
                self._lastSync = time.time()
                    
                    
    def checkClan(self, uid):
        """ Check if a user is in the same clan as the bot or if they are on
        the whitelist. Returns {} if user is not in clan. Otherwise returns
        the user record, a dict with keys 'userId', 'userName', 'karma', 
        'rankName', 'whitelist', and 'inClan'. Note that 'karma' will be zero
        if the user is whitelisted and outside the clan (which will be
        indicated by the 'inClan' field equal to False). """
        if uid <= 0:
            return {'inClan': True, 'userId': uid, 'rankName': 'SPECIAL',
                    'userName': str(uid), 'karma': 1, 'whitelist': False}
        info = self.director.clanMemberInfo(uid)
        return info


    def cleanup(self):
        """ run cleanup operations before bot shutdown. This MUST be called
        before shutting down by the CommunicationDirector. """
        with self._syncLock:
            self._log.info("Cleaning up manager {}...".format(self.identity))
            self._log.debug("Cleanup: syncing states...")
            self._syncState(force=True)
            self._initialized = False
            self._persist = None
        for m in reversed(self._modules):
            mod = m.module
            self._log.debug("Cleanup: unregistering heartbeat for {}..."
                           .format(mod.id))
            mod.heartbeatUnregister()
            self._log.debug("Cleanup: unregistering events for {}..."
                           .format(mod.id))
            mod.eventUnregister()
            self._log.debug("Cleanup: cleaning up module {}...".format(mod.id))
            mod.cleanup()
        self._log.debug("Unregistering heartbeat...")
        self.heartbeatUnregister()
        self._log.debug("Unregistering events...")
        self.eventUnregister()
        self._log.info("Done cleaning up manager {}".format(self.identity))
        self._modules = None
        self._log.info("----- Manager shut down. -----\n")
    
    
    @property    
    def director(self):
        """ Get a reference to the CommunicationDirector. """
        parent = self.__parent()
        if parent is not None:
            return parent
        return None
    
        
    @property    
    def session(self):
        """ Get the current session (for pyKol requests). """
        return self._s
        
    
    @property
    def properties(self):
        """ Get the current RunProperties (load various information) """
        return self._props
        
    
    @property
    def inventoryManager(self):
        """ Get the current InventoryManager """
        return self._invMan
    
    
    @property
    def chatManager(self):
        return self._c
        
    
    def defaultChannel(self):
        """ Get the default chat channel for this manager. May be overridden
        in derived classes. If no channel is specified in sendChatMessage(),
        self.defaultChannel is used. By default, this uses the current
        chat channel (i.e., not the "listened" channels, the main one). """
        return self.chatManager.currentChannel
    
    
    def sendChatMessage(self, 
                        text, channel=None, waitForReply=False, raw=False):
        """ Send a chat message with specified text. If no channel is
        specified, self.defaultChannel is used. If waitForReply is true, the
        chatManager will block until response data is loaded; otherwise, the
        chat is sent asynchronously and no response is available. If raw is
        true, the chat is sent undecorated; if false, the chat is sanitized
        to avoid /command injections and is decorated in emote format. """
        if channel is None:
            channel = self.defaultChannel()
        if channel is None or channel == "DEFAULT":
            channel = self.chatManager.currentChannel
            
        useEmote = not raw
        return self.director.sendChat(channel, text, waitForReply, useEmote)
    
    
    def whisper(self, uid, text, waitForReply=False):
        """ Send a private message to the specified user. """
        return self.director.whisper(uid, text, waitForReply)
    
    def sendKmail(self, message):
        """ Send a Kmail that is not a reply. message should be a Kmail object
        from the common.kmailContainer package. """
        self.director.sendKmail(message)
    
    def parseChat(self, msg, checkNum):
        """ This function is called by the CommunicationDirector every time
        a new chat is received. The manager can choose to ignore the chat or
        to process it. To ignore the chat, just return []. To process it, pass
        the chat to each module and return a LIST of all the replies that 
        are not None. """
        return []
    
    def parseKmail(self, msg):
        """ Parse Kmail and return any replies in a LIST of KmailResponses
        in the same fashion as the parseChat method. """
        return []
    
    
    def kmailFailed(self, module, message, exception):
        """ This is called by the CommunicationDirector if a kmail fails 
        to send for some reason. """
        if module is not None:
            module.extendedCall('message_send_failed', message, exception)
    
    
    def _heartbeat(self):
        """ By default, the heartbeat calls syncState(), so in derived classes
        be sure to do that too or call the parent _heartbeat(). """
        if self._initialized:
            self._syncState()
