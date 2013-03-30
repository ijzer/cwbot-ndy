from cwbot.sys.eventSubsystem import EventSubsystem
from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem
from cwbot.modules.test.MockHeartbeatSubsystem import MockHeartbeatSubsystem
import threading
import logging

class MockProps(object):
    def addProp(self, name, val):
        setattr(self, name, val)

class MockInventory(object):
    def __init__(self):
        self._items = {}
    
    def setItemQty(self, iid, qty):
        self._items[iid] = qty
        if qty == 0:
            del self._items[iid]
        
    def refreshInventory(self):
        pass
    
class MockSession(object):
    isConnected = True
    serverURL = "server/"
    
    
class MockSystem(EventSubsystem.EventCapable):
    def __init__(self, evSys):
        super(MockSystem, self).__init__(name="sys.system",
                                         identity="system",
                                         evSys=evSys)
    
    def raiseSystemEvent(self, subject, receiver=None, data={}, **kwargs):
        return self._raiseEvent(subject, receiver, data)
    
    def _eventCallback(self, eData):
        if eData.to is not None:
            self._raiseEvent("EventToSystem", "mockmanager", eData)


class MockChatManager(EventSubsystem.EventCapable,
                      HeartbeatSubsystem.HeartbeatCapable):
    capabilities = ['chat', 'kmail', 'inventory', 'admin']

    def __init__(self, heartbeatTime=5):
        self._log = logging.getLogger("mockmanager")
        self._log.propagate = False
        self._log.handlers = []
        self._log.setLevel(logging.CRITICAL)
        self._hbStop = threading.Event()
        self._hb = threading.Event()
        hbSys = MockHeartbeatSubsystem()
        evSys = EventSubsystem()
        super(MockChatManager, self).__init__(name="mockmanager", 
                                              identity="mockmanager", 
                                              evSys=evSys,
                                              hbSys=hbSys)
        self.identity = "mockmanager"
        self._modules = []
        self._properties = MockProps()
        self._items = MockInventory() 
        self.operations = []
        self._opReturns = {}
        self._system = MockSystem(evSys)
        
    def cleanup(self):
        for mod in reversed(self._modules):
            mod.heartbeatUnregister()
            mod.eventUnregister()
            mod.cleanup()
        self._hbStop.set()
        self.heartbeatSubsystem.join()
        self.heartbeatUnregister()
        self.eventUnregister()
        self._modules = None

    def raiseEvent(self, subject, receiver=None, data={}, **kwargs):
        return self._raiseEvent(subject, receiver, data)
    
    def raiseSystemEvent(self, subject, receiver=None, data={}, **kwargs):
        return self._system.raiseSystemEvent(subject, receiver, data)
    
    def addModule(self, module, state={}, initData={}):
        module.initialize(state, initData)
        self._modules.append(module)
        module.heartbeatRegister(self.heartbeatSubsystem)
    
    def setProperty(self, pname, pval):
        self._properties.addProp(pname, pval)

    def setItemQty(self, iid, qty):
        self._items.setItemQty(iid, qty)
        
    def setOpReturn(self, opNumber, returnVal):
        self._opReturns[opNumber] = returnVal
        
    def getState(self, module):
        return module.state
        
    def _addOp(self, op):
        self.operations.append(op)
        n = len(self.operations)
        return self._opReturns.get(n-1, None)
    
    def processCommand(self, message, commandText, commandArgs):
        replies = []
        for mod in self._modules:
            r = mod.extendedCall('process_command', message, 
                                 commandText, commandArgs)
            if r is not None:
                replies.append(r)
        return replies
    
    def waitForHeartbeat(self, n=1):
        for _i in range(n):
            self.heartbeatSubsystem.pulse()
    
#############################################################################
# Modules use functions below
#############################################################################
    
    @property    
    def session(self):
        return MockSession()
    
    @property
    def properties(self):
        return self._properties
        
    
    @property
    def inventoryManager(self):
        return self._items

    def sendChatMessage(self, 
                        text, channel=None, waitForReply=False, raw=False):
        return self._addOp({'type': 'chat', 'channel':channel, 
                            'wait':waitForReply, 'raw':raw, 'text': text})
    
    def whisper(self, uid, text, waitForReply=False):
        return self._addOp({'type': 'whisper', 'userId':uid, 
                            'wait':waitForReply, 'text':text})
    
    def sendKmail(self, message):
        return self._addOp({'type': 'kmail', 'message': message})

    def kmailFailed(self, module, message, exception):
        module.extendedCall('message_send_failed', message, exception)
        
    def _eventCallback(self, eData):
        if ((eData.fromIdentity == "__system__" and eData.to is None) or 
                eData.fromName == "mockmanager"):
            return
        data = self._addOp({'type': 'event', 'event': eData})
        if data is not None:
            self._eventReply(data)

