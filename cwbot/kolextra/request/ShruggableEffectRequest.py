from kol.request.GenericRequest import GenericRequest
import re


class ShruggableEffectRequest(GenericRequest):
    "Get a list of all shruggable effect numbers."

    def __init__(self, session):
        super(ShruggableEffectRequest, self).__init__(session)
        self.url = session.serverURL + "charpane.php"
        self.requestData["pwd"] = session.pwd

    def parseResponse(self):
        self.responseData['effects'] = re.findall(r'shrug\((\d+),', self.responseText)