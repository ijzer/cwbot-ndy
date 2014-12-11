from kol.request.UseSkillRequest import UseSkillRequest
from kol.database import SkillDatabase
from kol.manager import PatternManager
from kol import Error
import re

class UseSkillRequestExtra(UseSkillRequest):
    _hc_ronin = re.compile(r"That player is in Hardcore mode, and cannot receive buffs from other players|That player cannot currently receive buffs from other players")
    _noskill = re.compile(r"You don't have that skill")
    _nouser = re.compile(r"Invalid target player selected")
    _ignoring = re.compile(r"You cannot target a player who has placed you on his or her ignore list")
    _tooManyATBuffs = re.compile(r"That player already has too many songs stuck in his \(or her\) head")
    
    def __init__(self, session, skillId, numTimes=1, targetPlayer=None):
        super(UseSkillRequestExtra, self).__init__(session, skillId, numTimes, targetPlayer)

    def parseResponse(self):
        resultsPattern = PatternManager.getOrCompilePattern('results')

        if self._hc_ronin.search(self.responseText) is not None:
            raise Error.Error("Unable to cast spell. "
                              "User is in Hardcore/Ronin.", 
                              Error.USER_IN_HARDCORE_RONIN)
        if self._noskill.search(self.responseText) is not None:
            raise Error.Error("Unable to cast spell. I don't know it.",
                              Error.INVALID_ITEM)
        if self._nouser.search(self.responseText) is not None:
            raise Error.Error("Unable to cast spell. No such user.",
                              Error.INVALID_USER)
        if self._ignoring.search(self.responseText) is not None:
            raise Error.Error("Unable to cast spell. User is ignoring us.",
                              Error.USER_IS_IGNORING)
        if self._tooManyATBuffs.search(self.responseText) is not None:
            raise Error.Error("Unable to cast spell. User has too many "
                              "songs in his/her head.",
                              Error.LIMIT_REACHED)

        match = resultsPattern.search(self.responseText)
        if match:
            results = match.group(1)
            self.responseData["results"] = results
