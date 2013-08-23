from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventDbMatch
import re


def stageClearCount(events):
    return sum(c['turns'] for c in eventDbMatch(
                   events, 
                   {'town_code': "ruin"}, 
                   {'town_code': "busk"}, 
                   {'town_code': "mosh"}))

def stageCount(events):
    return sum(s['turns'] 
               for s in eventDbMatch(events, {'town_code': "stage"}))

    
UNKNOWN = 0
GUESSED = 1
KNOWN = 2

KNOWN_UNOPENED = 1
KNOWN_OPEN = 2
KNOWN_CLOSED = 3


class TownModule(BaseDungeonModule):
    """ 
    A module that tracks town square status, including zone and stage openings.
    This module also coordinates with the TownScarehobo and TownStage modules,
    to keep the logic separated.
    
    NOTE: This module must be loaded **after** TownScarehobo and TownStage 
    modules! So make SURE it has **lower** priority, or the bot won't start.
    
    This module is responsible for the following:
    
    1. It communicates with the TownScarehoboModule and TownStageModule to
        determine how much damage has been done due to scarehobos and
        moshing, and uses this information plus the logs to determine the
        approximate number of hobos killed in the town square.
    2. It determines when enough hobos have been killed to open a new side
        area (or the tent), and sends an event to these side areas that they
        are open. Note that if an area is not sent this message, it will open
        itself after an adventure is spent there.
    3. If an area is detected as open from the logs, but the TownModule thinks
        it is closed, it corrects the amount of killed hobos.
    4. It tracks when the town stage opens and closes. However, other stage
        details are handled by the TownStageModule.
    5. It handles the !town command by coordinating with the other two
        modules.
    6. It handles the !status command by getting information from the other
        Hobopolis side zone modules.
    
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "town"
    
    # list of openings: (# kills, formal name, module name, tag name)
    openings = [(250,  "Burnbarrel Blvd.", "burnbarrel", "Burnbarrel"),
                (500,  "Exposure Esplanade", "exposure", "Exposure"),
                (750,  "The Heap", "heap", "Heap"),
                (1000, "The Ancient Hobo Burial Ground", "burial", "AHBG"),
                (1250, "The Purple Light District", "pld", "PLD"),
                (1500, "The tent", None, None)]
    
    
    # approximate values of dances
    def __init__(self, manager, identity, config):
        self._killed = None
        self._resumeData = None
        self._lastOpening = None
        self._tentOpen = UNKNOWN
        self._lastTent = 0
        self._stageClears = None
        self._totalperformers = None
        self._damageCorrection = 0 # additional damage that we know must exist
        super(TownModule, self).__init__(manager, identity, config)


    def checkOpenings(self, doneAmt, suppressChat=False):
        """ Check if a new side zone has been opened. """
        self.debugLog("Checking openings... (last {})"
                      .format(self._lastOpening))
        if self._lastOpening < 1500 and self._lastOpening is not None:
            #     check if a new zone has opened
            # get next zone to open from openings list
            (nextOpening, areaName, procName, _tagName) = min(
                (item for item in self.openings 
                     if item[0] > self._lastOpening), 
                key=lambda x: x[0])
            if doneAmt >= nextOpening:
                # zone is open now!
                self._lastOpening = nextOpening
                self.log("Done amount {}".format(doneAmt))
                self.log("Next opening {}".format(nextOpening))
                if not suppressChat:
                    self.log("Printing opening...")
                    self.chat("{} {} is now open (or is almost open)."
                              .format(self.getTag(), areaName))
                self._raiseEvent("open", procName)
                if nextOpening == 1500:
                    self._tentOpen = KNOWN_OPEN
                    self._lastTent = doneAmt
                doneAmt = self.getDoneAndState()[0]
                # check if more zones have opened!
                self.checkOpenings(doneAmt, suppressChat)
        elif self._lastTent is not None and self._tentOpen != KNOWN_OPEN:
            # check if the tent has reopened
            self.debugLog("Last tent {}".format(self._lastTent))
            if doneAmt >= self._lastTent + 100:
                self._tentOpen = KNOWN_OPEN
                if not suppressChat:
                    self.chat("{} The tent has reopened (or is almost open)."
                              .format(self.getTag()))
              
                
    def correctDamage(self, events, damage):
        """ adjust damage if any areas are open but we "think" they are not.
        make sure to do this AFTER accounting for scarehobos """

        minDamage = 0
        if any(eventDbMatch(events, {'town_code': "stage"})):
            minDamage = 1500 + 100 * max(0, self._stageClears - 1)
        elif any(eventDbMatch(events, {'pld_code': "combat"})):
            minDamage = 1250
        elif any(eventDbMatch(events, {'ahbg_code': "combat"})):
            minDamage = 1000
        elif any(eventDbMatch(events, {'heap_code': "combat"},
                                      {'heap_code': "trashcano"})):
            minDamage = 750
        elif any(eventDbMatch(events, {'ee_code': "combat"})):
            minDamage = 500
        elif any(eventDbMatch(events, {'bb_code': "combat"})):
            minDamage = 250
            
        if minDamage > damage:
            oldDC = self._damageCorrection
            self._damageCorrection += minDamage - damage
            self.log("Correcting damage: Detected {} damage, "
                     "minDamage = {}, old correction = {}, "
                     "new correction = {}"
                     .format(damage, minDamage, oldDC, self._damageCorrection))
            damage = self.getDoneAndState()[0]
        return damage

    
    def initialize(self, state, initData):
        events = initData['events']
        self._db = initData['event-db']
        
        self._killed = sum(k['turns'] for k in eventDbMatch(
                               events, {'town_code': "combat"}))
        self._stageClears = stageClearCount(events)
        self._totalperformers = stageCount(events)
        self._damageCorrection = state['damageCorrection']
        
        # do an initial damage calculation
        (doneAmt, guessState) = self.getDoneAndState() 
        doneAmt = self.correctDamage(events, doneAmt)
        
        self._doProcessLog(initData, suppressChat=True)
        
        self._lastOpening = self.getDoneAndState()[0]
        self.log("Last opening: {}".format(self._lastOpening))

        # figure out the whole tent opening thing
        lastStageClears = state['stageClears']
        lastPerformers = state['totalPerformers']
        onStage = self.getOnStage()[0]
        killDiff = doneAmt - state['lastTent']
        if onStage > 0:
            # we KNOW that the stage is open
            self._tentOpen = KNOWN_OPEN            
            self._lastTent = doneAmt - 100
            self.log("Detected {} or more players on stage -> OPEN"
                     .format(onStage))
        elif guessState == KNOWN and doneAmt < 1500:
            # we know it's not open
            self._tentOpen = KNOWN_UNOPENED
            self._lastTent = 0
        elif doneAmt < 1250:
            # there have been no adventures in the PLD and we are fairly 
            # certain the tent is not open yet.
            self._tentOpen = KNOWN_UNOPENED
            self._lastTent = 0            
        elif killDiff < 100:
            # we know that the stage still not reopened
            self._tentOpen = KNOWN_CLOSED
            self._lastTent = state['lastTent']
        elif lastStageClears == self._stageClears:
            # unfortunately, busking with 0 players on stage is not logged, 
            # so there's a chance that the stage is closed now.
            self._tentOpen = UNKNOWN
            self._lastTent = doneAmt
        elif lastPerformers == self._totalperformers:
            # the stage has been cleared, no new performers. But we don't
            # know when :/
            self._tentOpen = UNKNOWN
            self._lastTent = doneAmt
        else:
            # stage is cleared, but there may be new performers
            self._tentOpen = UNKNOWN
            self._lastTent = doneAmt

        for numKills, areaName, procName, _tagName in self.openings:
            if doneAmt > numKills:
                self._raiseEvent("open", procName)
                self.log("Opening {}".format(areaName))
    
        
    @property
    def state(self):
        return {'killed': self._killed,
                'lastOpening': self._lastOpening,
                'tentOpen': self._tentOpen,
                'lastTent': self._lastTent,
                'stageClears': self._stageClears,
                'totalPerformers': self._totalperformers,
                'damageCorrection': self._damageCorrection}
        

    @property
    def initialState(self):
        return {'killed': 0,
                'lastOpening': 0,
                'tentOpen': KNOWN_UNOPENED,
                'lastTent': 0,
                'stageClears': 0,
                'totalPerformers': 0,
                'damageCorrection': 0}

    
    def _processLog(self, raidlog):
        return self._doProcessLog(raidlog)
    
    
    def _doProcessLog(self, raidlog, suppressChat=False):
        events = raidlog['events']
        doneAmt = self.getDoneAndState()[0] 
        doneAmt = self.correctDamage(events, doneAmt)
        self._killed = sum(k['turns'] for k in eventDbMatch(
                               events, {'town_code': "combat"}))
        newPerformers = stageCount(events)
        newStageClears = stageClearCount(events)
        if newStageClears > self._stageClears:
            self._tentOpen = KNOWN_CLOSED
            if not suppressChat:
                self.chat("{} The tent will open when 100 more hobos "
                          "are killed.".format(self.getTag()))
            self._lastTent = self.getDoneAndState()[0]
        elif newPerformers > self._totalperformers:
            self._tentOpen = KNOWN_OPEN
        self._totalperformers = newPerformers
        self._stageClears = newStageClears
        self.checkOpenings(doneAmt, suppressChat)
        return True
    
    
    def getDoneAndState(self):
        doneAmt = self._killed + self._damageCorrection
        replies = self._raiseEvent("damage", None)
        moshDmgEvt = [e for e in replies if e.fromName == "town_stage"]
        scarehoboDmgEvt = [e for e in replies 
                           if e.fromName == "town_scarehobo"]
        if len(moshDmgEvt) != 1:
            raise Exception("improper moshDmgEvt: {}".format(moshDmgEvt))
        if len(scarehoboDmgEvt) != 1:
            raise Exception("improper scarehoboDmgEvt: {}"
                            .format(scarehoboDmgEvt))
        d = [moshDmgEvt[0].data['damage'], 
             scarehoboDmgEvt[0].data['damage']]
        guessState = min(moshDmgEvt[0].data['guess'], 
                         scarehoboDmgEvt[0].data['guess'])
        doneAmt += d[0] + d[1]
        return (doneAmt, guessState)

    
    def getScarehobosAvailable(self):
        scarehoboEvt = self._raiseEvent("scarehobo_available", 
                                        "town_scarehobo")
        if len(scarehoboEvt) != 1:
            raise Exception("improper scarehoboEvt: {}".format(scarehoboEvt))
        return scarehoboEvt[0].data['available']
    
    
    def getOnStage(self):
        stageEvt = self._raiseEvent("onstage", "town_stage")
        if len(stageEvt) != 1:
            raise Exception("improper stageEvt: {}".format(stageEvt))
        return (stageEvt[0].data['stage'], stageEvt[0].data['guess'])
    
    
    def getTag(self):
        try:
            (doneAmt, guessState) = self.getDoneAndState()
            percentDone = max(0, min(99, int(100 * doneAmt / 3000.0)))
            guessStr = "" if (guessState == KNOWN) else ">"
            return "[Town {}{}%]".format(guessStr, percentDone)
        except:
            return "[Town]"
    
            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if "has passed a hat in the tent, but didn't manage" in txt:
            # for some reason, this doesn't show up in the logs.
            self._tentOpen = KNOWN_CLOSED
            self._lastTent = self.getDoneAndState()[0]            
            return ("{} The tent will open when 100 more hobos are defeated."
                    .format(self.getTag()))
        return None
    
        
    def _processCommand(self, msg, cmd, args):
        if cmd in ["town", "townsquare", "stage"]: 
            if not self._dungeonActive():
                return ("Hodgman is gone, leaving the town square completely "
                        "empty.")
            availableScareHobos = self.getScarehobosAvailable()
            (onstage, stageGuess) = self.getOnStage()
            if self._tentOpen == UNKNOWN:
                if self._lastOpening < 1250:
                    return ("{} The tent hasn't opened yet. {} scarehobos "
                            "available."
                            .format(self.getTag(), availableScareHobos))
                else:
                    return ("{} I haven't been online long enough to see the "
                            "tent's state. {} scarehobos available."
                            .format(self.getTag(), availableScareHobos))
            elif self._tentOpen == KNOWN_UNOPENED:
                return ("{} The tent hasn't opened yet. {} scarehobos "
                        "available."
                        .format(self.getTag(), availableScareHobos))
            elif self._tentOpen == KNOWN_CLOSED:
                doneAmt = self.getDoneAndState()[0]
                return ("{} The tent will open when {} more hobos are "
                        "defeated. {} scarehobos available."
                        .format(self.getTag(), self._lastTent + 100 - doneAmt,
                                availableScareHobos))
            elif self._tentOpen == KNOWN_OPEN:
                if stageGuess == UNKNOWN:
                    return ("{} The tent is open with at least {} players "
                            "on stage. {} scarehobos available."
                            .format(self.getTag(), onstage, 
                                    availableScareHobos))
                else:
                    return ("{} The tent is open with {} players on stage. "
                            "{} scarehobos available."
                            .format(self.getTag(), onstage, 
                                    availableScareHobos))
        elif cmd in ["summary", "hobopolis", "status", "hobo"]: 
            if not self._dungeonActive():
                return "The Hobopolis instance is complete."
            return self.getSummary()
        return None


    def getSummary(self):
        """ Return the string for the !summary command """
        (doneAmt, guessState) = self.getDoneAndState()
        self.checkOpenings(doneAmt)
        
        showedNextClosed = False
        replies = []
        r1 = self._raiseEvent("done", "sewer")
        if r1:
            replies.append(r1[0].data['done'])
        r2 = self._raiseEvent("done", "cage")
        if r2:
            replies.append(r2[0].data['done'])
        replies.append(self.getTag()[1:-1])
        for numKills, _areaName, procName, tagName in self.openings:
            if procName is not None:
                try:
                    newReply = (self._raiseEvent("done", procName)[0]
                                .data['done'])
                    if re.search("Closed|closed", newReply) is not None:
                        if not showedNextClosed:
                            killDiff = numKills - doneAmt
                            if killDiff > 0:
                                showedNextClosed = True
                                estimateStr = ("<" if guessState != KNOWN 
                                               else "")
                                newReply = ("[{}{} Hobos to open {}]"
                                            .format(estimateStr, killDiff, 
                                                    tagName))
                    replies.append(newReply)
                except IndexError:
                    pass
        
        s = ", ".join(replies)
        return s


    def reset(self, _events):
        self._killed = 0
        self._lastOpening = 0
        self._tentOpen = KNOWN_UNOPENED
        self._lastTent = 0
        self._stageClears = 0
        self._totalperformers = 0
        self._damageCorrection = 0      
    

    def _eventCallback(self, eData):
        s = eData.subject        
        if s == "done":
            self._eventReply({'done': self.getTag()[1:-1]})
        elif s == "state":
            self._eventReply(self.state)
        elif s == "tag":
            self._eventReply({'tag': self.getTag()})
    
    
    def _availableCommands(self):
        return {'town': "!town: show the number of scarehobos available "
                        "and the state of the town stage.",
                'status': "!status: show a summary of Hobopolis progress."}
