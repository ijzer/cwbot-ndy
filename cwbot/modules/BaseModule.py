import abc
import weakref
import logging
from cwbot.sys.eventSubsystem import EventSubsystem
from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem
from cwbot.util.tryRequest import tryRequest


class ProcessorException(Exception):
    pass


class ModuleMetaClass(abc.ABCMeta):
    def __init__(cls, name, bases, attrs): #@NoSelf
        if 'requiredCapabilities' not in attrs:
            raise NotImplementedError(
                    "The '{}' class does not implement a "
                    "'requiredCapabilities' attribute".format(name))
        if '_name' not in attrs:
            raise NotImplementedError(
                    "The '{}' class does not implement a '_name' attribute"
                    .format(name))
        super(ModuleMetaClass, cls).__init__(name, bases, attrs)


class BaseModule(EventSubsystem.EventCapable,
                 HeartbeatSubsystem.HeartbeatCapable):
    """The parent class of every Module. All child classes MUST implement
    the requiredCapabilities attribute, which contains a list of capabilities
    that are required of the module's parent manager, and the _name attribute,
    which is a unique identifier for the class. """
    __metaclass__ = ModuleMetaClass
    # construction will require the manager that invokes this object to 
    # have all capabilities in this list
    requiredCapabilities = []
    # other calling methods
    _name = ""
    
    
    def __init__(self, manager, identity, config):
        """ Initialize the BaseModule. When BaseModule.__init__ is called,
        the following occurs:
        
        1. The event subsystem (but NOT the heartbeat subsystem) is linked.
        2. _configure() is called.
        
        After all modules are constructed, the manager performs the following:
        
        3. the manager calls initialize()
        4. the manager links the heartbeat subsystem to the module.
        """
        super(BaseModule, self).__init__(name=self._name, 
                                         identity=identity,
                                         evSys=manager.eventSubsystem)
        self._log = logging.getLogger("{}.{}".format(manager.identity, 
                                                     identity))
        self.__parent = weakref.ref(manager)
        self.__callDict = {}
        self._configure(config)
        self.id = identity
        reqCapabilities = type(self).requiredCapabilities
        for errCap in (item for item in reqCapabilities 
                       if item not in manager.capabilities):
            raise ProcessorException("Module {} requires capability {}."
                                     .format(type(self), errCap))


    # startup-related functions and persistent state

    def _configure(self, config):
        ''' 
        Run at startup to initialize from configuration file.
        If required options are not in the config dictionary, 
        please use defaults and ADD THEM TO THE DICTIONARY.
        This is done preferably by using 
        value = config.setdefault("key", "default")
        '''
        pass

    
    def initialize(self, lastKnownState, initData):
        ''' 
        run at startup, after _configure but before processing anything. 
        Initialized with any persistent state information. The manager
        determines whether to use initialState or its stored state for
        lastKnownState. initData varies by the manager as well.
        '''
        self.debugLog("Empty initialization.")


    @property
    def state(self):
        """ Return state of object. This state is used for reinitialization. 
        If the module has no peristent state, do not override. Otherwise,
        you must return the module's state information in a dictionary whose
        entries are all in JSON-serializable format (http://www.json.org/)
        """
        return {}


    @property
    def initialState(self):
        """
        This should return the known initial state of the module. 
        If state information is unavailable, or 
        the state needs to be reset for some reason 
        (e.g., a new Hobopolis instance for Hobo Modules), it
        will be initialized with this state. Like the state property, this
        information should be JSON-serializable.
        """
        return {}


    def reset(self, initData):
        """
        Reset the state of the module. This function is not usually called.
        The major exception is for the HoboChannelManager, which calls this 
        function when the dungeon is reset. By default, this just calls 
        self.initialize(self.initialState, initData). If this behavior is
        undesirable, you should override this.
        """
        self.initialize(self.initialState, initData)


    # property getters

    @property
    def name(self):
        return self._name
 
    @property
    def parent(self):
        parent = self.__parent()
        if parent is not None:
            return parent

    @property
    def session(self):
        """Get the session"""
        return self.parent.session
    
    @property
    def properties(self):
        """Get the runproperties"""
        return self.parent.properties

    @property
    def inventoryManager(self):
        """Get the inventory manager"""
        return self.parent.inventoryManager


    # logging
    
    def log(self, txt):
        """Write something to the log with level INFO"""
        self._log.info(txt)
        
    
    def debugLog(self, txt):
        """Write something to the log with level DEBUG"""
        self._log.debug(txt)
        
    
    def errorLog(self, txt):
        """Write something to the log with level ERROR"""
        self._log.error(txt)

   
    # chat/kmail-related     
    
    def chat(self, text, channel=None, waitForReply=False, raw=False):
        """ Post something in chat (posts according to parent manager's 
        configuration)
        """
        return self.parent.sendChatMessage(text, channel, waitForReply, raw)

    
    def whisper(self, uid, text, waitForReply=False):
        """Send a private message"""
        self.parent.whisper(uid, text, waitForReply)


    def sendKmail(self, kmail):
        """ Note: if this is a response to another kmail, you should
        instead use a BaseKmailModule and use the processKmail method. 
        This is coordinated with the MailHandler to ensure that messages are
        not double-sent. It's especially important if you're sending items. """
        self.parent.sendKmail(kmail)
        
    def tryRequest(self, request, *args, **kwargs):
        """ Use this to perform KoL requests from PyKol. Do not use
        tryRequest() or request.doRequest() directly; running requests through
        this function allows easier unit testing. """
        return tryRequest(request, *args, **kwargs)
    
    # other
    
    def cleanup(self):
        """Executed before closing KoL session"""
        pass

    
    # do not override any of the following in leaf classes
    
    def __empty(self, *args, **kwargs):
        return None
    
    
    def extendedCall(self, command, *args, **kwargs):
        """ 
        This function is used for extended functionality in other modules.
        Return None if nothing is done with the call. Otherwise, functions
        should return some sort of value if they did something.
        """
        return self.__callDict.get(command, self.__empty)(*args, **kwargs)
    
    
    def _registerExtendedCall(self, command, func):
        """ Use this function to register an extended call. """
        self.__callDict[command] = func
