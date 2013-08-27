from kol.request.GenericRequest import GenericRequest

class RemovePlayerFromClanWhitelistRequest(GenericRequest):
    def __init__(self, session, uid):
        super(RemovePlayerFromClanWhitelistRequest, self).__init__(session)
        self.url = session.serverURL + "clan_whitelist.php"
        self.requestData["action"] = "update"
        self.requestData["pwd"] = session.pwd
        self.requestData["drop{}".format(uid)] = "on"
        self.requestData["player{}".format(uid)] = uid
