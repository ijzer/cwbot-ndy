import time
import logging
import copy
import sys
import cwbot.util.DebugThreading as threading
from configObj.configobj import ConfigObj, ParseError, flatten_errors
from configObj.validate import Validator
from StringIO import StringIO
import kol.Error
from cwbot.sys.CommunicationDirector import CommunicationDirector
from cwbot.common.moduleSpec import MODULE_SPEC
from cwbot.common.exceptions import ManualRestartException, ManualException, \
                                    RolloverException, FatalError
from cwbot.sys.eventSubsystem import EventSubsystem
from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem
from cwbot.common.InitData import InitData
from kol.request.StatusRequest import StatusRequest
from kol.request.UserProfileRequest import UserProfileRequest
from cwbot.util.tryRequest import tryRequest


def _quoteConfig(cfg):
    try:
        for k in cfg.keys():
            cfg[k] = _quoteConfig(cfg[k])
        return cfg
    except AttributeError:
        if isinstance(cfg, str):
            if "\"" in cfg or "'" in cfg:
                if ((cfg.startswith('"""') and cfg.endswith('"""')) or
                    (cfg.startswith("'''") and cfg.endswith("'''"))):
                    return cfg
                cfg = '"""' + cfg + '"""'
                return cfg
        return cfg
    

