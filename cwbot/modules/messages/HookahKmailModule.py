from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.modules.BaseModule import BaseModule
from cwbot.common.exceptions import MessageError
from cwbot.kolextra.request.AddItemsToDisplayCaseRequest import \
                                            AddItemsToDisplayCaseRequest
from cwbot.kolextra.request.TakeItemsFromDisplayCaseRequest import \
                                            TakeItemsFromDisplayCaseRequest
from cwbot.kolextra.request.GetDisplayCaseRequest import GetDisplayCaseRequest
from cwbot.locks import InventoryLock


class NoHookahStockException(Exception):
    pass


def hookahItems():
    return {4510: "walrus ice cream",
            4511: "beautiful soup",
            4515: "lobster qua grill",
            4516: "missing wine",
            4512: "eggman noodles",
            4513: "vials of jus de larmes"}

    
def hookahItemDict():
    return dict([(h,1) for h in hookahItems().keys()])


def hookahItemCount(items):
    count = 0
    for i,q in items.items():
        if i in hookahItems():
            count += q
    return count
    

def splitItems(items):
    hItems = dict()
    oItems = dict()
    for i,q in items.items():
        if i in hookahItems().keys():
            hItems[i] = q
        else:
            oItems[i] = q
    return (hItems, oItems)


class BaseHookahModule(BaseModule):
    """ Functions common to both the HookahModule and the BaseHookahModule.
    """
    requiredCapabilities = []
    _name = "base_hookah_iterface"

    def __init__(self, manager, identity, config):
        super(BaseHookahModule, self).__init__(manager, identity, config)

        
    def outOfStock(self, keepLast):
        """ get a list of hookah parts that are not in stock (in display case)
        keepLast is an integer that states how many of each part should not be
        counted in this calculation. """
        missingItems = []
        with InventoryLock.lock:
            r = GetDisplayCaseRequest(self.session)
            inventory = self.tryRequest(r).get('items', [])     
            for iid, iname in hookahItems().items():
                threshold = keepLast
                if not any(item['id'] == iid and item['quantity'] > threshold 
                           for item in inventory):
                    missingItems.append(iname)
            return missingItems
    

    def displayAllHookahParts(self):
        """ Place all hookah parts in the display case. This ignores, of
        course, any items reserved by the inventory manager. """
        with InventoryLock.lock:
            self.inventoryManager.refreshInventory()
            inventory = self.inventoryManager.inventory()
            hList = []
            for hItem in (item for item in hookahItems().keys() 
                          if item in inventory):
                hList.append({'id': hItem, 'quantity': inventory[hItem]})
            if len(hList) > 0:
                self.log("Adding to display case: {}"
                         .format(hList))
                r = AddItemsToDisplayCaseRequest(self.session, hList)
                self.tryRequest(r)
            

    def displayHookahParts(self, itemMap):
        """ Place SOME hookah parts in the display case. The parts are
        specified by the itemMap in (item-id: quantity) entries. """
        with InventoryLock.lock:
            self.inventoryManager.refreshInventory()
            inventory = self.inventoryManager.inventory()
            hList = []
            for hItem in (item for item in hookahItems().keys() 
                          if item in inventory):
                hList.append({'id': hItem, 
                              'quantity': min(inventory.get(hItem, 0), 
                                              itemMap.get(hItem, 0))})
            if len(hList) > 0:
                r = AddItemsToDisplayCaseRequest(self.session, hList)
                self.tryRequest(r)


    def removeHookahFromDisplay(self, keepLast):
        """ Take a set of hookah parts from the display if available. If
        none are available, raise a NoHookahStockException. keepLast works
        as specified in outOfStock(). """
        with InventoryLock.lock:
            oos = self.outOfStock(keepLast) 
            if len(oos) == 0:
                hList = [{'id': iid, 'quantity': 1} 
                         for iid in hookahItems().keys()]
                r = TakeItemsFromDisplayCaseRequest(self.session, hList)
                self.tryRequest(r)
            else:
                raise NoHookahStockException


