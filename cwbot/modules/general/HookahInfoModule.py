from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.kolextra.request.GetDisplayCaseRequest import GetDisplayCaseRequest


class HookahInfoModule(BaseChatModule):
    """ 
    A module that provides information about the HookahKmailModule in chat.
    
    Configuration options:
    save_last - integer number of hookah part sets to keep from being
                sent out [default = 1]
    """
    requiredCapabilities = ['chat', 'inventory']
    _name = "hookah_info"
    
    def __init__(self, manager, identity, config):
        self._saveLast = True
        super(HookahInfoModule, self).__init__(manager, identity, config)


    def _configure(self, config):
        try:
            self._saveLast = int(config.setdefault('save_last', 1))
        except ValueError:
            raise Exception("(HookahInfoModule) Config option "
                            "save_last must be integral") 


    def _processCommand(self, unused_message, cmd, args):
        if cmd == "hookah":
            r = GetDisplayCaseRequest(self.session)
            inventory = self.tryRequest(r)['items']
            
            # get list of quantities
            hookahItems = [4510,4511,4515,4516,4512,4513] 
            itemDict = dict((it['id'], it['quantity']) for it in inventory 
                             if it['id'] in hookahItems)
            itemQty = [itemDict.get(iid, 0) for iid in hookahItems]
            
            # deduct one for save last option
            if self._saveLast:
                itemQty = [max(i-1,0) for i in itemQty]
            if len(args) >= 5 and args[:5].lower() == 'stock':
                return ("Hookah stock: {} Walrus Ice Cream (SC), "
                        "{} Beautiful Soup (TT), {} Lobster qua Grill (DB), "
                        "{} Missing Wine (AT), {} Eggman Noodles (PM), "
                        "{} Vial of jus de larmes (S)".format(*itemQty))
            else:
                return ("Send me some hookah items, and I will send you "
                        "back a full set! Send me a kmail with the text "
                        "'hookah' for details. I have enough stock for {} "
                        " hookahs.".format(min(itemQty)))
        return None
        
        
    def _availableCommands(self):
        return {'hookah': "!hookah: Show information about the hookah program."
                          " '!hookah stock' shows detailed stock info."}

