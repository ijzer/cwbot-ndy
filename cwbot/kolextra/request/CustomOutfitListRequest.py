import re
from kol.request.GenericRequest import GenericRequest


class CustomOutfitListRequest(GenericRequest):
    """Gets a list of custom outfits"""
    _matcher = re.compile(r'(?i)<b>#(\d+)</b></td><td><input type=text class=text size=30 name=name(?:\d*) value="([^"]+)"></td><td align=center><input type=checkbox name=delete(?:\d*)></td></tr><tr><td></td><td class=tiny><center><b>Contents:</b></centeR>(.*?)<br>(?:<br>)?</td>', re.IGNORECASE)

    def __init__(self, session):
        super(CustomOutfitListRequest, self).__init__(session)
        self.url = session.serverURL + "account_manageoutfits.php"
        self.requestData["pwd"] = session.pwd


    def doRequest(self):
        super(CustomOutfitListRequest, self).doRequest()
        
        self.responseData['outfits'] = []
        matches = self._matcher.findall(self.responseText)
        for outfitId, outfitName, equipmentText in matches:
            equipment = equipmentText.split("<br>")
            self.responseData['outfits'].append(
                {'id': int(outfitId),
                 'name': outfitName.strip(),
                 'equipment': [e.strip() for e in equipment 
                               if e.strip() != ""]})
        return self.responseData