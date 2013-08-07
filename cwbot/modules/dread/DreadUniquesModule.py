from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventDbMatch
from cwbot.common.exceptions import FatalError
from cwbot.util.textProcessing import stringToBool, toTypeOrNone
from collections import defaultdict, Counter


class DreadUniquesModule(BaseDungeonModule):
    """ 
    Displays which per-instance items are still in Dreadsylvania
    
    Configuration options:
    
    announce - if new items should be announced (True)
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-uniques"
    
    _areaNames = ["The Woods", "The Village", "The Castle"]
    
    def __init__(self, manager, identity, config):
        self._announce = None
        self._db = None
        self._dread = None
        self._uniques = None
        self._claimed = None
        super(DreadUniquesModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._claimed = None
        self._db = initData['event-db']
        self._uniques = [r for r in self._db if r['unique_type']]
        self._processLog(initData)


    def _configure(self, config):
        self._announce = stringToBool(config.setdefault('announce', "True"))


    @property
    def state(self):
        return {}

    
    @property
    def initialState(self):
        return {}

    
    def _processLog(self, raidlog):
        events = raidlog['events']
        
        # get dread status
        try:
            replies = self._raiseEvent("dread", "dread-overview", 
                                       data={'style': 'dict',
                                             'keys': ['status',
                                                      'index',
                                                      'locked']})
            self._dread = replies[0].data
        except IndexError:
            raise FatalError("DreadUniquesModule requires a "
                             "DreadOverviewModule with higher priority")

        newClaimed = defaultdict(list)
        userNames = {}
        for record in self._uniques:
            itemTxt = record['unique_text']
            quantity = toTypeOrNone(record['quantity'], int)
            if quantity is None:
                quantity = 1
            
            # see how many items were taken and who did it
            itemsAcquired = 0
            logMessage = ""
            for e in eventDbMatch(events, record):
                logMessage = e['event']
                newClaimed[itemTxt].extend([e['userId']] * e['turns'])
                userNames[e['userId']] = e['userName']
                itemsAcquired += e['turns']
            
            # compare to old list and announce if specified in the options
            if self._claimed is not None:
                # count up which users got this log message
                c1 = Counter(self._claimed.get(itemTxt, []))
                c2 = Counter(newClaimed.get(itemTxt, []))
                for k,v in c2.items():
                    # iterate through each user
                    numCollected = v - c1[k]
                    # print a pickup message for each time user X got item
                    # should be only once for dreadsylvania
                    for _ in range(numCollected):
                        self.chat("{} {} ({} remaining)."
                                  .format(userNames[k], 
                                          logMessage,
                                          quantity - itemsAcquired))
        self._claimed = newClaimed
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
    
    
    def _getUniqueData(self, typeList):
        for record in self._uniques:
            if record['unique_type'] not in typeList:
                continue     
            itemData = self._dread[record['category']]
            if itemData['status'] in ["done", "boss"]:
                continue

            quantity = toTypeOrNone(record['quantity'], int)
            if quantity is None:
                quantity = 1
            
            itemName = record['unique_text']
            numAvailable = (quantity - len(self._claimed[itemName]))
            if numAvailable <= 0:
                continue
            isLocked = (record['subzone'] in itemData['locked'])
            yield (record, numAvailable, isLocked)
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["unique", "uniques"]:
            if not self._dungeonActive() or self._claimed is None:
                return ("Dreadsylvania has faded into the mist, along with "
                        "all its stuff. Don't you just hate when that "
                        "happens?")
            messages = {}
            lockedTxt = {True: "LOCKED ", False: ""}
            areaItems = defaultdict(list)
            for record,available,locked in self._getUniqueData(['pencil', 
                                                                'unique', 
                                                                'uncommon']):
                areaItems[record['category']].append(
                                                (record, available,locked))
            for k,v in areaItems.items():
                itemTxt = []
                for record,available,locked in v:
                    quantity = toTypeOrNone(record['quantity'], int)
                    if quantity is None:
                        quantity = 1
                    
                    txt = ""
                    if quantity > 1:
                        txt += "{}x ".format(available)
                    txt += lockedTxt[locked]
                    txt += record['unique_text']
                    itemTxt.append(txt)
                messages[k] = "({}) {}".format(k[4:], ", ".join(itemTxt))
                    
            # get list of areas by index
            areas = dict((v['index'], k) for k,v in self._dread.items())
            txtSegments = []
            for idx in sorted(areas.keys()):
                areaname = areas[idx]
                if areaname in messages:
                    txtSegments.append(messages[areaname])
            txt = ["; ".join(txtSegments)]

            # show FKs
            fkTxt = []
            for record,available,locked in self._getUniqueData(['fk']):
                fkTxt.append("{} {}x{}".format(record['zone'],
                                               lockedTxt[locked],
                                               available))
            if fkTxt:
                txt.append("FKs available: {}".format(", ".join(fkTxt)))

            if txt:
                return "\n".join(txt)
            return ("Looks like adventurers have combed over Dreadsylvania "
                    "pretty well.")
        if cmd in ["pencil", "pencils"]:
            if not self._dungeonActive() or self._claimed is None:
                return ("Dreadsylvania has dissappeared once again, along "
                        "with its ghost pencil factory. You probably can't "
                        "find them in stores anymore.") 
            pencils = list(self._getUniqueData(['pencil']))
            if not pencils:
                return ("All the ghost pencils are gone. Now nobody can do "
                        "their ghost homework assignment from ghost math "
                        "class.")
            (_,available,locked) = pencils[0]
            if locked:
                return "The schoolhouse is still locked."
            return "{} pencils available.".format(available)
        return None
        
                
    def _availableCommands(self):
        return {'uniques': "!uniques: Show which Dreadsylvanian unique items "
                            "are still available."}    
        