from cwbot.modules.BaseHoboModule import BaseHoboModule, eventFilter
from cwbot.util.textProcessing import stringToBool
from itertools import chain
from collections import defaultdict, Counter

def ditem(itname, 
          itregex, 
          itarea, 
          qty=1, 
          unlockedRegex=None, 
          lockedText=None,
          acquireText=None):
    return {'name': itname, 
            'regex': itregex, 
            'area': itarea,
            'unlocked_regex': unlockedRegex,
            'locked_text': lockedText, 
            'qty': qty,
            'acquire_text': acquireText if acquireText else itregex}

class DreadUniquesModule(BaseHoboModule):
    """ 
    Displays which per-instance items are still in Dreadsylvania
    
    Configuration options:
    
    announce - if new items should be announced (True)
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
                        "got a Dreadsylvanian auditor's badge", 
                        "Cabin: need Replica Key")],
              1: [ditem('gallows item', 
                        "(?:hung|hanged) a clanmate", 
                        "Square: coordinated @ gallows",
                        acquireText="picked up an item from the gallows"),
                  ditem('ghost pencil',
                        "collected a ghost pencil",
                        "Schoolhouse: in desk",
                        qty=10,
                        unlockedRegex="unlocked the schoolhouse",
                        lockedText="unlock Schoolhouse")],
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
        self._announce = None
        self._woodsDone = None
        self._villageDone = None
        self._castleDone = None
        self._woodsKilled = None
        self._villageKilled = None
        self._castleKilled = None
        self._locked = None
        self._claimed = None
        super(DreadUniquesModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._claimed = None
        self._processLog(initData)


    def _configure(self, config):
        self._announce = stringToBool(config.setdefault('announce', "True"))


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
        
        newClaimed = defaultdict(list)
        self._locked = {}
        userNames = {}
        for item in chain.from_iterable(self._areas.values()):
            # check if unlocked
            self._locked[item['name']] = (
                item['unlocked_regex'] is not None 
                and any(eventFilter(events, item['unlocked_regex'])))
            
            # see how many items were taken and who did it
            itemsAcquired = 0
            for e in eventFilter(events, item['regex']):
                newClaimed[item['name']].extend([e['userId']] * e['turns'])
                userNames[e['userId']] = e['userName']
                itemsAcquired += e['turns']

            # compare to old list and announce if specified in the options
            if self._claimed is not None:
                c1 = Counter(self._claimed.get(item['name'], []))
                c2 = Counter(newClaimed.get(item['name'], []))
                for k,v in c2.items():
                    numCollected = v - c1[k]
                    for _ in range(numCollected):
                        self.chat("{} {}.".format(userNames[k], 
                                                  item['acquire_text']))
        self._claimed = newClaimed
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["unique", "uniques"]:
            if not self._dungeonActive() or self._claimed is None:
                return ("Dreadsylvania has faded into the mist, along with "
                        "all its stuff. Don't you just hate when that "
                        "happens?")
            doneAreas = [self._woodsDone or self._woodsKilled >= 1000, 
                         self._villageDone or self._villageKilled >= 1000, 
                         self._castleDone or self._castleKilled >= 1000]
            messages = []
            qtyText = lambda x: "{}x ".format(x)
            for areaIdx, itemList in self._areas.items():
                if doneAreas[areaIdx]:
                    continue
                txt = []
                for item in itemList:
                    itemName = item['name']
                    numAvailable = item['qty'] - len(self._claimed[itemName])
                    if numAvailable == 0:
                        continue
                    if self._locked[itemName]:
                        txt.append("{}{} ({})".format(qtyText(numAvailable),
                                                      itemName, 
                                                      item['locked_text']))
                    else:
                        txt.append("{}{} ({})".format(qtyText(numAvailable),
                                                      itemName, 
                                                      item['area']))
                if txt:
                    messages.append("{}: {}."
                                    .format(self._areaNames[areaIdx],
                                            ", ".join(txt)))
            if messages:
                return "\n".join(messages)
            return ("Looks like adventurers have combed over Dreadsylvania "
                    "pretty well.")
        if cmd in ["pencil", "pencils"]:
            pencils = 10 - self._claimed['ghost pencil']
            pencilsLocked = self._locked['ghost pencil']
            if (pencils > 0 
                    and not self._villageDone 
                    and not self._villageKilled >= 1000):
                if pencilsLocked:
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
    