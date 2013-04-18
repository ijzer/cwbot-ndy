from cwbot.modules.BaseModule import BaseModule
from cwbot.util.textProcessing import stringToBool
from kol.request.CrimboTreeRequest import CrimboTreeRequest
from kol.request.LookingGlassRequest import LookingGlassRequest
from kol.request.MeatBushRequest import MeatBushRequest
from kol.request.MeatTreeRequest import MeatTreeRequest
from kol.request.MeatOrchidRequest import MeatOrchidRequest
from kol.request.DeluxeMrKlawRequest import DeluxeMrKlawRequest
from kol.request.MrKlawRequest import MrKlawRequest
from kol.request.RumpusRoomRequest import RumpusRoomRequest
from kol.request.StoreRequest import StoreRequest
from kol.request.CharpaneRequest import CharpaneRequest
from kol.request.UseItemRequest import UseItemRequest
from kol.request.HermitRequest import HermitRequest
from collections import defaultdict


class BreakfastModule(BaseModule):
    """ 
    A module that performs various login activities like checking the 
    Meat Bush. Right now, the snack machine and swimming pool are unsupported.
    
    Configuration options:
    vip - if set, also check the VIP lounge [default = True]
    clovers - set if we should try to buy clovers.
    """
    requiredCapabilities = ['chat']
    _name = "breakfast"

    def __init__(self, manager, identity, config):
        self._items = defaultdict(lambda:0)
        self._meat = 0
        self._vip = False
        self._clovers = 0
        self._breakfasted, self._initialized = False, False
        super(BreakfastModule, self).__init__(manager, identity, config)
        
        
    def _configure(self, config):
        self._vip = stringToBool(config.setdefault('vip', 'true'))
        self._clovers = stringToBool(config.setdefault('clovers', 'true'))
        

    def _doRequest(self, RequestClass, *args):
        """ Wrapper around self.tryRequest. Returns True on success. """
        if not self.session.isConnected:
            return
        r = RequestClass(self.session, *args)
        result = self.tryRequest(r, nothrow=True, numTries=1)
        if result is None:
            return False
        self._meat += result.get('meat', 0)
        items = result.get('items', [])
        for it in items:
            iname = it['name']
            self._items[iname] += it.get('quantity')
        return True
    

    def _numWorthless(self):
        """ Number of worthless trinkets """
        self.inventoryManager.refreshInventory()
        inv = self.inventoryManager.inventory()
        n = inv.get(43, 0) + inv.get(44, 0) + inv.get(45, 0)
        return n
    
    
    def _numChewingGum(self):
        """ Number of chewing gum on a string """
        self.inventoryManager.refreshInventory()
        inv = self.inventoryManager.inventory()
        n = inv.get(23, 0)
        return n
    
    
    def _getWorthless(self):
        """ Get a new worthless trinket by using chewing gum repeatedly.
        Return number of trinkets received (should be 1 or 0). """
        n = 0
        success = True
        while n == 0 and success:
            if self._numChewingGum() == 0:
                success &= self._doRequest(StoreRequest, StoreRequest.MARKET, 
                                           23)
                if success:
                    self._meat -= 50
            success &= self._doRequest(UseItemRequest, 23)
            n = self._numWorthless()
        return n
    
    
    def _getClover(self):
        """ Get a clover by first getting a worthless trinket if necessary. 
        The clover is automatically disassembled. """
        if self._numWorthless() == 0:
            self._getWorthless()
        success = self._doRequest(HermitRequest, 24)
        success &= self._doRequest(UseItemRequest, 24)
        if success:
            self._clovers += 1
        return success

    
    def _eventCallback(self, eData):
        if eData.subject == "startup" and eData.fromIdentity == "__system__":
            # run once startup occurs.
            self._initialized = True
    
    
    def _heartbeat(self):
        # actual breakfast is done inside the heartbeat thread to make it
        # asynchronous.
        if self._breakfasted or not self._initialized:
            return
        self._breakfasted = True
        r = RumpusRoomRequest(self.session)
        d1 = self.tryRequest(r)
        d = d1.get('furniture', [])
        sourceList = []
        
        self.log("Performing breakfast...")
        if 'A Mr. Klaw "Skill" Crane Game' in d:
            success  = self._doRequest(MrKlawRequest)
            success |= self._doRequest(MrKlawRequest)
            success |= self._doRequest(MrKlawRequest)
            if success:
                sourceList.append("Mr. Klaw")
        if "An Exotic Hanging Meat Orchid" in d:
            success = self._doRequest(MeatOrchidRequest)
            if success:
                sourceList.append("Meat Orchid")        
        if "A Potted Meat Bush" in d:
            success = self._doRequest(MeatBushRequest)
            if success:
                sourceList.append("Meat Bush")
        if "A Potted Meat Tree" in d:
            success = self._doRequest(MeatTreeRequest)
            if success:
                sourceList.append("Meat Tree")
        if self._vip:
            success = self._doRequest(CrimboTreeRequest)
            if success:
                sourceList.append("Crimbo Tree")
            success = self._doRequest(LookingGlassRequest)
            if success:
                sourceList.append("Looking Glass")
            success  = self._doRequest(DeluxeMrKlawRequest)
            success |= self._doRequest(DeluxeMrKlawRequest)
            success |= self._doRequest(DeluxeMrKlawRequest)
            if success:
                sourceList.append("Deluxe Mr. Klaw")
        
        r = CharpaneRequest(self.session)
        d = self.tryRequest(r, nothrow=True)
        if d is not None and d['meat'] > 2000:
            success = self._getClover()
            while success:
                success = self._getClover()

        if self._meat > 0 or len(self._items) > 0:
            itemTxt = '\n'.join("{}x {}".format(qty, name) 
                                for name,qty in self._items.items() 
                                if qty != 0)
            self.log("Breakfast results:\nGot {} meat and the following "
                     "items:\n{}".format(self._meat, itemTxt))
        else:
            self.log("Got nothing.")
            