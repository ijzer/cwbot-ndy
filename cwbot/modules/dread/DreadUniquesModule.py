from cwbot.modules.BaseHoboModule import BaseHoboModule, eventFilter
from itertools import chain

def ditem(itname, itregex, itarea):
    return {'name': itname, 'regex': itregex, 'area': itarea}

class DreadUniquesModule(BaseHoboModule):
    """ 
    Displays which per-instance items are still in Dreadsylvania
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-uniques"
    
    _areaNames = ["Woods", "Village", "Castle"]
    _areas = {0: [ditem('moon-amber', 
                        "acquired a chunk of moon-amber", 
                        "Tree: Mus. only"),
                  ditem('blood kiwi', 
                        "got a blood kiwi", 
                        "Tree: coordinated w/ Mus. only"),
                  ditem("Auditor's badge", 
                        "UNKNOWN", 
                        "Cabin: need Replica Key")],
              1: [ditem('clockwork key', 
                        "(?:hung|hanged) a clanmate", 
                        "Square: coordinated @ gallows")],
              2: [ditem('dreadful roast', 
                        "got some roast beast", 
                        "Hall: dining room"),
                  ditem('wax banana',
                        "got a wax banana",
                        "Hall: dining room"),
                  ditem('stinking agaricus',
                        "got some stinking agaric",
                        "Dungeon: guardroom")]}
    
    def __init__(self, manager, identity, config):
        self._woodsDone = None
        self._villageDone = None
        self._castleDone = None
        self._woodsKilled = None
        self._villageKilled = None
        self._castleKilled = None
        self._available = None
        self._pencils = None
        self._pencilsUnlocked = None
        super(DreadUniquesModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._processLog(initData)


    @property
    def state(self):
        return {}

    
    @property
    def initialState(self):
        return {}

    
    def getTag(self):
        return ""


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._woodsDone   = any(eventFilter(events, 
            r"""(?i)defeated\s+(The Great Wolf of the Air|Falls-From-Sky)"""))
        self._villageDone = any(eventFilter(events, 
            r"""(?i)defeated\s+(the Zombie Homeowners' Association|Mayor Ghost)"""))
        self._castleDone  = any(eventFilter(events, 
            r"""(?i)defeated\s+(The Unkillable Skeleton|Count Drunkula)"""))
        self._woodsKilled   = raidlog['dread'].get('forest', 0)
        self._villageKilled = raidlog['dread'].get('village', 0)
        self._castleKilled  = raidlog['dread'].get('castle', 0)
        self._available = set([])
        for item in chain.from_iterable(self._areas.values()):
            if not any(eventFilter(events, item['regex'])):
                self._available.add(item['name'])
        self._pencils = 10 - sum(e['turns'] for e in eventFilter(events, 
                                                r'collected a ghost pencil'))
        self._pencilsUnlocked = any(eventFilter(events, 
                                                "unlocked the schoolhouse"))
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["unique", "uniques"]:
            if not self._dungeonActive():
                return ("Dreadsylvania has faded into the mist, along with "
                        "all its stuff. Don't you just hate when that "
                        "happens?")
            doneAreas = [self._woodsDone or self._woodsKilled >= 1000, 
                         self._villageDone or self._villageKilled >= 1000, 
                         self._castleDone or self._castleKilled >= 1000]
            messages = []
            
            for areaIdx, itemList in self._areas.items():
                if doneAreas[areaIdx]:
                    continue
                txt = []
                for item in itemList:
                    if item['name'] in self._available:
                        txt.append("{} ({})"
                                   .format(item['name'], item['area']))
                if areaIdx == 1 and self._pencils > 0:
                    if not self._pencilsUnlocked:
                        txt.append("10 ghost pencils (unlock Schoolhouse)")
                    else:
                        txt.append("{} ghost pencils (Schoolhouse: in desk)"
                                   .format(self._pencils))
                if txt:
                    messages.append("{}: {}"
                                    .format(self._areaNames[areaIdx],
                                            ", ".join(txt)))
            if messages:
                return "\n".join(messages)
            return ("Looks like adventurers have combed over Dreadsylvania "
                    "pretty well.")
        if cmd in ["pencil", "pencils"]:
            if self._pencils > 0:
                if not self._pencilsUnlocked:
                    return ("10 ghost pencils remaining "
                            "(unlock the Schoolhouse).")
                else:
                    return ("{} ghost pencils remaining (desk in the Village "
                               "Square Schoolhouse).".format(self._pencils))
            return "No ghost pencils remaining."
        return None
        
                
    def _availableCommands(self):
        return {'uniques': "!uniques: Show which Dreadsylvanian unique items "
                            "are still available.",
                'pencils': "!pencils: Show how many ghost pencils are left."}
    