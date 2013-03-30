from kol.request.GenericRequest import GenericRequest
import re


class EffectRequest(GenericRequest):
    "Get a list of all effects on the character. Requires a SGEEA."

    def __init__(self, session):
        super(EffectRequest, self).__init__(session)
        self.url = session.serverURL + "uneffect.php"
        self.requestData["pwd"] = session.pwd

    def parseResponse(self):
        matches = re.findall(r'<input type=radio name=whicheffect value=(\d+)></td><td><img src[^>]+></td><td>(.*?) \(\d+ Adventure', self.responseText)
        self.responseData['effects'] = dict(matches)
        
        if re.search('''You don't have any more green fluffy antidote echo drops, or whatever they're called''', self.responseText) is not None:
            self.responseData['out'] = True
        else:
            self.responseData['out'] = False
            