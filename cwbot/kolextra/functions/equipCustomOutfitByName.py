from cwbot.kolextra.request.CustomOutfitListRequest import \
                            CustomOutfitListRequest
from cwbot.kolextra.request.OutfitEquipRequest import OutfitEquipRequest
from cwbot.util.tryRequest import tryRequest
from kol import Error

def equipCustomOutfitByName(session, outfitName):
    r1 = CustomOutfitListRequest(session)
    d1 = tryRequest(r1)
    matches = [item['id'] for item in d1['outfits']
               if item['name'].lower() == outfitName.lower()]
    if not matches:
        raise Error.Error("Invalid outfit name: {}".format(outfitName),
                          Error.INVALID_ACTION)
    r2 = OutfitEquipRequest(session, matches[0], True)
    d2 = tryRequest(r2, numTries=1)
    return d2