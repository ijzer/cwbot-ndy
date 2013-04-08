from kol.request.GenericRequest import GenericRequest
import re
from cwbot.locks import InventoryLock


class GetDisplayCaseRequest(GenericRequest):
    "Get list of items in the player's display case."
    __lock = InventoryLock.lock

    def __init__(self, session):
        super(GetDisplayCaseRequest, self).__init__(session)
        self.url = session.serverURL + "managecollection.php"
        self.requestData["pwd"] = session.pwd


    def doRequest(self):
        with self.__lock:
            return super(GetDisplayCaseRequest, self).doRequest()

    
    def parseResponse(self):
        m = re.search(r'Take:.*?</select>', self.responseText, re.MULTILINE | re.DOTALL)
        if m is None:
            self.responseData['items'] = {}
            return
        txt = m.group(0)
        items = []
        for it in re.finditer(r'''<option value='(\d+)'.*?\((\d+)\)</option>''', txt, re.MULTILINE | re.DOTALL):
            items.append({'id': int(it.group(1)), 'quantity': int(it.group(2))})
        self.responseData['items'] = items