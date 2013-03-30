import re
from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.modules.messages.HookahKmailModule import BaseHookahModule
from cwbot.locks import InventoryLock
from cwbot.common.kmailContainer import Kmail


class HookahOverrideModule(BaseHookahModule, BaseChatModule):
    """ 
    A module that allows an admin to manually send a set of hookah parts
    to a player. It is highly recommended that this module be protected
    with a permission.
    
    Configuration options:
    save_last - same as in HookahInfoModule [default = 1]
    """
    requiredCapabilities = ['chat', 'inventory', 'admin']
    _name = "hookah_override"
    
    def __init__(self, manager, identity, config):
        self._saveLast = True
        super(HookahOverrideModule, self).__init__(manager, identity, config)
        
        
    def _configure(self, config):
        try:
            self._saveLast = int(config.setdefault('save_last', 1))
        except ValueError:
            raise Exception("(HookahOverrideModule) Config options n and "
                            "save_last must be integral") 


    def sendHookah(self, uid):
        """ Send a set of hookah parts to a user """
        with InventoryLock.lock:
            oos = self.outOfStock(self._saveLast)
            if len(oos) > 0:
                print(str(oos))
                return "Not enough hookah parts."
            self.removeHookahFromDisplay(0)
            hookahItems = [4510,4511,4515,4516,4512,4513]
            items = dict((iid, 1) for iid in hookahItems)
            k = Kmail(uid=uid, 
                      text="Hookah override. DO NOT FORGET TO COOK THE "
                           "NOODLES AND VIAL.\n\nSeriously, don't forget.")
            k.addItems(items)
            self.sendKmail(k)
            return "Hookah sent to >>{}".format(uid)


    def _processCommand(self, message, cmd, args):
        if cmd == "hookah_override":
            m = re.search(r'^(\d+)', args)
            if m is None:
                return "No userId detected."
            try:
                uid = int(m.group(1))
                return self.sendHookah(uid)
            except Exception as e:
                return "An error occurred. {}".format(e)
        return None


    def _availableCommands(self):
        return {"hookah_override": "!hookah_override: send a hookah to a user."
                                   " Usage: '!hookah_override playerIdNumber'"}

