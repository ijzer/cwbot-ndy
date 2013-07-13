from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock
from cwbot.kolextra.request.HotdogStockRequest import HotdogStockRequest
from cwbot.util.tryRequest import tryRequest
from cwbot.util.textProcessing import intOrFloatToString
import kol.Error
from copy import deepcopy

class HotdogModule(BaseKmailModule):
    """ 
    A module that stores hot dog ingredients for users.
    """
    
    requiredCapabilities = ['kmail', 'inventory']
    _name = "hotdogs"
    
    _hotdogs = [
        {'id': -93, 'name': "savage macho dog", 'item': 616, 'quantity': 10},
        {'id': -94, 'name': "one with everything", 'item': 672, 'quantity': 10},
        {'id': -95, 'name': "sly dog", 'item': 163, 'quantity': 10},
        {'id': -96, 'name': "devil dog", 'item': 1451, 'quantity': 25},
        {'id': -97, 'name': "chilly dog", 'item': 1452, 'quantity': 25},
        {'id': -98, 'name': "ghost dog", 'item': 1453, 'quantity': 25},
        {'id': -99, 'name': "junkyard dog", 'item': 1454, 'quantity': 25},
        {'id': -100, 'name': "wet dog", 'item': 1455, 'quantity': 25},
        {'id': -101, 'name': "sleeping dog", 'item': 2638, 'quantity': 10},
        {'id': -103, 'name': "video games hot dog", 'item': 6174, 'quantity': 3}]
        
    _instructionText = ("Hotdogs require a VIP key.\nTo store hotdog items, "
                        "send the applicable items to "
                        "me.\nTo request a hotdog, send a kmail with the text "
                        "'hotdog XXXX', where XXXX is part of the name of a "
                        "hotdog.\nTo get your items back, send the text "
                        "'hotdog return'.\nMore information about hotdogs "
                        "is available at "
                        "http://kol.coldfront.net/thekolwiki/index.php/Hot_Dog_Stand")
    
    def __init__(self, manager, identity, config):
        self._stored = {}
        super(HotdogModule, self).__init__(manager, identity, config)
    
    def initialize(self, state, initData):
        self._stored = {}
        # convert from JSON, which only allows string keys
        for uid_s,its in state['stored'].items():
            self._stored[int(uid_s)] = dict((int(k),v) for k,v in its.items())
        
    @property
    def state(self):
        stored = {}
        # convert to JSON, which only allows string keys
        for uid,its in self._stored.items():
            stored[str(uid)] = dict((str(k),v) for k,v in its.items())
        return {'stored': stored}

    @property
    def initialState(self):
        return {'stored': {}}

    def _getDisplayItemText(self, uid):
        storedItems = self._stored.get(uid, {})
        displayItems = {}
        for v in self._hotdogs:
            n = storedItems.get(v['item'], 0)
            if n > 0:
                displayItems[v['name']] = float(n) / v['quantity']
        if not displayItems:
            return "You have no hotdogs available.\n\n" + self._instructionText
        return ("You have the following hotdogs available: \n\n"
                + '\n'.join("{}x {}".format(intOrFloatToString(v),k)
                  for k,v in displayItems.items())
                + "\n\n" + self._instructionText)
        
        
    def _storeItems(self, message, newItems):
        returnItems = dict((k,v-newItems.get(k,0)) 
                           for k,v in message.items.items())
        storedItems = self._stored.get(message.uid, {})
        for k,v in newItems.items():
            storedItems[k] = storedItems.get(k, 0) + v
        self.log("Deposit from {}. New totals: {}"
                 .format(message.uid, storedItems))
        self._stored[message.uid] = storedItems
        return (self.newMessage(message.uid,
                                "I have saved your items for later use.\n\n"
                                + self._getDisplayItemText(message.uid),
                                message.meat).addItems(returnItems))
    
    
    def _processKmail(self, message):
        newItems = {}
        uid = message.uid
        for v in self._hotdogs:
            iid = v['item']
            qtyInKmail = message.items.get(v['item'], 0)
            newItems[iid] = qtyInKmail
        if any(n > 0 for n in newItems.values()):
            return self._storeItems(message, newItems)
        elif message.text[:6].lower() == "hotdog":
            afterText = message.text[7:].strip().lower()
            if afterText == "":
                return (self.newMessage(uid,
                                        self._getDisplayItemText(uid), 
                                        message.meat).addItems(message.items))              
            if afterText == "return":
                with InventoryLock.lock:
                    msg = self.newMessage(uid,
                                          "Here are your items.\n\n"
                                          + self._instructionText, 
                                          message.meat).addItems(message.items)
                    for k,v in self._stored.get(uid, {}).items():
                        msg.addItem(k,v)
                    try:
                        del self._stored[message.uid]
                    except KeyError:
                        pass
                    return msg
            return self._sendHotdog(message, afterText)
        return None
                

    def _sendHotdog(self, message, afterText):
        createMsg = lambda s: (self.newMessage(
                                   uid, 
                                   s + "\n\n" + self._getDisplayItemText(uid), 
                                   message.meat)
                               .addItems(message.items))
        words = afterText.lower().split()
        hotdogs = []
        uid = message.uid
        for h in self._hotdogs:
            if all(w in h['name'] for w in words):
                hotdogs.append(h)
        if len(hotdogs) > 1:
            return createMsg("'{}' matched more than one hotdog."
                             .format(afterText))
        if not hotdogs:
            return createMsg("'{}' matched no hotdogs.".format(afterText))
        h = hotdogs[0]
        if self._stored.get(message.uid, {}).get(h['item'], 0) < h['quantity']:
            return createMsg("You don't have enough items deposited "
                             "for the {}.".format(h['name']))
        with InventoryLock.lock:
            self.inventoryManager.refreshInventory()
            inv = self.inventoryManager.inventory()
            n = inv.get(h['item'], 0)
            if n < h['quantity']:
                return createMsg("ERROR: I am out of items! Please "
                                 "notify an administrator.")
            r = HotdogStockRequest(self.session, h['id'], h['quantity'])
            try:
                tryRequest(r, numTries=1)
            except kol.Error.Error as e:
                return createMsg("An error occurred: {}".format(e.msg))
           
            storedItems = deepcopy(self._stored[uid]) 
            storedItems[h['item']] -= h['quantity']
            self.log("Cashing out {} for hotdog {}, new totals {}"
                     .format(uid, h['id'], storedItems))
            storedItems = dict((k,v) for k,v in storedItems.items()
                                           if v != 0)
            if storedItems:
                self._stored[uid] = storedItems
            elif self._stored[uid]:
                del self._stored[uid]
            return createMsg("One {} has been prepared for you."
                             .format(h['name']))
    

    def _kmailDescription(self):
        return ("HOTDOGS: I will store hotdog ingredients for you to use "
                "in-run. Send a kmail with the text 'hotdog' for help.") 
