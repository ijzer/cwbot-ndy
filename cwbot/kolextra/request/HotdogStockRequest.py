import re
import kol.Error as Error
from kol.request.GenericRequest import GenericRequest


class HotdogStockRequest(GenericRequest):
    notEnough = re.compile(r"You don't have that many")
    success = re.compile(r"You have put some hot dog making supplies")
    badId = re.compile(r"That's not a real hot dog")


    def __init__(self, session, hotdogId, quantity=1):
        super(HotdogStockRequest, self).__init__(session)
        self.session = session
        self.url = session.serverURL + "clan_viplounge.php"
        self.requestData['preaction'] = "hotdogsupply"
        self.requestData['whichdog'] = hotdogId
        self.requestData['quantity'] = quantity
        self.requestData['pwd'] = session.pwd


    def parseResponse(self):
        if self.notEnough.search(self.responseText):
            raise Error.Error("Not enough items", Error.ITEM_NOT_FOUND)
        if self.badId.search(self.responseText):
            raise Error.Error("Bad hotdog ID", Error.INVALID_ACTION)
        if self.success.search(self.responseText):
            self.responseData["success"] = True
            return
        raise Error.Error("Unknown error. No success message detected.", Error.REQUEST_FATAL)
