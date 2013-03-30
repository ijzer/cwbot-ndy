import re
import time
import threading
from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.kolextra.request.ShruggableEffectRequest import \
                                                ShruggableEffectRequest
from cwbot.kolextra.request.EffectRequest import EffectRequest
from cwbot.kolextra.request.ShrugEffectRequest import ShrugEffectRequest
from cwbot.kolextra.request.UneffectRequest import UneffectRequest


class UneffectModule(BaseChatModule):
    """ 
    A module that players can use to uneffect chat effects. Since this could
    be used for abuse, it might be wise to restrict this to clan members. When
    !uneffect is called, ALL shruggable effects are removed as well.

    The module also automatically removes certain effects.
    
    Configuration options:

    auto_remove: comma-separated list of effect id numbers that should be
                 automatically removed [default = 697] (697=Bruised Jaw)
    """
    requiredCapabilities = ['chat', 'inventory']
    _name = "uneffect"

    def __init__(self, manager, identity, config):
        self._autoRemove = []
        self._lastAutoRemove = 0
        self._autoRemoveInterval = 120
        self._newMessage = threading.Event()
        self._lock = threading.RLock()
        super(UneffectModule, self).__init__(manager, identity, config)
        
        
    def _configure(self, config):
        autoRemove = config.get('auto_remove', '697').split(',')
        for item in autoRemove:
            try:
                self._autoRemove.append(str(int(item)))
            except ValueError:
                pass  
        config['auto_remove'] = ', '.join(self._autoRemove)
        

    def _processCommand(self, message, cmd, args):
        if cmd == "uneffect":
            with self._lock:
                self.shrug() # shrug all shruggable effects
                m = re.search(r'^(\d+)', args)
                if m is None:
                    effects = self.effectList() 
                    if effects is None:
                        return ("I am out of SGEEAs. "
                                "Please help and send me a few!")
                    eids = effects.keys()
                    eids.sort()
                    s = "Current effects: "
                    strings = [("{}={}".format(eid, effects[eid]))
                               for eid in eids] 
                    if not strings:
                        strings = ["none"]
                    return s + ", ".join(strings)
                return self.uneffect(m.group(1))
        return None

    
    def shrug(self):
        r1 = ShruggableEffectRequest(self.session)
        d1 = self.tryRequest(r1, nothrow=True, numTries=2)
        self.log("Shrugging effects: {}".format(d1['effects']))
        for eid in d1['effects']:
            r2 = ShrugEffectRequest(self.session, eid)
            self.tryRequest(r2, nothrow=True, numTries=1)

    
    def effectList(self):
        r1 = EffectRequest(self.session)
        d1 = self.tryRequest(r1)
        if d1['out']:
            self.log("Out of SGEEAs.")
            return None
        eff = d1['effects']
        self.debugLog("Detected effects: {}".format(eff))
        return eff
    

    def uneffect(self, eid):
        r = UneffectRequest(self.session, eid)
        d = self.tryRequest(r)
        self.log("Uneffect {} result: {}".format(eid, d['result']))
        self.inventoryManager.refreshInventory()
        n = self.inventoryManager.inventory().get(588, 0)
        return d['result'] + " {} SGEEAs remaining.".format(n)


    def _availableCommands(self):
        return {'uneffect': "!uneffect: Use '!uneffect EFFECT_ID' to remove "
                            "an existing effect from the bot. '!uneffect' "
                            "will list active effects."}


    def _eventCallback(self, eData):
        if eData.subject == "unknown_chat" and eData.fromName == "sys.comms":
            self._newMessage.set()


    def _heartbeat(self):
        # let's check for autoremove effects
        if (time.time() - self._lastAutoRemove > self._autoRemoveInterval or 
                self._newMessage.is_set()):
            self._newMessage.clear()
            with self._lock:
                effects = self.effectList()
                if effects is None:
                    return
                
                for eff in effects:
                    if eff in self._autoRemove:
                        self.uneffect(eff)
                
                self._lastAutoRemove = time.time()
                
