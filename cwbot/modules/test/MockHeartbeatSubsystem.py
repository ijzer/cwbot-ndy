from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem


class MockHeartbeatSubsystem(object):
    """ The class that handles the heartbeat (simple threading) subsystem.
    
    To use the heartbeat subsystem in your class, derive from 
    HeartbeatSubsystem.HeartbeatCapable. See full documentation in that class.
    """
    
    _HeartbeatObject = HeartbeatSubsystem._HeartbeatObject
    
    def __init__(self, *args, **kwargs):
        self._objs = []
        
    
    @property
    def exception(self):
        return False
    
    def registerObject(self, obj, callback):
        self._objs.append((object, callback))
        
    def unregisterObject(self, obj):
        self._objs = [(o,c) for o,c in self._objs if o is not obj]
    
    def raiseException(self):
        raise Exception("Tried to get heartbeat exception, but there "
                        "is none.")
        
    def join(self):
        pass
    
    def pulse(self):
        for _o,c in self._objs:
            c()