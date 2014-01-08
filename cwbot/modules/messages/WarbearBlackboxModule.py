from cwbot.modules.BaseKmailModule import BaseKmailModule
from cwbot.locks import InventoryLock
from cwbot.kolextra.request.SpecialShopRequest import SpecialShopRequest
from cwbot.common.exceptions import FatalError
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
    
    _items = {'blind-packed die-cast metal toy': 
                {'cost': 10, 
                 'nicknames': ["die-cast", "die cast"],
                 'id': 6972},
              'warbear helm fragment': 
                {'cost': 50,
                 'nicknames': ["helm fragment"],
                 'id': 6927},
              'warbear trouser fragment': 
                {'cost': 50,
                 'nicknames': ["trouser fragment"],
                 'id': 6937},
              'warbear accoutrements chunk': 
                {'cost': 50,
                 'nicknames': ["accoutrements chunk", "accessory chunk"],
                 'id': 6947},
              'warbear requisition box': 
                {'cost': 100,
                 'nicknames': ["box2"],
                 'id': 6957},
              'warbear dress greaves': 
                {'cost': 200,
                 'nicknames': ["greaves"],
                 'id': 7094},
              'warbear dress bracers': 
                {'cost': 300,
                 'nicknames': ["bracers"],
                 'id': 7093},
              'warbear dress helmet': 
                {'cost': 400,
                 'nicknames': ["helmet"],
                 'id': 7092},
              'warbear officer requisition box': 
                {'cost': 500,
                 'nicknames': ["box3"],
                 'id': 6968}}

    
    def __init__(self, manager, identity, config):
        super(WarbearBlackboxModule, self).__init__(manager, identity, config)
        self.inventoryManager.refreshInventory()
        inventory = self.inventoryManager.inventory()
        blackBoxes = inventory.get(7035, 0)
        if blackBoxes == 0:
            raise FatalError("No warbear black box in inventory.")
        
        
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
        cost = qty * self._items[desiredName]['cost']
        if cost > whosits:
            self.debugLog("Not enough whosits; need {} but only got {}"
                          .format(cost, whosits))
            return (self.newMessage(message.uid,
                                    "I need {} warbear whosits to create {}x "
                                    "{}.".format(cost, qty, desiredName),
                                    message.meat)
                                    .addItems(message.items))
        d2 = {}
        with InventoryLock.lock:
            itemId = self._items[desiredName]['id']
            self.inventoryManager.refreshInventory()
            inventory = self.inventoryManager.inventory()
            qtyHave = min(inventory.get(itemId, 0), qty)
            qtyNeed = max(qty - qtyHave, 0)
            self.debugLog("Have {} {}, need {} more..."
                          .format(inventory.get(itemId, 0), 
                                  desiredName, 
                                  qtyNeed))
            if qtyNeed > 0:
                try:
                        r1 = SpecialShopRequest(self.session, 'warbear')
                        d1 = self.tryRequest(r1)
                        row = d1['available'][desiredName]
                        r2 = SpecialShopRequest(self.session, 
                                                'warbear', 
                                                row, 
                                                qtyNeed)
                        d2 = self.tryRequest(r2)
                except kol.Error.Error as e:
                    self.errorLog("Error with Warbear Black Box: {}", e)
                    d2 = {}
            
            receivedQty = d2['items'][0]['quantity'] if d2 else 0
            totalQty = receivedQty + qtyHave
            realCost = self._items[desiredName]['cost'] * totalQty
            returnItems = copy.deepcopy(message.items)
            returnItems[6913] -= realCost
            m = (self.newMessage(message.uid,
                                "Enjoy!",
                                message.meat)
                                .addItems(returnItems))
            return m.addItems({itemId: totalQty})
        
        
    def _getDesired(self, txt):
        matches = []
        for name, data in self._items.items():
            if any(True for nick in data['nicknames'] if nick in txt.lower()):
                matches.append(name)
        if len(matches) != 1:
            return None, None
        qtyMatch = re.search(r"""^(\d+)\s""", txt)
        qty = int(qtyMatch.group(1)) if qtyMatch is not None else 1
        if qty == 0:
            return None, None
        return matches[0], qty


    def _kmailDescription(self):
        return ("WARBEAR BLACK BOX: I can convert Warbear Whosits into other "
                """Warbear items. Send the text "whosits" for details.""")
        