class BotSystem(EventSubsystem.EventCapable,
                          HeartbeatSubsystem.HeartbeatCapable):
    """ This is the "Main" class for the bot. Here, the subsystems are
    created and destroyed, and the configuration file is processed. 
    The method loop() is the main loop of the program.
    """
    def __init__(self, s, c, props, inv, configFile, db, exitEvent):
        """ Initialize the BotSystem """

        self._exitEvent = exitEvent

        self._initialized = False
        
        # trigger to stop heartbeat subsystem
        self._hbStop = threading.Event()
        
        # start subsystems
        try:
            oldTxt = None
            hbSys = HeartbeatSubsystem(5, 5, self._hbStop)
            evSys = EventSubsystem()
            
            # initialize subsystems
            super(BotSystem, self).__init__(
                    name="sys.system", identity="system", 
                    evSys=evSys, hbSys=hbSys)

            if exitEvent.is_set():
                sys.exit()

            # copy arguments
            self._s = s
            self._c = c
            self._props = props
            self._inv = inv
            self._db = db
            self._log = logging.getLogger()

            # initialize some RunProperties data now that we are logged on
            self._log.debug("Getting my userId...")
            r1 = StatusRequest(self._s)
            d1 = tryRequest(r1)
            self._props.userId = int(d1['playerid'])
            self._log.info("Getting my clan...")
            r2 = UserProfileRequest(self._s, self._props.userId)
            d2 = tryRequest(r2)
            self._props.clan = d2.get('clanId', -1)
            self._log.info("I am a member of clan #{} [{}]!"
                           .format(self._props.clan, 
                                   d2.get('clanName', "Not in any clan")))

            
            # config file stuff
            self._config = None
            self._overWriteConfig = False
            oldTxt = self._loadConfig(configFile)
            
            # listen to channels
            self._initializeChatChannels(self._config)
            c.getNewChatMessages() # discard old PM's and whatnot
            
            # initialize directors
            self._dir = None
            iData = InitData(s, c, props, inv, db)
            self._log.info("Starting communication system...")
            self._dir = CommunicationDirector(self, iData, 
                                              self._config['director'])
            self._lastCheckedChat = 0
            self._initialized = True
        except:
            self._hbStop.set()
            raise
        finally:
            # rewrite config file (values may be modified by modules/managers)
            if oldTxt is not None:
                self._saveConfig(configFile, oldTxt)
    
    
    def _loadConfig(self, configFile):
        """ Load ini file and parse some values from it """
        self._log.debug("Loading config file...")
        try:
            c = ConfigObj(
                    configFile, configspec=StringIO(MODULE_SPEC), 
                    list_values=False, raise_errors=True, create_empty=True)
            passed = c.validate(Validator(), copy=True, preserve_errors=True)
        except ParseError as e:
            raise FatalError("Parse error in modules.ini:{}: \"{}\""
                             .format(e.line_number, e.line))
        if passed != True:
            f = flatten_errors(c, passed)
            error1 = f[0]
            raise FatalError("Invalid module configuration. First error "
                             "found in section [{}], key \"{}\". Error: {}"
                             .format('/'.join(error1[0]), 
                                     error1[1], error1[2]))
        self._overWriteConfig = c['overwrite_config']
        self._config = c
        with open(configFile) as f:
            txt = f.read()
        self._saveConfig(configFile, txt)
        self._chatDelay = c['system']['communication_interval']
        self._log.debug("{} loaded.".format(configFile))
        return txt
        
        
    def _saveConfig(self, configFile, oldTxt):
        """ Write config to file """
        outTxt = StringIO()
        fixedConfig = _quoteConfig(copy.deepcopy(self._config))
        fixedConfig.write(outTxt)
        txt = outTxt.getvalue()
        if txt != oldTxt:
            filename = configFile + ("" if self._overWriteConfig else ".new") 
            self._log.debug("Config changed; writing to {}".format(filename))
            with open(filename, 'w') as f:
                fixedConfig.write(f)
                self._log.debug("Wrote new configuration to {}"
                                .format(filename))
    

    def _initializeChatChannels(self, config):
        """ Listen to appropriate chat channels """
        channels = map(str.strip, config['system']['channels'].split(','))
        mainChannel = channels[0]
        listenChannels = channels[1:]
        
        self._log.debug("Listening to chat channels: {}"
                        .format(', '.join(channels)))
        self._c.sendChatMessage(
                "/channel {}".format(mainChannel), waitForReply=True, 
                useEmoteFormat=False)
        self.listenChannel(listenChannels)
    
    
    def sendChatMessage(self, msg, waitForReply=False):
        return self._c.sendChatMessage(msg, waitForReply, True)


    def listenChannel(self, listenList):
        """ Listen to a list of channels. The first channel in the list
        is the "main" channel. """
        r = self._c.sendChatMessage("/listen", waitForReply=True);
        r1 = r[0]
        currentListen = set()
        currentChannel = ""
        if "currentChannel" in r1:
                currentChannel = r1["currentChannel"]
        if "otherChannels" in r1:
                currentListen.update(r1["otherChannels"])
                        
        for channelName in currentListen:
            if channelName not in listenList:
                # unlisten
                self._c.sendChatMessage("/listen " + channelName)
                        
        for channelName in listenList:
            if channelName not in currentListen:
                if channelName != currentChannel:
                    # listen
                    self._c.sendChatMessage("/listen " + channelName)

        
    def loop(self):
        """ The main loop of the CWbot program. """
        try:
            self._log.info("Entered main loop.")
            self._raiseEvent("startup", None)
            
            # this is the main loop. The only way out is to raise an exception.
            while True:
                # handle exit signals
                if self._exitEvent.is_set():
                    self._log.info("User interrupt detected, exiting...")
                    sys.exit()
                if self._props.connection is not None:
                    if self._props.connection.poll():
                        svcMessage = self._props.connection.recv()
                        if svcMessage == "stop":
                            self._log.info("Received stop signal from Win32 "
                                           "service manager, exiting...")
                            sys.exit()
                if not self._s.isConnected:
                    raise kol.Error.Error("Session unexpectedly closed.", 
                                          kol.Error.NOT_LOGGED_IN)
                if self.heartbeatSubsystem.exception:
                    self._log.error("Exception in heartbeat subsystem.")
                    self.heartbeatSubsystem.raiseException()

                # do work
                if time.time() - self._lastCheckedChat >= self._chatDelay:
                    self._lastCheckedChat = time.time()
                    self._dir.processNewCommunications()
                    
                time.sleep(0.05)

        except RolloverException:
            self._raiseEvent("shutdown", None)
            self._log.info("Shutting down for rollover...")
            return
        except ManualRestartException:
            self._raiseEvent("manual_restart", None)
            self._log.info("Manual restart invoked.")
            raise
        except (SystemExit, KeyboardInterrupt, ManualException) as e:
            self._raiseEvent("manual_stop", None)
            self._log.info("Encountered stop signal: {}."
                           .format(e.__class__.__name__))
            raise SystemExit
        except Exception as e:
            self._raiseEvent("crash", None, {'args': e.__class__.__name__})
            self._log.critical("Unknown error.")
            raise
        finally:
            self._cleanup()
            
            
    def _cleanup(self):
        self._log.info("******** Shutting down ********")
        self._hbStop.set()
        
        # shut down heartbeat subsystem
        try:
            self.heartbeatSubsystem.join()
            self.heartbeatUnregister()
        except Exception:
            self._log.exception("Error shutting down Heartbeat Subsystem.")
        
        # shut down director
        try:
            if self._dir is not None:
                self._log.info("Cleaning up director...")
                self._dir.cleanup()
            else:
                self._log.warn("No director to clean up!")
            self._dir = None
        except Exception:
            self._log.exception("Error shutting down Heartbeat Subsystem.")

        # shut down event subsystem
        try:
            self.eventUnregister()
        except Exception:
            self._log.exception("Error shutting down Heartbeat Subsystem.")

        self._log.info("Bot system shutdown complete.")


    def _eventCallback(self, eData):
        """ Handle system events """
        m = eData.subject.upper()
        if eData.to == "__system__":
            txt = eData.data.get('text', "Received {} signal".format(m))
            if m == "LOGOUT":
                raise RolloverException(txt)
            elif m == "STOP":
                raise ManualException(txt)
            elif m == "RESTART":
                raise ManualRestartException(txt)
        
        
    def __del__(self):
        self._hbStop.set()