class HookahKmailModule(BaseHookahModule, BaseKmailModule):
    """ 
    A module that handles the Hookah trade program. (Users send any N hookah
    parts, and the bot returns one of each). If someone gets a hookah, it's
    announced in chat.
    
    Configuration options:
    save_last - how many of each hookah part to "reserve" [default = 1]
    message_channel - what channel the hookah message is broadcast on
                      (use None for no announcement) [default = clan]
    n - number of hookah parts required for a trade-in [default = 6]
    resends - how many additional times a player can trade for a hookah,
              in case they were stupid and didn't cook the noodles and jus.
              This is here to prevent abuse.
    
    Note that it's possible to have multiple HookahKmailModules, e.g. one
    for the clan (with clan_only = True) and another for outsiders, possibly
    with more items required for a trade-in. 
    """
    _hookahText = ("Enjoy your hookah!\n\nDO NOT FORGET to cook the "
                   "Eggman Noodles and the Vial of Jus de Larmes first!"
                    "\n\nDO NOT FORGET TO COOK THE NOODLES AND VIAL.\n\n"
                    "Seriously, don't forget. DO IT, DO IT NOW!\n\n")
    _noDonateText = ("(If you meant to donate your hookah parts, send the "
                     "parts back with 'donate' in the message text.)\n\n")
    _otherItemText = ("(Also, you sent me some other stuff. I'm not sure "
                      "what to do with it.)\n\n")
    _plusNText = ("(Also, I noticed you sent more parts than required. "
                  "I have kept the rest as a donation. Thank you!)\n\n")
    _alreadyReceivedText = ("Did you forget to cook the noodles and vial? "
                            "I told you not to. You're on your own.")

    requiredCapabilities = ['kmail', 'chat']
    _name = "hookah_kmail"

    def __init__(self, manager, identity, config):
        self._saveLast = True
        self._gotHookah = {}
        self._channel = "None"
        self._n = 6
        self._resends = 0
        super(HookahKmailModule, self).__init__(manager, identity, config)
        self.displayAllHookahParts()
        self._adminsNotified = False


    def _configure(self, config):
        self._channel = config.setdefault('message_channel', 'clan')
        try:
            self._saveLast = int(config.setdefault('save_last', 1))
            self._n = int(config.setdefault('n', 6))
            self._resends = int(config.setdefault('resends', 0))
        except ValueError:
            raise Exception("(HookahKmailModule) Config options n, resends, "
                            "and save_last must be integral") 
            
            
    def initialize(self, lastKnownState, _initData):
        self._gotHookah = lastKnownState['count']


    def checkInventory(self):
        """ Get out-of-stock parts """
        oos = self.outOfStock(self._saveLast)
        if len(oos) > 0:
            self.log("Out of hookah parts: {}".format(oos))
        return oos
        

    def helpMessage(self, uid):
        """ Send a help message to a user """
        if self._gotHookah.get(uid, 0) > self._resends:
            return self.newMessage(uid, "You're not allowed to request "
                                        "any more hookah parts.")
        
        return self.newMessage(
            uid, ("Need a hookah? Send me any {} hookah parts and I "
                  "will send you a full set of the parts in return. "
                  "For information about the hookah, see "
                  "http://kol.coldfront.net/thekolwiki/"
                  "index.php/Ittah_bittah_hookah on the KoL Wiki."
                  .format(self._n)))


    def alreadyGotHookah(self, uid, items):
        """ Send this message if a user cannot trade any more parts. """
        return self.newMessage(uid, self._alreadyReceivedText).addItems(items)    
    
        
    def tooFew(self, uid, items, count):
        """ Send this message if a user didn't send enough parts! """
        return self.newMessage(
                uid, ("You sent me {0} hookah parts, but I need {1} to give "
                      "you a full set. Try again when you have {1} parts!\n\n" 
                      "(If you meant to donate these, please include 'donate' "
                      "in your message text.)"
                      .format(count, self._n))).addItems(items)

    
    def noStock(self, uid, items, oos):
        """ Give a sad message that we are out of stock, and notify the
        admins that restocking is required. """
        if not self._adminsNotified:
            for userId in self.properties.getAdmins('hookah_notify'):
                try:
                    self.sendKmail(self.newMessage(
                            userId, "I am out of the following hookah parts: "
                                    "{}".format(', '.join(oos))))
                except MessageError:
                    self.errorLog("Could not send message to {}"
                                  .format(userId))
                except:
                    self.errorLog("Error sending out of hookah parts message")
            self._adminsNotified = True
        return (self.newMessage(uid, "I'm sorry, but I am out of stock for "
                                     "hookah parts. I've notified the admins.")
                .addItems(items))

    
    def sendHookah(self, userName, uid, otherItems, count):
        """ Send the message to send a hookah! """
        msgtxt = self._hookahText + self._noDonateText
        if self._channel.lower().strip() != "none":
            if count > self._n:
                msgtxt += self._plusNText
                self.chat("{} has earned the right to wield a shiny new "
                          "hookah, and donated an extra {} parts! DO NOT "
                          "FORGET TO COOK THE NOODLES AND VIAL."
                          .format(userName, count-self._n), self._channel)
            else:
                self.chat("{} has earned the right to wield a shiny "
                          "new hookah! DO NOT FORGET TO COOK THE NOODLES "
                          "AND VIAL.".format(userName), self._channel)
        if len(otherItems) > 0:
            msgtxt += self._otherItemText
            
        self.log("Sending hookah to {}...".format(uid))
        
        self._gotHookah[uid] = self._gotHookah.get(uid, 0) + 1
        newMsg = self.newMessage(uid, msgtxt).addItems(hookahItemDict())
        if otherItems is not None and len(otherItems) > 0:
            newMsg.addItems(otherItems)
        return newMsg

    
    def _processKmail(self, message):
        items = message.items
        uid = message.uid
        count = hookahItemCount(items)
        if count == 0:
            if message.text.lower()[:6] != "hookah":
                return None
    
        with InventoryLock.lock:
            self.log("Received {} hookah items from {}".format(count, uid))
            (hookahItems, otherItems) = splitItems(items)
            
            if self._gotHookah.get(uid, 0) > self._resends:
                return self.alreadyGotHookah(uid, items)
            
            if count == 0:
                return self.helpMessage(uid)
            if count < self._n:
                return self.tooFew(uid, items, count)
    
            uname = message.info.get('userName', "A mysterious stranger")
            
            if count >= self._n:
                self.displayHookahParts(hookahItems)
                try:
                    self.log("Removing hookah...")
                    self.removeHookahFromDisplay(self._saveLast)
                    self.log("done.")
                except NoHookahStockException:
                    oos = self.outOfStock(self._saveLast)
                    return self.noStock(uid, items, oos)
                return self.sendHookah(uname, uid, otherItems, count)
            raise Exception("Logic error: unknown number of hookah items")
        
    
    def messageSendFailed(self, sentMessage, exception):
        """ Roll back number of received hookahs """
        uid = sentMessage.uid
        self._gotHookah[uid] = self._gotHookah.get(uid, 1) - 1
        self.errorLog("Error sending hookah to {}; rolling back..."
                      .format(uid))
        
    def _eventCallback(self, eData):
        if eData.subject == "state":
            return self.state
        
        
    @property
    def state(self):
        return {'count': self._gotHookah}
    
    
    @property
    def initialState(self):
        return {'count': {}}
    
    
    def _kmailDescription(self):
        return ("HOOKAH EXCHANGE: Want an ittah bittah hookah? Send me a "
                "kmail with the text \"hookah\" for details.")


