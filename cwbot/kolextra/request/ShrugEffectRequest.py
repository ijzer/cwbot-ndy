from kol.request.GenericRequest import GenericRequest


class ShrugEffectRequest(GenericRequest):
    "Attempt to remove an effect. No response is available."

    def __init__(self, session, effectId):
        super(ShrugEffectRequest, self).__init__(session)
        self.url = session.serverURL + "charsheet.php"
        self.requestData["action"] = "unbuff"
        self.requestData["pwd"] = session.pwd
        self.requestData["whichbuff"] = effectId

    def parseResponse(self):
        pass