import re
import kol.Error as Error
from kol.request.GenericRequest import GenericRequest


class GalaktikRequest(GenericRequest):
    requestTooHigh = re.compile(r"You don't require that much healing, my friend!|You don't require any invigoration, my friend!")
    notEnoughMeat = re.compile(r"You can't afford that much")


    def __init__(self, session, hp=True, quantity=None):
        super(GalaktikRequest, self).__init__(session)
        self.session = session
        self.url = session.serverURL + "galaktik.php"
        if hp:
            self.requestData['action'] = "curehp"
        else:
            self.requestData['action'] = "curemp"
        if quantity is not None:
            self.requestData['quantity'] = quantity
        self.requestData['pwd'] = session.pwd


    def parseResponse(self):
        if self.requestTooHigh.search(self.responseText):
            raise Error.Error("You don't require that much healing.", Error.REQUEST_GENERIC)
        if self.notEnoughMeat.search(self.responseText):
            raise Error.Error("You don't have enough meat.", Error.NOT_ENOUGH_MEAT)
        self.responseData = {}
