from kol.request.GenericRequest import GenericRequest
from cwbot.locks import KmailLock


class SaveMessagesRequest(GenericRequest):
    "A request used to save messages."

    def __init__(self, session, messagesToDelete, box="Inbox"):
        super(SaveMessagesRequest, self).__init__(session)
        self.url = session.serverURL + "messages.php"
        self.requestData["the_action"] = "save"
        self.requestData["pwd"] = session.pwd
        self.requestData["box"] = box

        for msgId in messagesToDelete:
            self.requestData["sel%s" % msgId] = "1"
    
    def doRequest(self):
        with KmailLock.lock:
            return super(SaveMessagesRequest, self).doRequest()
