from kol.request.GenericRequest import GenericRequest
from kol.Error import Error
import re


class GetScareHoboPartsRequest(GenericRequest):
    """Get the list of Scarehobo parts available in Hobopolis. This does
    not require getting through the sewers. """

    def __init__(self, session):
        super(GetScareHoboPartsRequest, self).__init__(session)
        self.url = session.serverURL + "clan_hobopolis.php"
        self.requestData["pwd"] = session.pwd
        self.requestData["place"] = "3"
        self.requestData["action"] = "talkrichard"
        self.requestData["whichtalk"] = "3"

    def parseResponse(self):
        t = self.responseText
        
        intConvert = lambda x: int(x[0].replace(",", "")) if len(x) > 0 else 0
        n1 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> pairs? of charred hobo boots.', t))
        n2 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> pairs? of frozen hobo eyes.', t))
        n3 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> piles? of stinking hobo guts.', t))
        n4 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> creepy hobo skulls?.', t))
        n5 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> hobo crotche?s?.', t))
        n6 = intConvert(re.findall(r'Richard has <b>([\d,]+)</b> hobo skins?.', t))
        self.responseData = {'parts': [n1,n2,n3,n4,n5,n6]}
        
        m = re.search(r'bandages|Richard|scarehobo', t)
        if m is None:
            raise Error("Failed to read scarehobo parts.")
