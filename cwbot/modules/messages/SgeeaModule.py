from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock 


class SgeeaModule(BaseKmailModule):
    """ 
    A module that handles donation kmails of SGEEAs.
    
    No configuration options.
    """
    requiredCapabilities = ['kmail']
    _name = "sgeea"

    def __init__(self, manager, identity, config):
        super(SgeeaModule, self).__init__(manager, identity, config)

    def _processKmail(self, message):
        items = message.items
        uid = message.uid
        text = message.text
        count = items.get(588, 0)
        if count == 0:
            return None
            
        with InventoryLock.lock:
            del items[588]
            if len(items) == 0 or "donate" in text.lower():
                return self.newMessage(uid, "Thank you for your donation!")
        
            m = self.newMessage(uid, "Thank you for your donation!\n\n"
                                     "(Also, you sent me some other stuff. "
                                     "I'm not sure what to do with it.)")
            m.addItems(items)
            return m
