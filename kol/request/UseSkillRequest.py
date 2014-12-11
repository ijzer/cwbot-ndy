from GenericRequest import GenericRequest
from kol.database import SkillDatabase
from kol.manager import PatternManager

class UseSkillRequest(GenericRequest):
    def __init__(self, session, skillId, numTimes=1, targetPlayer=None):
        super(UseSkillRequest, self).__init__(session)
        self.get = True
        self.url = session.serverURL + "runskillz.php"
        self.requestData["pwd"] = session.pwd
        self.requestData["action"] = "Skillz"
        self.requestData["whichskill"] = skillId
        self.requestData["ajax"] = 1
        self.requestData["quantity"] = numTimes
        if targetPlayer != None:
            self.requestData["targetplayer"] = targetPlayer
        else:
            self.requestData["targetplayer"] = session.userId

    def parseResponse(self):
        resultsPattern = PatternManager.getOrCompilePattern('results')
        match = resultsPattern.search(self.responseText)
        if match:
            results = match.group(1)
            self.responseData["results"] = results
