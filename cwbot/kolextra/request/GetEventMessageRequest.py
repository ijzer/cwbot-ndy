from kol.request.ApiRequest import ApiRequest

class GetEventMessageRequest(ApiRequest):
    "This class is used to get a list of items in the user's inventory."

    def __init__(self, session, sinceAzTime=None):
        super(GetEventMessageRequest, self).__init__(session)
        self.requestData["what"] = "events"
        if sinceAzTime is not None:
            self.requestData['since'] = "@{}".format(sinceAzTime)
        

    def parseResponse(self):
        super(GetEventMessageRequest, self).parseResponse()
        self.responseData["events"] = self.jsonData
