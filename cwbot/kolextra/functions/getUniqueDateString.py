from kol.request.StatusRequest import StatusRequest
from cwbot.util.tryRequest import tryRequest
    
def getUniqueDateString(session):
    r = StatusRequest(session)
    d = tryRequest(r)
    s = str(d['rollover'])
    return s
