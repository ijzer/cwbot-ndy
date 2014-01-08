from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock
from cwbot.kolextra.request.SpecialShopRequest import SpecialShopRequest
import kol.Error
import re
import copy


class WarbearBlackboxModule(BaseKmailModule):
    """ 
    A module allows users to send whosits for black box items
    """
    
    requiredCapabilities = ['kmail', 'inventory']
    _name = "warbear"
    
    _helpText = ("Send me warbear whosits along with a command to create "
                 "items.\n\n"
                "List of commands and their associated items and costs:\n\n"
                "'die-cast': blind-packed die-cast metal toy (10 whosits)\n"
                "'helm fragment': warbear helm fragment (50 whosits)\n"
                "'trouser fragment': warbear trouser fragment (50 whosits)\n"
                "'accoutrements chunk' or 'accessory chunk': "
                                "warbear accoutrements chunk (50 whosits)\n"
                "'box2': warbear requisition box (100 whosits)\n"
                "'greaves': warbear dress greaves (200 whosits)\n"
                "'bracers': warbear dress bracers (300 whosits)\n"
                "'helmet': warbear dress helmet (400 whosits)\n"
                "'box3': warbear officer requisition box (500 whosits)\n\n"
                "Only one type of item can be created at a time, but you can "
                "request multiple copies of the same item. For example, "
                "send the text '10 die-cast' (along with 100 warbear whosits) "
                "to make ten die-cast toys at once.")
    
    _items = {'blind-packed die-cast metal toy': 10,
              'warbear helm fragment': 50,
              'warbear trouser fragment': 50,
              'warbear accoutrements chunk': 50,
              'warbear requisition box': 100,
              'warbear dress greaves': 200,
              'warbear dress bracers': 300,
              'warbear dress helmet': 400,
              'warbear officer requisition box': 500}
    
    _nicknames = {'die-cast': 'blind-packed die-cast metal toy',
                  'die cast': 'blind-packed die-cast metal toy',
                  'helm fragment': 'warbear helm fragment',
                  'trouser fragment': 'warbear trouser fragment',
                  'accoutrements chunk': 'warbear accoutrements chunk',
                  'accessory chunk': 'warbear accoutrements chunk',
                  'box2': 'warbear requisition box',
                  'greaves': 'warbear dress greaves',
                  'bracers': 'warbear dress bracers',
                  'helmet': 'warbear dress helmet',
                  'box3': 'warbear officer requisition box'}

    
    def __init__(self, manager, identity, config):
        super(WarbearBlackboxModule, self).__init__(manager, identity, config)
        
        
    def _processKmail(self, message):
        if "whosit" in message.text.lower():
            return (self.newMessage(message.uid,
                                    self._helpText,
                                    message.meat)
                                    .addItems(message.items))
        whosits = message.items.get(6913, 0)
        if whosits == 0:
            return None
        self.debugLog("Player {} sent {} whosits".format(message.uid,
                                                         whosits))
        desiredName, qty = self._getDesired(message.text)
        if desiredName is None:
            return (self.newMessage(message.uid,
                                    self._helpText,
                                    message.meat)
                                    .addItems(message.items))
        self.debugLog("Player {} requested {} {}".format(message.uid,
                                                         qty,
                                                         desiredName))
        cost = qty * self._items[desiredName]
        if cost > whosits:
            self.debugLog("Not enough whosits; need {} but only got {}"
                          .format(cost, whosits))
            return (self.newMessage(message.uid,
                                    "I need {} warbear whosits to create {}x "
                                    "{}.".format(cost, qty, desiredName),
                                    message.meat)
                                    .addItems(message.items))
        d2 = {}
        try:
            with InventoryLock.lock:
                r1 = SpecialShopRequest(self.session, 'warbear')
                d1 = self.tryRequest(r1)
                row = d1['available'][desiredName]
                r2 = SpecialShopRequest(self.session, 'warbear', row, qty)
                d2 = self.tryRequest(r2)
        except kol.Error.Error as e:
            self.errorLog("Error with Warbear Black Box: {}", e)
            d2['items'] = []
            
        its = d2['items']
        if not its:
            return (self.newMessage(message.uid,
                                    "An error occurred. Please try again "
                                    "later.",
                                    message.meat)
                                    .addItems(message.items))
        receivedQty = d2['items'][0]['quantity']
        realCost = self._items[desiredName] * receivedQty
        returnItems = copy.deepcopy(message.items)
        returnItems[6913] -= realCost
        m = (self.newMessage(message.uid,
                            "Enjoy!",
                            message.meat)
                            .addItems(returnItems))
        return m.addItems({it['id']: it['quantity'] for it in its})
        
        
    def _getDesired(self, txt):
        matches = [name for name in self._nicknames if name in txt.lower()]
        if len(matches) != 1:
            return None, None
        qtyMatch = re.search(r"""^(\d+)\s""", txt)
        qty = int(qtyMatch.group(1)) if qtyMatch is not None else 1
        if qty == 0:
            return None, None
        return self._nicknames[matches[0]], qty


    def _kmailDescription(self):
        return ("WARBEAR BLACK BOX: I can convert Warbear Whosits into other "
                """Warbear items. Send the text "whosits" for details.""")
        
