from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock
from kol.request.CursePlayerRequest import CursePlayerRequest 
import kol.Error


class SmoreModule(BaseKmailModule):
    """ 
    A module that sends smores if you send marshmallows.
    """
    
    requiredCapabilities = ['kmail', 'inventory']
    _name = "smores"
    
    def __init__(self, manager, identity, config):
        super(SmoreModule, self).__init__(manager, identity, config)
        
        
    def _processKmail(self, message):
        mallows = message.items.get(3128, 0)
        if mallows == 0:
            return None
        with InventoryLock.lock:
            self.inventoryManager.refreshInventory()
            cinv = self.inventoryManager.completeInventory()
            inv = self.inventoryManager.inventory()
            gun = cinv.get(5066, 0)
            if gun == 0:
                return (self.newMessage(message.uid,
                                        "Sorry, I don't have a s'more gun. "
                                        "Somebody needs to donate one, or you "
                                        "can send one along with your "
                                        "marshmallows.", message.meat)
                                       .addItems(message.items))
            self.inventoryManager.refreshInventory()
            mallowsBefore = inv.get(3128, 0)
            print mallowsBefore
            try:
                for _ in range(min(mallows, 40)):
                    r = CursePlayerRequest(self.session, message.uid, 5066)
                    self.tryRequest(r, numTries=1)
            except kol.Error.Error:
                pass
            self.inventoryManager.refreshInventory()
            mallowsAfter = self.inventoryManager.inventory().get(3128, 0)
            print mallowsAfter
            mallowsSent = mallowsBefore - mallowsAfter
            
            returnItems = message.items
            
            if mallowsSent == mallows:
                del returnItems[3128]
            else:
                returnItems[3128] -= mallowsSent
                returnItems[3128] = min(returnItems[3128], mallowsAfter)
            print returnItems
            
            sendStuffBack = returnItems or message.meat > 0
            
            if not sendStuffBack:
                return self.newMessage(-1)
            elif 3128 in returnItems:
                return self.newMessage(message.uid, 
                                       "There was an error sending you all "
                                       "of your smores (are you in "
                                       "Ronin/Hardcore? Did you request too "
                                       "many?). You can have your "
                                       "marshmallows back.",
                                       message.meat).addItems(returnItems)
            else:
                return self.newMessage(message.uid, 
                                       "Enjoy your smores!\n\n(Also, you sent "
                                       "me some other stuff. You can have it "
                                       "back.)", 
                                       message.meat).addItems(returnItems)


    def _kmailDescription(self):
        return ("If you send me marshmallows, I will shoot them back with "
                "my s'more gun so you can enjoy some ooey-gooey s'mores!")
        