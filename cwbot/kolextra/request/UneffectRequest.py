from kol.request.GenericRequest import GenericRequest
from kol.manager import PatternManager
from cwbot.locks import InventoryLock


class UneffectRequest(GenericRequest):
    """Uses a soft green echo eyedrop antidote to remove any effect.
    Modified to use InventoryLock and does not throw. """

    def __init__(self, session, effectId):
        super(UneffectRequest, self).__init__(session)
        self.url = session.serverURL + "uneffect.php"
        self.requestData["using"] = "Yep."
        self.requestData["pwd"] = session.pwd
        self.requestData["whicheffect"] = effectId

    def doRequest(self):
        with InventoryLock.lock:
            return super(UneffectRequest, self).doRequest()

    def parseResponse(self):
        # Check for errors.
        effectRemovedPattern = PatternManager.getOrCompilePattern('effectRemoved')
        if effectRemovedPattern.search(self.responseText):
            self.responseData['result'] = 'Effect removed.'
            return

        youDontHaveThatEffectPattern = PatternManager.getOrCompilePattern('youDontHaveThatEffect')
        if youDontHaveThatEffectPattern.search(self.responseText):
            self.responseData['result'] = "I don't seem to have effect number {}.".format(self.requestData['whicheffect'])
            return

        youDontHaveSGEEAPattern = PatternManager.getOrCompilePattern('youDontHaveSGEEA')
        if youDontHaveSGEEAPattern.search(self.responseText):
            self.responseData['result'] = "I am out of SGEEAs. Please help and send me a few!"
            return
        
        self.responseData['result'] = "An unknown error occurred while trying to remove an effect."
