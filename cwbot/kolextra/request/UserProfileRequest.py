from kol.request.GenericRequest import GenericRequest
from kol.manager import PatternManager
import re
from datetime import date


class UserProfileRequest(GenericRequest):
    _playerClanPattern = re.compile(r'Clan: <b><a class=nounder href="showclan\.php\?whichclan=([0-9]+)">(.*?)<\/a>(?:</b><br>Title:\s*<b>(.*?)</b>)?')
    _datePattern = re.compile(r'Last Login:</b></td><td>([^<]+)</td>')
    _astralSpiritPattern = re.compile(r'<br>Astral Spirit</td>')
    
    def __init__(self, session, playerId):
        super(UserProfileRequest, self).__init__(session)
        self.url = session.serverURL + "showplayer.php"
        self.requestData["who"] = playerId
    
    def parseResponse(self):
        if self._astralSpiritPattern.search(self.responseText):
            self.responseData["astralSpirit"] = True
        else:
            self.responseData["astralSpirit"] = False
        
        match = self._datePattern.search(self.responseText)
        if match:
            s = match.group(1).split()
            # pull month from dict, since I don't want to deal with locales
            month = {'January': 1,
                     'February': 2,
                     'March': 3,
                     'April': 4,
                     'May': 5,
                     'June': 6,
                     'July': 7,
                     'August': 8,
                     'September': 9,
                     'October': 10,
                     'November': 11,
                     'December': 12}[s[0]]
            lastLoginDate = date(int(s[2]), month, int(s[1][:-1]))
            self.responseData["lastLogin"] = lastLoginDate
        
        usernamePattern = PatternManager.getOrCompilePattern('profileUserName')
        match = usernamePattern.search(self.responseText)
        self.responseData["userName"] = match.group(1)

        match = self._playerClanPattern.search(self.responseText)
        if match:
            self.responseData["clanId"] = int(match.group(1))
            self.responseData["clanName"] = match.group(2)
            self.responseData["clanTitle"] = match.group(3)

        numberAscensionsPattern = PatternManager.getOrCompilePattern('profileNumAscensions')
        match = numberAscensionsPattern.search(self.responseText)
        if match:
            self.responseData["numAscensions"] = int(match.group(1))
        else:
            self.responseData["numAscensions"] = 0

        numberTrophiesPattern = PatternManager.getOrCompilePattern('profileNumTrophies')
        match = numberTrophiesPattern.search(self.responseText)
        if match:
            self.responseData["numTrophies"] = int(match.group(1))
        else:
            self.responseData["numTrophies"] = 0

        numberTattoosPattern = PatternManager.getOrCompilePattern('profileNumTattoos')
        match = numberTattoosPattern.search(self.responseText)
        if match:
            self.responseData["numTattoos"] = int(match.group(1))
        else:
            self.responseData["numTattoos"] = 0
