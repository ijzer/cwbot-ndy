import re
from kol.request.GenericRequest import GenericRequest
from kol.database import ItemDatabase
from kol.manager import PatternManager
from kol.util import ParseResponseUtils
import kol.Error as Error
from cwbot.locks import InventoryLock


class SpecialShopRequest(GenericRequest):
    """Uses a special shop or assembly item (such as the star chart)"""

    _itemsRegex = re.compile(r'''javascript:descitem\(\d+\)'><b>([^<]+)</b>.*?whichrow=(\d+)''')

    def __init__(self, session, whichshop, whichrow=None, quantity=1):
        super(SpecialShopRequest, self).__init__(session)
        self.url = session.serverURL + "shop.php"
        self.requestData["pwd"] = session.pwd
        self.requestData["whichshop"] = whichshop
        self._buy = (whichrow is not None)
        if self._buy:
            self.requestData["whichrow"] = whichrow
            self.requestData["quantity"] = quantity
            self.requestData["action"] = "buyitem" 

    def doRequest(self):
        with InventoryLock.lock:
            return super(SpecialShopRequest, self).doRequest()

    def parseResponse(self):
        # Check for errors.
        if self._buy:
            items = ParseResponseUtils.parseItemsReceived(self.responseText, self.session)
            if len(items) == 0:
                raise Error.Error("Unknown error. No items received.", Error.REQUEST_FATAL)
            self.responseData["items"] = items
        found = self._itemsRegex.findall(self.responseText)
        self.responseData["available"] = {name: row for name,row in found}
        
        
