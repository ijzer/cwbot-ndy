from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter


def moshCount(events):
    return sum(m['turns'] for m in eventFilter(
            events, r'mosh pits? in the tent'))

def buskCount(events):
    return sum(b['turns'] for b in eventFilter(
            events, "passed the hat in the tent"))

def ruinCount(events):
    return sum(r['turns'] for r in eventFilter(events, r'ruined .* show'))

def stageCount(events):
    return sum(s['turns'] for s in eventFilter(events, "took the stage"))

def uniqueStagePlayers(events):
    players = set(s['userId'] for s in eventFilter(events, "took the stage"))
    return len(players)
    

UNKNOWN = 0
GUESSED = 1
KNOWN = 2
def guessStr(n):
    return {UNKNOWN: "unknown",
            GUESSED: "guessed",
            KNOWN: "known"}[n]


def getMoshDamage(n):
    """ Amount of damage from a mosh with N players on stage """
    if n > 6 or n < 1:
        raise Exception("Invalid n={}".format(n))
    return [5,10,20,40,64,100][n-1]

class TownStageModule(BaseDungeonModule):
    """ 
    A module that keeps track of the stage in town square, including getting
    on/off stage, mosh damage, and busking .Players do not directly communicate
    with this module; instead, the TownModule passes events to get information
    from this module. However, the module does send chats when stage
    events occur.
    
    The module has three modes: KNOWN, GUESSED, and UNKNOWN. The module starts
    in KNOWN mode. In this mode, it can accurately track how many people are
    on stage and how much damage is done in moshes. 
    
    If the bot starts up and there's been a mosh/busk/show ruin since it
    last was online, it changes to UNKNOWN mode. Here it doesn't know if
    anyone is on stage. For now, this happens even if there haven't been
    100 hobos killed.
    
    The next time the stage is cleared, it reverts to GUESSED mode. At this
    time, it calculates the minimum amount of damage that could have happened
    due to moshing while it was offline, and adds that to the total killed.
    It's a crude approximation, but in normal operation the bot should not
    be offline to miss much stage activity.
    
    
    NOTE: This module must be loaded **before** the TownModule; it is a
    dependency. 
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "town_stage"
    
    # approximate values of dances
    def __init__(self, manager, identity, config):
        self._performers = None
        self._totalperformers = None
        self._moshes = [None] * 6
        self._stageClears = None
        self._guessState = None
        self._resumeData = None
        self._initialized = False
        self._lastTent = 10000
        super(TownStageModule, self).__init__(manager, identity, config)


    def initialize(self, state, initData):
        self._processLog(initData)
        self._resumeData = state
        self._initialized = True
        
        # first, look for additional stage performances
        totalPerformances = self._stageClears
        oldPerformances = state['stageClears']
        self.log("Total performances: {}".format(totalPerformances))
        self._moshes = state['moshes']
        if totalPerformances == oldPerformances:
            # nothing has changed (except, possibly, the number of 
            # performers on stage, so let's add additional members on stage)
            self._performers = (state['performers'] 
                                + self._totalperformers 
                                - state['totalPerformers']) 
            # restore to previous known/guess/unknown state
            self._guessState = state['guessState']
            self.log("Same number of stage clears: guess state {}"
                     .format(guessStr(self._guessState)))
        else:
            self._performers = 0
            self._guessState = UNKNOWN
            self.log("Set guess UNKNOWN")


    @property
    def state(self):
        if self._guessState == UNKNOWN:
            return self._resumeData
        return {'performers': self._performers, 
                'totalPerformers': self._totalperformers,
                'moshes': self._moshes, 
                'stageClears': self._stageClears,
                'guessState': self._guessState}
        
    @property
    def initialState(self):
        return {'performers': 0, 
                'totalPerformers': 0,
                'moshes': [0] * 6, 
                'stageClears': 0,
                'guessState': KNOWN}
        
    
    def getDone(self):
        """ Get number of hobos killed due to moshes """
        if not self._initialized:
            return None
        doneAmt = 0
        if len([item for item in self._moshes if item is None]) == 0:
            for i,d in zip(range(1,7), self._moshes):
                doneAmt += d*getMoshDamage(i)
        return doneAmt

    
    def getTag(self):
        """ get tag from TownModule """
        tagMsg = self._raiseEvent("tag", "town")
        if len(tagMsg) != 1:
            raise Exception("Invalid tag Event reply: {!s}".format(tagMsg))
        return tagMsg[0].data['tag']

    
    def _processLog(self, raidlog):
        events = raidlog['events']
        self._totalperformers = stageCount(events)
        self._stageClears = (buskCount(events) + ruinCount(events) 
                             + moshCount(events))
        return True
    
    
    def settleMoshes(self, newMosh, events):
        """ Figure out damage due to moshes. If newMosh == True, this means
        that another mosh has just occurred. If False, that means that the
        stage was just cleared without a new mosh. """
        if self._guessState != UNKNOWN:
            # we are not in unknown state. damage is simple calculation
            if not newMosh:
                return 0
            self._performers = max(1, self._performers)
            self._moshes[self._performers - 1] += 1
            return getMoshDamage(self._performers)
        else:
            self._guessState = GUESSED
            moshes = moshCount(events)
            newMoshes = moshes - sum(self._resumeData['moshes'])
            nonMoshes = self._stageClears - moshes
            newNonMoshes = nonMoshes - (self._resumeData['stageClears'] 
                                        - sum(self._resumeData['moshes']))
            self.log("Computed from state {}/moshes={}/stageclears={}: "
                     "newMoshes={}, newNonMoshes={}"
                     .format(self._resumeData, moshes, self._stageClears, 
                             newMoshes, newNonMoshes))
            if newMoshes == 0:
                self.log("No new moshes detected.")
                return 0
            
            playerDiff = (self._totalperformers 
                          - self._resumeData['totalPerformers'])
            moshVals = [1] * newMoshes
            if newMosh:
                moshVals[0] = self._performers
            
            # be as pessimistic as possible: each non-mosh had maximum number 
            # of players on stage
            maxStagePlayers = uniqueStagePlayers(events)
            playerDiff = (playerDiff - sum(moshVals) 
                          - maxStagePlayers * newNonMoshes)
            
            # any remaining positive value in playerDiff is assigned to moshes
            for _i in range(playerDiff):
                moshVals.sort()
                moshVals[0] += 1
                
            self.log("Determined moshes: {}".format(str(moshVals)))
            for item in moshVals:
                self._moshes[item - 1] += 1
            return getMoshDamage(max(moshVals))
            
    
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        events = raidlog['events']
        if "has taken the stage" in txt:
            self._performers += 1
            self._totalperformers += 1
            if self._guessState == UNKNOWN:
                return ("{} There are at least {} performers on stage."
                        .format(self.getTag(), self._performers))
            return ("{} There are {} performers on stage."
                    .format(self.getTag(), self._performers))
        elif ("taking the entire crowd" in txt or 
              "passed a hat in the tent" in txt):
            self.settleMoshes(False, events)
            self._performers = 0
        elif "got a mosh pit going in the tent, knocking" in txt:
            damage = self.settleMoshes(True, events)
            self._performers = 0
            return ("{} The moshing defeated {} hobos!"
                    .format(self.getTag(), damage))
        elif "got a mosh pit going in the tent" in txt:
            damage = self.settleMoshes(False, events)
            self._performers = 0
        return None
        
    
    def _processCommand(self, msg, cmd, args):
        return None

    
    def reset(self, _events):
        self._performers = 0
        self._totalperformers = 0
        self._moshes = [0] * 6
        self._stageClears = 0
        self._guessState = KNOWN
        self._resumeData = self.initialState
        
    
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "damage":
            self._eventReply({'damage': self.getDone(), 
                              'guess': self._guessState})
        elif s == "onstage":
            self._eventReply({'stage': self._performers, 
                              'guess': self._guessState})
        elif s == "state":
            self._eventReply(self.state)
    