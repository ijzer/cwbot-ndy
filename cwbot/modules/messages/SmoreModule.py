from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock
from kol.request.CursePlayerRequest import CursePlayerRequest 
import kol.Error


class SmoreModule(BaseKmailModule):
    """ 
    A module that sends smores if you send marshmallows. It also does time's arrows. And rubber spiders.
    """
    
    requiredCapabilities = ['kmail', 'inventory']
    _name = "smores"
    
    def __init__(self, manager, identity, config):
        super(SmoreModule, self).__init__(manager, identity, config)
        
        
    def _processKmail(self, message):
        r = self._doMallows(message)
        if r is not None:
            return r
        r = self._doArrow(message)
        if r is not None:
            return r
        r = self._doSpider(message)
        if r is not None:
            return r

        return None


    def _doArrow(self, message):
        arrows = message.items.get(4939, 0)
        if arrows == 0:
            return None
        if arrows >= 2:
            return (self.newMessage(message.uid,
                                    "Please do not send more than one time's arrow.",
                                    message.meat)
                                    .addItems(message.items))
        try:
            r = CursePlayerRequest(self.session, message.uid, 4939)
            self.tryRequest(r, numTries=1)
            return self.newMessage(-1)
        except kol.Error.Error as e:
            if e.code == kol.Error.USER_IN_HARDCORE_RONIN:
                return (self.newMessage(message.uid,
                                        "You are in hardcore or ronin.",
                                        message.meat)
                                        .addItems(message.items))
            if e.code == kol.Error.ALREADY_COMPLETED:
                return (self.newMessage(message.uid,
                                        "You have already been arrow'd today.",
                                        message.meat)
                                        .addItems(message.items))
            return (self.newMessage(message.uid,
                                    "Unknown error: {}".format(e.msg),
                                    message.meat)
                                    .addItems(message.items))

    def _doSpider(self, message):
        spiders = message.items.get(7698, 0)
        if spiders == 0:
            return None
        if spiders >= 2:
            return (self.newMessage(message.uid,
                                    "Please do not send more than one rubber spider.",
                                    message.meat)
                                    .addItems(message.items))
        try:
            r = CursePlayerRequest(self.session, message.uid, 7698)
            self.tryRequest(r, numTries=1)
            return self.newMessage(-1)
        except kol.Error.Error as e:
            if e.code == kol.Error.USER_IN_HARDCORE_RONIN:
                return (self.newMessage(message.uid,
                                        "You are in hardcore or ronin.",
                                        message.meat)
                                        .addItems(message.items))
            if e.code == kol.Error.ALREADY_COMPLETED:
                return (self.newMessage(message.uid,
                                        "You have already been spidered today.",
                                        message.meat)
                                        .addItems(message.items))
            return (self.newMessage(message.uid,
                                    "Unknown error: {}".format(e.msg),
                                    message.meat)
                                    .addItems(message.items))


    def _doMallows(self, message):
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
        return ("SMORES AND ARROWS AND SPIDERS: If you send me marshmallows "
                "or a time's arrow, I will shoot them back so you can enjoy "
                "some ooey-gooey s'mores or some extra adventures!")
        
