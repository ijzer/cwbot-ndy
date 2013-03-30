from kol.request.GenericRequest import GenericRequest
from cwbot.locks import InventoryLock


class AddItemsToDisplayCaseRequest(GenericRequest):
    """Adds items to the player's display case. There is no notification of
    failure (KoL limitation). """
    __lock = InventoryLock.lock

    def __init__(self, session, items):
        super(AddItemsToDisplayCaseRequest, self).__init__(session)
        self.url = session.serverURL + "managecollection.php"
        self.requestData["pwd"] = session.pwd
        self.requestData["action"] = "put"

        ctr = 0
        for item in items:
            if item['quantity'] > 0:
                ctr += 1
                self.requestData["whichitem%s" % ctr] = item["id"]
                self.requestData["howmany%s" % ctr] = item["quantity"]


    def doRequest(self):
        with self.__lock:
            super(AddItemsToDisplayCaseRequest, self).doRequest()
            