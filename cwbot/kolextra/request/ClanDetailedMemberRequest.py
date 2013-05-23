from kol.request.GenericRequest import GenericRequest
import re

class ClanDetailedMemberRequest(GenericRequest):
    "Retrieves information from the clan detailed member list page."
    _matcher = re.compile(r'<tr>.*?"showplayer\.php\?who=(\d+)"><b>(.*?)</b>.*?<td.*?>([^<>]*?)</td><td[^>]*>(\d+)</td></tr>')


    def __init__(self, session):
        super(ClanDetailedMemberRequest, self).__init__(session)
        self.url = session.serverURL + "clan_detailedroster.php"

    def parseResponse(self):
        members = []
        for match in self._matcher.finditer(self.responseText):
            member = {}
            member["userId"] = int(match.group(1))
            member["userName"] = match.group(2)
            member["rankName"] = match.group(3)
            member["karma"] = int(match.group(4)) 
            members.append(member)

        self.responseData["members"] = members

