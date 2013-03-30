from kol.request.GenericRequest import GenericRequest
from cwbot.locks import InventoryLock


class TakeItemsFromDisplayCaseRequest(GenericRequest):
    """Remove items from the player's display case. No error checking is 
    performed."""
    __lock = InventoryLock.lock

    def __init__(self, session, items):
        super(TakeItemsFromDisplayCaseRequest, self).__init__(session)
        self.url = session.serverURL + "managecollection.php"
        self.requestData["pwd"] = session.pwd
        self.requestData["action"] = "take"

        ctr = 0
        for item in items:
            ctr += 1
            self.requestData["whichitem%s" % ctr] = item["id"]
            self.requestData["howmany%s" % ctr] = item["quantity"]
        print("Request: " + str(self.requestData))

    def doRequest(self):
        with self.__lock:
            super(TakeItemsFromDisplayCaseRequest, self).doRequest()
