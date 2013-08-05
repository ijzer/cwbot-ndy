from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter


def killPercent(n):
    return int(max(0, min(99, 100*n / 500.0)))


def getTireDamage(n):
    return int(round(0.1*n*n + 0.7*n))

UNKNOWN = 0
GUESSED = 1
KNOWN = 2


class BurnbarrelModule(BaseDungeonModule):
    """ 
    A module that tracks the tire stack in Burnbarrel Blvd.
    This module is extremely complicated due to the stateful nature of
    Burnbarrel Blvd. Basically, there are 3 modes of operation:
    
    In KNOWN mode, the bot has been online to witness every tirevalanche.
    This means the bot can calculate how many tires were stacked for each
    one. Note that if the bot goes offline, it can still figure out how many
    tires it missed if there hasn't been a new tirevalanche by comparing the
    total number of tires when it logged off to the total number when it
    logged on. If the bot is in KNOWN mode, it can figure out exactly how many
    hoboes have been killed due to tirevalanches.
    
    If the bot misses a tirevalanche, then there's a 
    problem. How many of the missed tires were thrown on the stack before
    the tirevalanche, and how many after? There's no way to know. If the bot
    starts up and missed these events, it switches to UNKNOWN mode. It will
    now need to guess how many hoboes were killed in the previous
    tirevalanches. It does this by splitting the missed tires evenly among all
    of the tirevalanches it missed. This results in the lowest possible
    estimate of hoboes killed.
    
    The next time a tirevalanche occurs, it commits its estimate and upgrades
    itself to GUESSED mode. The bot assumes that its estimate is correct. The
    only difference between GUESSED and KNOWN is that it displays a > symbol
    in its tag to indicate a guessed value.  
    
    No configuration options.
    """    
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "burnbarrel"

    def __init__(self, manager, identity, config):
        self._hobosKilled = None # hobos defeated - 8 * doors opened
        self._tireDamage = None # sum of tirevalanche damage
        self._damageState = None

        self._open = False
        self._bbDone = False
        
        self._tires = None # tires on the stack (negative if Ol' Scratch dead)
        self._totalTires = None # total number of tires
        self._totalAvalanches = None # total number of tirevalanches

        self._resumeData = {} # holds data from last known state
        
        self._lastTireNotify = None
        super(BurnbarrelModule, self).__init__(manager, identity, config)

        
    def initTotals(self, events):
        """ get total tires/avalanches """
        self._totalTires = 0
        self._totalAvalanches = 0
        
        # detect number of avalanches
        self._totalAvalanches = sum(
                a['turns'] for a in eventFilter(events, "tirevalanche"))
        self._totalTires = sum(
                t['turns'] for t in eventFilter(events, r'tires? on the fire'))
        self.log("Detected {} avalanches".format(self._totalAvalanches))
        self.log("Detected {} tire tosses".format(self._totalTires))                
        
        
    def initialize(self, state, initData):
        # Burnbarrel Blvd is very complicated to work out if any 
        # tirevalanches were "missed" by the bot, since the damage depends 
        # on the size of the tire stack, which we don't have available. 
        # So the total damage needs to be estimated in that case.
        events = initData['events']

        # initialize
        self._bbDone = False
        self.initTotals(events)
        self._resumeData = state # hold on to a copy of the loaded state
        self._tireDamage = state['TireDamage']
        self._lastTireNotify = 0
        self._open = state['open']
        if not self._open:
            if any(item['category'] == 'Burnbarrel Blvd.' for item in events):
                self._open = True
        
        if self._totalAvalanches == state['Avalanches']:
            # yay, we missed nothing!
            self.log("No change in avalanches.")
            self._tires = (state['Tires'] 
                           + self._totalTires 
                           - state['TotalTires'])
            self.log("New tire count {}.".format(self._tires))
            self._damageState = state['DamageState']
        else:
            # uh oh, we missed avalanches
            self.log("Avalanches: before={}, after={}"
                     .format(state['Avalanches'], self._totalAvalanches))
            self._tires = 0
            self._damageState = UNKNOWN
        self._processLog(initData)

        
    @property
    def state(self):
        state = {}
        if self._damageState == UNKNOWN:
            # return old state -- we essentially haven't added any information
            return self._resumeData
        state['TotalTires'] = self._totalTires
        state['Tires'] = self._tires
        state['TireDamage'] = self._tireDamage
        state['DamageState'] = self._damageState
        state['Avalanches'] = self._totalAvalanches
        state['open'] = self._open
        return state

    
    @property
    def initialState(self):
        return {'TotalTires': 0, 
                'Tires': 0, 
                'Avalanches': 0, 
                'DamageState': KNOWN, 
                'TireDamage': 0,
                'open': False}

        
    def getTag(self):
        if self._bbDone:
            return "[Burnbarrel done]"
        if not self._open:
            return "[Burnbarrel closed]"
        estimateStr = "" if self._damageState == KNOWN else ">"
        totalKilled = self._tireDamage + self._hobosKilled
        if self._damageState == UNKNOWN:
            totalKilled += self.getUnknownAvalancheDamage(False)
        kp = killPercent(totalKilled)
        return "[Burnbarrel {}{}%]".format(estimateStr, kp)
    
    
    def _processLog(self, raidlog):
        events = raidlog['events']
        #check hot hobos killed (negative for hot door opened)
        #  = defeated - 8 * hot doors opened        
        self._hobosKilled = (
                      sum(k['turns'] for k in eventFilter(
                        events, r'defeated +Hot hobo'))
                - 8 * sum(d['turns'] for d in eventFilter(
                        events, "for the clan coffer")))

        # if Ol' Scratch is dead, set burnbarrel to finished
        self._bbDone = any(eventFilter(events, r'''defeated +Ol' +Scratch'''))
                
        if (self._hobosKilled > 0 or 
                self._totalTires > 0 or 
                self._totalAvalanches > 0):
            self._open = True  
        return True
    
            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if self._bbDone:
            return None
        if "put a tire on the fire" in txt:
            self._tires += 1
            self._totalTires += 1
            if self._lastTireNotify != self._tires:
                self._lastTireNotify = self._tires
                return self.getProgressText(True)
        elif "started a tirevalanche" in txt:
            return self.processTireAvalanche()
        return None
    
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["tires", "burnbarrel", "burn", "barrel", "bb"]:
            if not self._dungeonActive():
                return "When Hodgman was defeated, so all the fires went out."
            return self.getProgressText(False)        
        return None


    def processTireAvalanche(self):
        """ Figure out how much damage was done in the tirevalanche """
        self._totalAvalanches += 1
        if self._damageState in [KNOWN, GUESSED]: # already have dmg. estimate
            damage = getTireDamage(self._tires + 1)
            tires = self._tires + 1
            self._tires = 0
            self._tireDamage += damage
            return ("{} The {}-tire avalance destroyed {} hobos!"
                    .format(self.getTag(), tires, damage))
        else:
            damage = self.getUnknownAvalancheDamage()
            self._tires = 0
            self._tireDamage += damage
            self._damageState = GUESSED
            return ("{} I am now tracking Burnbarrel Blvd. in a limited "
                    "capacity.".format(self.getTag()))


    def getUnknownAvalancheDamage(self, countCurrentStack=True):
        ''' Do a tire avalanche calculation with N avalanches 
        (N-1 unaccounted, one just happened). If countCurrentStack is False,
        then it gets the avalanche damage but does not count the one that
        just "happened". 
        Tire damage estimate is performed by evenly-splitting number of missed
        tires among N stacks.'''
        nAvalanches = self._totalAvalanches - self._resumeData['Avalanches']
        stacks = [] # list of all unknown avalanche sizes
        
        # minimum number of tires seen on this stack now (post-login)
        # (since we know that there must be this many tires on the most
        #  recent stack)
        stacks.append(self._tires + 1) 
        
        # minimum numberof tires on stack before 1st avalanche (pre-shutdown)
        # since, again, we know that there were at least this many tires
        stacks.append(self._resumeData['Tires'] + 1)
        
        remainingAvalanches = nAvalanches - 2
        stacks.extend([1] * remainingAvalanches)
        remainingTires = self._totalTires - sum(stacks) + len(stacks)
        if countCurrentStack:
            self.log("NewTotal: {}, OldTotal: {}, Stacks: {}"
                     .format(self._totalTires, self._resumeData['TotalTires'],
                             sum(stacks)))
            self.log("Performing tire approximation. Missed {} avalanches. "
                     "Initial tire distribution = {}. Distributing {} tires."
                     .format(nAvalanches - 1, str(stacks), remainingTires))
        
        # distribute the remaining tires as evenly as possible
        for _i in range(remainingTires):
            stacks.sort()
            stacks[0] += 1
            
        # add up the damage
        newDamage = 0
        for tireVal in stacks:
            newDamage += getTireDamage(tireVal)
        if countCurrentStack:
            self.log("Distributed tires. New distribution = {}. Damage = {}"
                     .format(str(stacks), newDamage))
        else:
            # do not count current stack!
            # the current stack is either the largest or second-largest stack
            # when we use this approximation.
            stacks.sort()
            if self._tires > self._resumeData['Tires']:
                newDamage -= getTireDamage(stacks[-1])
            else:
                newDamage -= getTireDamage(stacks[-2])
        return newDamage


    def getProgressText(self, quickDisplay):
        """ Get chat to send when inquiry is done """         
        if self._bbDone:
            return ("{} It seems that all the tires rolled away after "
                    "Ol' Scratch kicked the bucket.".format(self.getTag()))
        elif self._damageState in [KNOWN, GUESSED]: # good guess made
            totalKilled = self._tireDamage + self._hobosKilled
            toKill = getTireDamage(self._tires + 1)
            percent1 = killPercent(totalKilled)
            percent2 = killPercent(toKill + totalKilled)
            if toKill + totalKilled >= 510:
                return ("{} There are {} tires on the stack. The next "
                        "avalanche should finish them!"
                        .format(self.getTag(), self._tires))                
            elif quickDisplay:
                return ("{} Tire stack: {} tires high. Next avalanche: "
                        "{}% -> {}%"
                        .format(self.getTag(), self._tires, 
                                percent1, percent2))
            return ("{} There are {} tires on the stack. Next avalanche: "
                    "{}% -> {}%"
                    .format(self.getTag(), self._tires, percent1, percent2))
        else: # just guess something!
            totalKilled = self._tireDamage + self._hobosKilled
            totalKilled += self.getUnknownAvalancheDamage(False)
            toKill = (self.getUnknownAvalancheDamage(True) 
                      - self.getUnknownAvalancheDamage(False))
            if toKill + totalKilled >= 510:
                return ("{} I've seen {} tires thrown since I logged on. "
                        "The next avalanche should finish them!"
                        .format(self.getTag(), self._tires))                
            
            percent1 = killPercent(totalKilled)
            percent2 = killPercent(toKill + totalKilled)
            return ("{} I've seen {} tires thrown since I logged on. "
                    "Next avalanche: {}% -> {}%"
                    .format(self.getTag(), self._tires, percent1, percent2))


    def _eventCallback(self, eData):
        s = eData.subject
        if s == "done":
            self._eventReply({'done': self.getTag()[1:-1]})
        elif s == "open":
            self._open = True
        elif s == "state":
            self._eventReply(self.state)

    
    def _availableCommands(self):
        return {'tires': "!tires: Display the size of the tire stack in "
                         "Burnbarrel Blvd.",
                'burnbarrel': None, 'bb': None, 'burn': None, 'barrel': None}
