import math
from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter


def killPercent(n):
    return int(max(0, min(99, 100*n / 500.0)))


class PldModule(BaseDungeonModule):
    """ 
    A module that tracks the club opening in the PLD. There is some persistent
    state here, because a barfight kills 10% of the remaining hobos in the
    area. So, if any barfights are missed while the bot if offline, the
    10% reduction is applied immediately. This means the bot will probably
    be underestimating the number of hobos killed.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "pld"
    
    def __init__(self, manager, identity, config):
        self._unpopularity = None # current unpopularity level 
        self._pldKilled = None # number of sleaze hobos killed
        self._pldFightDamage = None
        self._pldFights = None
        self._pldKnown = None
        self._pldDone = False
        self._pldOpen = False
        self._pldLastNotify = -10000
        super(PldModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._pldLastNotify = -10000
        self._pldDone = False
        self._open = state['open']
        self._processLog(initData)
        self.log("Detected {} sleaze kills".format(self._pldKilled))
        self._pldKnown = state['known']
        self._pldFightDamage = state['fightDamage']
        if self._pldFights > state['fights']:
            self._pldKnown = False
            fights = self._pldFights - state['fights']
            self._pldFightDamage = int(
                    math.floor((500 - self._pldKilled) * (1 - 0.9 ** fights) 
                               - 0.5 * fights))
            self.log("Detected {} surplus fights; estimating {} kills"
                     .format(fights, self._pldFightDamage))

    
    @property
    def state(self):
        return {'known': self._pldKnown,
                'fightDamage': self._pldFightDamage,
                'fights': self._pldFights,
                'killed': self._pldKilled,
                'open': self._open}

    
    @property
    def initialState(self):
        return {'known': True, 
                'fightDamage': 0, 
                'fights': 0, 
                'killed': 0, 
                'open': False}

    
    def getTag(self):
        if self._pldDone:
            return "[PLD done]"
        if not self._open:
            return "[PLD closed]"
        pldPercent = killPercent(self._pldFightDamage + self._pldKilled)
        estimateStr = "" if self._pldKnown else ">"
        return "[PLD {}{}%]".format(estimateStr, pldPercent) 

                
    def _processLog(self, raidlog):
        events = raidlog['events']
        # check stench hobos killed
        self._unpopularity = (  
                sum(u['turns'] for u in eventFilter(
                        events, "bamboozled some hobos", 
                        "flimflammed some hobos",
                        "diverted some cold water out of Exposure"))
                - sum(p['turns'] for p in eventFilter(
                        events, "danced like a superstar",
                        "diverted some steam away from Burnbarrel")))
        
        self._pldKilled = (      
                sum(k['turns'] for k in eventFilter(
                        events, r'defeated +Sleaze hobo'))
                - 6 * sum(d['turns'] for d in eventFilter(events, "dumpster")))

        self._pldFights = sum(f['turns'] for f in eventFilter(
                                  events, "barfight"))
            
        # if Chester is dead, set the heap to finished
        if self._pldKilled > 0 or self._pldFights > 0:
            self._open = True
        
        self._pldDone = any(eventFilter(events, r'defeated +Chester'))
        return True
            

    def displayProgress(self, alwaysDisplay=True):
        if self._pldLastNotify != self._unpopularity or alwaysDisplay:
            self._pldLastNotify = self._unpopularity
            if self._unpopularity >= 21:
                return ("{} Unpopularity: {}/21 (open)"
                        .format(self.getTag(), self._unpopularity))
            return ("{} Unpopularity: {}/21 (closed)"
                    .format(self.getTag(), self._unpopularity))
        return None


    def displayBrawl(self, damage):
        return ("{} {} hobos got beaten up in the barfight!"
                .format(self.getTag(), damage))

    
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if self._pldDone:
            return None

        if any(item in txt for item in 
                   ["bamboozled some hobos",
                    "flim-flammed some hobos",
                    "diverted some cold water out of Exposure Esplanade",
                    "did some dancing",
                    "diverted some steam"]):
            return self.displayProgress(False)
        if "started a brawl" in txt:
            killedSoFar = self._pldFightDamage + self._pldKilled
            remaining = 500 - killedSoFar
            newDamage = int(math.floor(0.1 * remaining))
            self._pldFightDamage += newDamage
            self.debugLog("{} remaining; brawl did {} damage -> total {}"
                          .format(remaining, newDamage, self._pldFightDamage))
            return self.displayBrawl(newDamage)
        return None
        

    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["pld", "nightclub"]:
            if not self._dungeonActive():
                return ("Hodgman is dead, so the lease on the nightclub "
                        "lapsed. It's a parking lot now.")
            if self._pldDone:
                return ("{} Chester is dead, so it's probably best if you "
                        "stay away from VGBND.".format(self.getTag()))
            return self.displayProgress()
        return None
        

    def _eventCallback(self, eData):
        s = eData.subject
        if s == "done":
            self._eventReply({'done': self.getTag()[1:-1]})
        elif s == "open":
            self._open = True
        elif s == "state":
            self._eventReply(self.state)


    def _availableCommands(self):
        return {'pld': "!pld: Display the popularity of the nightclub.",
                'nightclub': None}
