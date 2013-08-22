from cwbot.modules.BaseDungeonModule import (BaseDungeonModule, eventFilter,
                                             eventDbMatch)
from cwbot.util.textProcessing import stringToList
from cwbot.common.exceptions import FatalError
from math import log

def dreadPercent(n):
    if n >= 1000:
        return "BOSS"
    return "{}%".format(max(0, min(99, int(n/10))))


class DreadOverviewModule(BaseDungeonModule):
    """ 
    Displays an overview of Dreadsylvania.
    NOTE: SHOULD BE HIGHER PRIORITY THAN OTHER MODULES IN DREADSYLVANIA
    
    Options:
        update-percent: comma-separated list of percent values to 
                        update progress on zones (25, 50, 75, 90)
        p_error: floating point probability of error between 0 and 1.
                 setting this lower will reduce the probability of a "miscall"
                 on which side is dominant in a Dreadsylvania area, at the
                 cost of taking longer to actually decide which side is
                 leading. 
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-overview"

    _balanceLetters = {0: ['W', 'B'], 1: ['Z', 'G'], 2: ['V', 'S']}
    _monsters = ["werewolf", "bugbear", "zombie", 
                 "ghost", "vampire", "skeleton"]
    _plurals = {'werewolf': "werewolves", 'bugbear': "bugbears",
                'zombie': "zombies", 'ghost': "ghosts",
                'vampire': "vampires", 'skeleton': "skeletons"}
    _areas = ["The Woods", "The Village", "The Castle"]
    
    def __init__(self, manager, identity, config):
        self._done = None
        self._killed = None # kills by area
        self._kills = None # kills by monster type
        self._defeats = None # defeats by monster type
        self._balance = None
        self._banished = None
        self._level = None
        self._drunk = None
        self._kisses = None
        self._lockedAreas = None
        self._locked = None
        self._notifyPercent = None
        self._logLikelihoodRatio = None # for sequential likelihood ratio tests
        self._likelihoodCalled = None
        self._perror = None
        
        super(DreadOverviewModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._lockedAreas = [r for r in self._db if r['zone'] == "(unlock)"]
        self._logLikelihoodRatio = state['likelihood']
        self._likelihoodCalled = state['decided']
        self._kills = {}
        self._processLog(initData)
        
    
    def _configure(self, config):
        try:
            self._notifyPercent = map(int, stringToList(
                                            config.setdefault('update-percent',
                                                        "25,50,75,90,100")))
        except ValueError:
            raise FatalError("update-percent must be a list of integers")
        try:
            self._perror = float(config.setdefault("p_error", "0.001"))
            if not 0 < self._perror < 1:
                raise ValueError()
        except ValueError:
            raise FatalError("p_error must be a float between 0 and 1")


    def _areaInfo(self, areaNum):
        d = {}
        d['index'] = areaNum
        d['accessible'] = self._drunk >= areaNum * 1000
        d['killed'] = self._killed[areaNum]
        d['done'] = self._done[areaNum]
        d['balance'] = self._balance[areaNum]
        if d['balance'] == 0:
            d['balanceWinning'] = ""
        else:
            idx = 1 if d['balance'] < 0 else 0
            d['balanceWinning'] = self._balanceLetters[areaNum][idx]
        d['level'] = self._level[areaNum]
        d['fullname'] = self._areas[areaNum]
        d['name'] = d['fullname'][4:]
        d['locked'] = [a['subzone'] for a in self._locked
                       if a['category'] == d['fullname']]
        d['status'] = ("done" if d['done']
                       else "boss" if d['killed'] >= 1000
                       else "open" if d['accessible']
                       else "locked")
        return d
    
    
    def getTag(self, areaNum):
        d = self._areaInfo(areaNum)
        # area
        txt = d['name']
        
        # completion
        if d['done']:
            return txt + " done"
        if d['level'] > 1:
            txt += "({})".format(d['level'])
        if d['killed'] >= 1000:
            txt += " BOSS "
        else:
            txt += " {}% ".format(int(d['killed']/10))
            
        calledStr = "?"
        n = self._likelihoodCalled[areaNum]
        if n is not None:
            calledStr = self._balanceLetters[areaNum][n]

        banishA = self._banished[self._monsters[2*areaNum]]
        banishB = self._banished[self._monsters[2*areaNum+1]]
        
        letterA, letterB = tuple(self._balanceLetters[areaNum])
        
        txtA = {0: letterA + letterA,
                1: "-" + letterA,
                2: "--"}[banishA]
        txtB = {0: letterB + letterB,
                1: letterB + "-",
                2: "--"}[banishB]
        txt += "[" + txtA + calledStr + txtB + "]"
        return txt
    
    
    def _doLRT(self, oldBanished, oldKills, oldDefeats):
        # determine which monster is more numerous using the
        # sequential likelihood ratio test
        # but ignore the kills if the banishments have just changed
        oldEncounters = None
        if oldKills is not None and oldDefeats is not None:
            oldEncounters = {m: oldKills.get(m, 0) + oldDefeats.get(m, 0)
                             for m in self._monsters}
        for i in range(3):
            printRatio = False
            
            monsterA = self._monsters[2*i]
            monsterB = self._monsters[2*i+1]
            monsters = [monsterA, monsterB] 
            
            banish = {m: self._banished[m] for m in monsters}
                
            if (oldBanished is None
                    or self._killed[i] > 1000
                    or self._done[i]):
                pass
            elif all(banish[m] == oldBanished[m] for m in monsters):
                useTotal = (sum(banish.values()) == 0)
                if useTotal:
                    oldEncounters[monsterA] = 0
                    oldEncounters[monsterB] = 0

                newEncounters = {m: self._kills[m] 
                                    + self._defeats[m] 
                                    - oldEncounters[m]
                                 for m in monsters}
                
                # initial probability of monster A is 0.6 or 0.4
                # BOTH probabilities below are the probability of an A 
                # appearing; one of the two probabilities is correct
                
                probFavoring = {monsterA: (3.0 - banish[monsterA]) 
                                          / (5.0 - sum(banish.values())),
                                monsterB: (2.0 - banish[monsterA]) 
                                          / (5.0 - sum(banish.values()))}

                # make sure the probability of killing the "wrong" monster
                # is non-zero (somebody might be in a fight or something!)

                probFavoring = {k: min(max(0.05, v), 0.95)
                                for k,v in probFavoring.items()}                
                
                # probabilities of these kills (newKillsA and newKillsB)
                # under both assumptions
                
                logProb = {m: newEncounters[monsterA]*log(probFavoring[m])
                              + newEncounters[monsterB]*log(1-probFavoring[m])
                           for m in monsters}

                oldRatio = self._logLikelihoodRatio[i]
                if useTotal:
                    self._logLikelihoodRatio[i] = 0
                self._logLikelihoodRatio[i] += logProb[monsterA]
                self._logLikelihoodRatio[i] -= logProb[monsterB]
                if oldRatio != self._logLikelihoodRatio[i]:
                    self.debugLog("Area {}: {} kills [{}, {}], "
                                  "ratio {} -> {}"
                                  .format(i, 
                                          "total" if useTotal else "new",
                                          newEncounters[monsterA], 
                                          newEncounters[monsterB],
                                          oldRatio, 
                                          self._logLikelihoodRatio[i]))
                
                oldCalled = self._likelihoodCalled[i]
                eta = log((1 - self._perror) / self._perror)
                if self._logLikelihoodRatio[i] > eta:
                    self._likelihoodCalled[i] = 0
                elif self._logLikelihoodRatio[i] < -eta:
                    self._likelihoodCalled[i] = 1
                elif abs(self._logLikelihoodRatio[i]) < 0.5 * eta:
                    self._likelihoodCalled[i] = None
                if (oldCalled != self._likelihoodCalled[i]
                        and self._likelihoodCalled[i] is not None):
                    printRatio = True
                    self.log("Called area {} for monster {}"
                             .format(i, self._likelihoodCalled[i]))
            else:
                self.debugLog("Different banishments, skipping LRT...")
                if (self._likelihoodCalled[i] is None
                        and sum(banish.values()) > 0):
                    self.chat("I don't know the distribution of {} to {} yet."
                              .format(monsterA, monsterB))
                elif sum(banish.values()) > 0:
                    printRatio = True
            if printRatio:
                a,b = (3,2) if self._likelihoodCalled[i] == 0 else (2,3)
                self.chat("The distribution of {} to {} is "
                          "currently {}:{}."
                          .format(self._plurals[monsterA], 
                                  self._plurals[monsterB], 
                                  a - banish[monsterA], 
                                  b - banish[monsterB]))


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._done = [any(eventDbMatch(events, 
                                       {'category': self._areas[i], 
                                        'zone': "(combat)",
                                        'subzone': "boss"}))
                      for i in range(3)]
        self._drunk = raidlog['dread']['drunkenness']
        
        newKilled = [raidlog['dread'].get('forest', 0),
                     raidlog['dread'].get('village', 0),
                     raidlog['dread'].get('castle', 0)]
        areaNames = ["Woods are", "Village is", "Castle is"]
        if self._killed is not None:
            for old,new,area in zip(self._killed, newKilled, areaNames):
                for threshold in self._notifyPercent:
                    if old < 10*threshold <= new:
                        self.chat("The {} {}% complete.".format(area,
                                                                int(new/10)))
                        break
        self._killed = newKilled

        oldKills = self._kills
        oldDefeats = self._defeats
        oldBanished = self._banished
        self._banished = {} 
        self._kills = {}      
        self._defeats = {}  
        prefix = r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+'
        prefixDef = r'was defeated by\s+(?:hot|cold|spooky|stench|sleaze)\s+'
        for monster in self._monsters:
            self._kills[monster] = (
                sum(e['turns'] for e in eventFilter(events, 
                                                    prefix + monster)))
            self._defeats[monster] = (
                sum(e['turns'] for e in eventFilter(events, 
                                                    prefixDef + monster)))
            self._banished[monster] = (
                sum(e['turns'] for e in eventFilter(events,
                            "drove some " + self._plurals[monster])))
            
        # do likelihood ratio test to determine which monsters are more
        # populous
        self._doLRT(oldBanished, oldKills, oldDefeats)
                        
        self._balance = {i: (self._kills[self._monsters[2*i]]
                             - self._kills[self._monsters[2*i+1]])
                         for i in range(3)}
        
        self._level = [1 + sum(e['turns'] 
                               for e in eventFilter(events, 
                                                    "made the " + a + " less"))
                       for a in ["forest", "village", "castle"]]
        
        self._kisses = raidlog['dread'].get('kisses', 0)
        
        self._locked = []
        for area in self._lockedAreas:
            if not any(eventDbMatch(events, area)):
                self._locked.append(area)
        return True
    
    
    @property
    def state(self):
        return {'likelihood': self._logLikelihoodRatio,
                'decided': self._likelihoodCalled}
    
    
    @property
    def initialState(self):
        return {'likelihood': [0, 0, 0],
                'decided': [None, None, None]}

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["dread", "dreadsylvania", "status", "summary"]:
            if not self._dungeonActive():
                return ("Dreadsylvania has disappeared for this century.")
            wtxt = "Woods done"
            vtxt = "Village done"
            ctxt = "Castle done"
            ktxt = "{} kisses".format(self._kisses)

            if not self._done[2]:
                if self._drunk < 2000:
                    ctxt = ("[+{} drunk to open Castle]"
                            .format(2000 - self._drunk))
                else:
                    ctxt = self.getTag(2)

            if not self._done[1]:
                if self._drunk < 1000:
                    vtxt = ("[+{} drunk to open Village]"
                            .format(1000 - self._drunk))
                    if not self._done[2]:
                        ctxt = "[Castle closed]"
                else:
                    vtxt = self.getTag(1)
                    
            if not self._done[0]:
                wtxt = self.getTag(0)
            txt = ", ".join([ktxt, wtxt, vtxt, ctxt])
            return txt
        return None
    
    
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            self._eventReply(self.state)
        elif s == "dread":
            style = 'list'
            keys = None
            if eData.data:
                style = eData.data.get('style', 'list')
                keys = eData.data.get('keys', None)
            dFilter = lambda x: x
            if keys:
                dFilter = lambda x: {k: x[k] for k in keys}
            
            dreadData = [self._areaInfo(areaNum) for areaNum in range(3)]
            filteredData = [dFilter(d) for d in dreadData]

            if style == 'dict':
                self._eventReply({dreadData[idx]['fullname']: 
                                       filteredData[idx] 
                                  for idx in range(len(dreadData))})
            elif style == 'list':
                self._eventReply(dreadData)
            else:
                raise IndexError("invalid dread event style")
                
                
    def _availableCommands(self):
        return {'status': "!status: Display an overview of Dreadsylvania."}
    