from kol.request.GenericRequest import GenericRequest
from kol.manager import PatternManager

def _nameKey(x):
    return "".join(x.split()).strip().lower()

class ClanDungeonLootRequest(GenericRequest):
    _hoboLoot = ["Ol' Scratch's ash can","Ol' Scratch's ol' britches","Ol' Scratch's stovepipe hat","Ol' Scratch's infernal pitchfork","Ol' Scratch's manacles","Ol' Scratch's stove door",
                 "Frosty's carrot","Frosty's nailbat","Frosty's old silk hat","Frosty's arm","Frosty's iceball","Frosty's snowball sack",
                 "Oscus's dumpster waders","Oscus's pelt","Wand of Oscus","Oscus's flypaper pants","Oscus's garbage can lid","Oscus's neverending soda",
                 "Zombo's grievous greaves","Zombo's shield","Zombo's skullcap","Zombo's empty eye","Zombo's shoulder blade","Zombo's skull ring",
                 "Chester's bag of candy","Chester's cutoffs","Chester's moustache","Chester's Aquarius medallion","Chester's muscle shirt","Chester's sunglasses",
                 "Hodgman's bow tie","Hodgman's porkpie hat","Hodgman's lobsterskin pants","Hodgman's almanac","Hodgman's lucky sock","Hodgman's metal detector","Hodgman's varcolac paw","Hodgman's harmonica","Hodgman's garbage sticker","Hodgman's cane","Hodgman's whackin' stick","Hodgman's disgusting technicolor overcoat","Hodgman's imaginary hamster"]
    _slimeLoot = ["hardened slime belt","hardened slime hat","hardened slime pants","slime-soaked brain","slime-soaked hypophysis","slime-soaked sweat gland","caustic slime nodule","squirming Slime larva"]
    _dreadLoot = ["Great Wolf's headband","Great Wolf's right paw","Great Wolf's left paw","Great Wolf's lice","Great Wolf's rocket launcher","Great Wolf's beastly trousers",#"Hunger Sauce",
                  "Drapes-You-Regally","Warms-Your-Tush","Covers-Your-Head","Protects-Your-Junk","Quiets-Your-Steps","Helps-You-Sleep","Gets-You-Drunk",
                  "Mayor Ghost's khakis","Mayor Ghost's cloak","Mayor Ghost's toupee","Mayor Ghost's scissors","Mayor Ghost's sash","Mayor Ghost's gavel","ghost pepper",
                  "zombie mariachi hat","zombie accordion","zombie mariachi pants","HOA regulation book","HOA zombie eyes","HOA citation pad","wriggling severed nose",
                  "skull capacitor","electric Kool-Aid","Unkillable Skeleton's shield","Unkillable Skeleton's sawsword","Unkillable Skeleton's restless leg","Unkillable Skeleton's skullcap","Unkillable Skeleton's shinguards","Unkillable Skeleton's breastplate",
                  "Thunkula's drinking cap","Drunkula's silky pants","Drunkula's cape","Drunkula's ring of haze","Drunkula's wineglass","Drunkula's bell","bottle of Bloodweiser"]
    _dreadHardLoot = {"wolf" : ["Great Wolf's lice", "Great Wolf's rocket launcher", "Great Wolf's beastly trousers"],
                      "falls-from-sky" : ["Protects-Your-Junk", "Quiets-Your-Steps", "Helps-You-Sleep"],
                      "mayor" : ["Mayor Ghost's scissors", "Mayor Ghost's sash", "Mayor Ghost's gavel"],
                      "zha" : ["HOA regulation book", "HOA zombie eyes", "HOA citation pad"],
                      "skeleton" : ["Unkillable Skeleton's shield", "Unkillable Skeleton's sawsword", "Unkillable Skeleton's restless leg"],
                      "drunkula" : ["Drunkula's ring of haze", "Drunkula's wineglass", "Drunkula's bell"]
                      }
    def __init__(self, session):
        super(ClanDungeonLootRequest, self).__init__(session)
        self.session = session
        self.url = session.serverURL + "clan_basement.php"
        self.requestData['fromabove'] = 1

    def parseResponse(self):
        dungeonUndistributedLootPattern = PatternManager.getOrCompilePattern("dungeonUndistributedLoot")
        hardMode = {"wolf": None,
                    "falls-from-sky": None,
                    "mayor": None,
                    "zha": None,
                    "skeleton": None,
                    "drunkula": None}
        dread = []
        hobo = []
        slime = []
        for match in dungeonUndistributedLootPattern.finditer(self.responseText):
            item = match.group(1)
            if item in self._slimeLoot:
                slime.append(item)
            elif item in self._hoboLoot:
                hobo.append(item)
            elif item in self._dreadLoot:
                dread.append(item)
                for boss, drops in self._dreadHardLoot.items():
                    if item in drops:
                        hardMode[boss] = _nameKey(match.group(2))

        self.responseData["hardMode"] = hardMode
        self.responseData["slime"] = slime
        self.responseData["hobo"] = hobo
        self.responseData["dread"] = dread