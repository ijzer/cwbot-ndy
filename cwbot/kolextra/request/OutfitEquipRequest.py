import re
from kol.request.GenericRequest import GenericRequest
from kol import Error
from cwbot.locks import InventoryLock


class OutfitEquipRequest(GenericRequest):
    """Equips an outfit"""
    _cantEquip = re.compile(r'''You don't have sufficient|You put on part of an Outfit|Item <b>NOT</b> found''', re.IGNORECASE)
    _badNumber = re.compile(r'Invalid Custom Outfit selected|Invalid outfit selected', re.IGNORECASE)
    _missingItems = re.compile(r'''You don't have enough items from this outfit to properly equip it''', re.IGNORECASE)
    _success = re.compile(r'''You are already wearing|You already have that outfit equipped|You put on an Outfit:''', re.IGNORECASE)
    
    
    def __init__(self, session, outfitNum, isCustom):
        super(OutfitEquipRequest, self).__init__(session)
        self.url = session.serverURL + "inv_equip.php"
        self.requestData["pwd"] = session.pwd
        self.requestData['action'] = 'outfit'
        signMult = -1 if isCustom else 1
        self.requestData['whichoutfit'] = str(signMult * outfitNum).strip()


    def doRequest(self):
        with InventoryLock.lock:
            super(OutfitEquipRequest, self).doRequest()
        self.responseData = {'result': self.responseText}
        if self._success.search(self.responseText) is not None:
            return self.responseData
        elif self._cantEquip.search(self.responseText) is not None:
            raise Error.Error("Stats are not high enough to equip outfit {}"
                              .format(self.requestData['whichoutfit']),
                              Error.USER_IS_LOW_LEVEL)
        elif self._missingItems.search(self.responseText) is not None:
            raise Error.Error("Missing items from outfit {}"
                              .format(self.requestData['whichoutfit']),
                              Error.ITEM_NOT_FOUND)
        elif self._badNumber.search(self.responseText) is not None:
            raise Error.Error("Invalid outfit number: {}"
                              .format(self.requestData['whichoutfit']),
                              Error.INVALID_ACTION)
        else:
            raise Error.Error("An unknown error occurred equipping outfit {}"
                              .format(self.requestData['whichoutfit']),
                              Error.REQUEST_GENERIC)
