import time
import threading
from cwbot.modules.BaseModule import BaseModule


class ShutdownModule(BaseModule):
    """ 
    A module that triggers bot shutdown after detecting a chat message
    about rollover.
    
    Configuration options:
    shutdown_time - amount of time, in minutes, before rollover that
                    the bot should shut down [default = 3]
    """
    requiredCapabilities = []
    _name = "shutdown"

    def __init__(self, manager, identity, config):
        self._engaged = threading.Event()
        self._time, self._shutdownTime = None, None
        self._lock = threading.RLock()
        super(ShutdownModule, self).__init__(manager, identity, config)


    def _configure(self, config):
        self._time = int(config.setdefault('shutdown_time', 3))

                
    def _eventCallback(self, eData):
        if eData.subject == "rollover" and eData.fromName == "sys.comms":
            with self._lock:
                t = eData.data['time']
                self.log("Rollover detected in {} minutes.".format(t))
                self._shutdownTime = (
                        time.time() + 60 * (t - self._time) - 1)
                self._engaged.set()
            
            
    def _heartbeat(self):
        if self._engaged.is_set():
            with self._lock:
                if time.time() >= self._shutdownTime:
                    self._raiseEvent("LOGOUT", "__system__")
                    self._engaged.clear()

