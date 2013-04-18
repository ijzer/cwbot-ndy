import re
import kol.Error as Error
from kol.request.GenericRequest import GenericRequest
from kol.manager import PatternManager
from kol.util import ParseResponseUtils


class GalaktikBuyRequest(GenericRequest):
    notEnoughMeat = re.compile(r"You can't afford that much medicine, my friend!")
    notSold = re.compile(r"We don't sell that item here, my friend!")


    def __init__(self, session, itemId, quantity=1):
        super(GalaktikBuyRequest, self).__init__(session)
        self.session = session
        self.url = session.serverURL + "galaktik.php"
        self.requestData['action'] = "buyitem"
        self.requestData['whichitem'] = itemId
        self.requestData['howmany'] = quantity
        self.requestData['pwd'] = session.pwd


    def parseResponse(self):
        if self.notSold.search(self.responseText):
            raise Error.Error("This store doesn't carry that item.", Error.ITEM_NOT_FOUND)
        if self.notEnoughMeat.search(self.responseText):
            raise Error.Error("You do not have enough meat to purchase the item(s).", Error.NOT_ENOUGH_MEAT)

        items = ParseResponseUtils.parseItemsReceived(self.responseText, self.session)
        if len(items) == 0:
            raise Error.Error("Unknown error. No items received.", Error.REQUEST_FATAL)
        self.responseData["items"] = items

        meatSpentPattern = PatternManager.getOrCompilePattern('meatSpent')
        match = meatSpentPattern.search(self.responseText)
        self.responseData['meatSpent'] = int(match.group(1).replace(',', ''))