class HookahDonateKmailModule(BaseHookahModule, BaseKmailModule):
    """ 
    A module that handles donation kmails with hookah parts and announces
    the donation in chat.
    
    message_channel - what channel the hookah donate message is broadcast on
                      (use None for no announcement) [default = clan]
    """
    requiredCapabilities = ['kmail', 'chat']
    _name = "hookah_donate"
    
    def __init__(self, manager, identity, config):
        self._channel = "none"
        super(HookahDonateKmailModule, self).__init__(
                                                manager, identity, config)
        
        
    def _configure(self, config):
        self._channel = config.setdefault('message_channel', 'clan')


    def _processKmail(self, message):
        items = message.items
        uid = message.uid
        text = message.text
        count = hookahItemCount(items)
        if count == 0:
            return None

        if "donate" in text.lower():
            with InventoryLock.lock:
                self.log("Received {} hookah item donation from {}"
                         .format(count, uid))
                if self._channel.lower().strip() != "none":
                    uname = message.info.get('userName', 
                                                "A mysterious stranger")
                    self.chat("{} has generously donated {} hookah part(s)!"
                              .format(uname, count), self._channel)
                (hookahItems, _otherItems) = splitItems(items)
                self.displayHookahParts(hookahItems)
            return self.newMessage(uid, "Thank you for your donation!")
        return None
