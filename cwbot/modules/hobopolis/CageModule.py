import re
import time
from cwbot.modules.BaseHoboModule import BaseHoboModule, eventFilter


UNKNOWN = 0
TRAPPED = 1
RELEASED = 2
EMPTY = 3

def cageStateStr(n):
    return {UNKNOWN: "unknown",
            TRAPPED: "trapped",
            RELEASED: "released",
            EMPTY: "empty"}[n]


class CageModule(BaseHoboModule):
    """ 
    A module that tracks the C.H.U.M. cage. It is capable of tracking the 
    following:
    
    1. If someone has been trapped in the cage but not freed,
    2. If someone has been freed but has not adventured in Hobopolis,
    3. If someone has been freed and is now adventuring in Hobopolis,
    4. If someone gnawed through the cage.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "cage"

    def __init__(self, manager, identity, config):
        # name of the player in the cage right now 
        # ("" if nobody's there, None if unknown)
        self.inCage = None 
        # num. of actions in hobopolis the caged player has done 
        # (to track cagesitting)
        self._inCageHoboActions = None              
        # times since caged player was released (None if nobody's there)
        self._inCageFreedTime = None                
        # total number of sewer actions at startup
        self._startupSewerActions = None            
        self._startupTime = time.time() # time at startup
        self._totalSewerActions = None # most recent sewer action count
        # at next log check, update _inCageHoboActions
        self._updateInCageActions = False 
        self._totalFreed = None
        # if the bot sees a message about someone being imprisoned:
        #       self.inCage = PlayerName, self._inCageFreedTime = None, 
        #       self._inCageHoboActions = # of actions that player has done
        # if the bot sees a message about that player gnawing through the cage:
        #       self.inCage = "", self._inCageFreedTime = None
        # if the bot sees a message about the player being freed from the cage:
        #       self._inCageFreedTime = time.time()
        # if it is detected from the log that self.inCage has adventured 
        # in hobopolis again:
        #       self.inCage = "", self._inCageFreedTime = None
        #
        # if the bot just logged on and it doesn't know who is in the cage:
        #       self.inCage = None
        # if the bot then sees a message about a player being rescued:
        #       self.inCage = PlayerName, 
        #       self._inCageHoboActions = # of actions that player has done
        # if the bot instead sees a message about gnawing through the cage:
        #       self.inCage = ""
        super(CageModule, self).__init__(manager, identity, config)
        

    def getCageState(self):
        if self.inCage is None:
            return UNKNOWN
        if self.inCage == "":
            return EMPTY
        if self._inCageFreedTime is None:
            return TRAPPED
        return RELEASED

        
    def initialize(self, state, initData):
        events = initData['events']
        
        self._totalFreed = sum(
                f['turns'] for f in eventFilter(
                    events, r'rescued .* from .* C. H. U. M. cage'))
        self._startupSewerActions = sum(
                s['turns'] for s in events if s['category'] == "Sewers")
        self.debugLog("Detected {} sewer actions at startup"
                      .format(self._startupSewerActions))
        
        self.inCage = state['inCage']
        self._inCageHoboActions = state['inCageHoboActions']
        self._inCageFreedTime = state['inCageFreedTime']
        
        if self.inCage is None:
            # previously unknown
            self.setUnknown()
        elif self.inCage == "":
            # nobody was in cage, but now we can't tell anymore.
            self.log("Restored from empty cage state, setting to unknown...")
            self.setUnknown()
        elif self._inCageFreedTime is not None:
            # somebody was previously in the cage, but freed
            if (self.getHoboActions(self.inCage, events) != 
                    self._inCageHoboActions):
                # they've adventured
                self.log("Player {} was freed and adventured in Hobopolis. "
                         "Setting to unknown...".format(self.inCage))
                self.setUnknown()
            else:
                # everything is the same!
                pass
        else:
            # somebody was in the cage but not freed
            if self._totalFreed != state['totalFreed']:
                # they have been freed!
                if (self.getHoboActions(self.inCage, events) != 
                        self._inCageHoboActions):
                    # and they've stayed put!
                    self.log("Player {} was freed and has not adventured "
                             "in Hobopolis. Setting to freed..."
                             .format(self.inCage))
                    self.setReleased(self.inCage)
                else:
                    # they've moved. we have no idea of cage state
                    self.log("Player {} was freed and adventured in Hobopolis."
                             " Setting to unknown...".format(self.inCage))
                    self.setUnknown()
            else:
                # everything is the same
                pass

        
    @property
    def state(self):
        return {'inCage': self.inCage,
                'inCageHoboActions': self._inCageHoboActions,
                'inCageFreedTime': self._inCageFreedTime,
                'totalFreed': self._totalFreed}

    
    @property
    def initialState(self):
        return {'inCage': None,
                'inCageHoboActions': None,
                'inCageFreedTime': None,
                'totalFreed': None}

        
    def _processLog(self, raidlog):
        events = raidlog['events']
        if self.getCageState() in [UNKNOWN, EMPTY]: # don't know cage status
            self._inCageFreedTime = None
        else:
            if self._updateInCageActions:
                self._updateInCageActions = False
                self._inCageHoboActions = self.getHoboActions(
                                        self.inCage, events)
                self.log("{} action count = {}".format(
                                        self.inCage, self._inCageHoboActions))
 
            # check if cage occupant has adventured in hobopolis
            currentHoboActions = self.getHoboActions(self.inCage, events)
            if currentHoboActions != self._inCageHoboActions:
                self.log("Detected {} escape: {} -> {}"
                         .format(self.inCage, self._inCageHoboActions, 
                                 currentHoboActions))
                self.chat("{} has left the C.H.U.M. cage.".format(self.inCage))
                self.setEscaped()
                    
        # check sewer actions
        newTotalFreed = sum(
                f['turns'] for f in eventFilter(
                    events, r'rescued .* from .* C. H. U. M. cage'))
        if newTotalFreed > self._totalFreed and self.getCageState() == TRAPPED:
            self.setReleased(self.inCage)
        self._totalFreed = newTotalFreed
        self._totalSewerActions = sum(
                s['turns'] for s in events if s['category'] == "Sewers")
        return True

            
    def _processDungeon(self, txt, raidlog):
        if "has been imprisoned by the C. H. U. M.s" in txt:
            m = re.search(r'^(.*) has been imprisoned by the', txt)
            self.setImprisoned(str(m.group(1)))
        elif "has rescued" in txt:
            m = re.search(r'rescued (.*) from the', txt)
            self.setReleased(str(m.group(1)))
        elif "by gnawing through" in txt:
            self.setEscaped()
        elif "resetCageStartupTime" in txt:
            self._startupTime = 0
            self._startupSewerActions = -10000
        self._processLog(raidlog)
        return None

                
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd == "cage" or cmd == "caged":
            if not self._dungeonActive():
                return "Hodgman is dead. Why are you worried about cages?"
            if self.getCageState() != UNKNOWN: # we know who is in cage
                if self.getCageState() == EMPTY: # nobody is in cage!
                    return "Nobody is inside the cage right now."
                elif self.getCageState() == RELEASED: 
                    # someone's been freed, but we haven't seen 'em do anything
                    minutes = int((time.time() - self._inCageFreedTime) // 60)
                    return ("{} was released from the C.H.U.M. cage {} "
                            "minutes ago, but has not adventured in Hobopolis "
                            "since.".format(self.inCage, minutes))
                else: # someone is in cage still and hasn't been freed
                    return ("{} is still trapped in the C.H.U.M. cage! "
                            "Somebody help {}!"
                            .format(self.inCage, self.inCage))
            else:
                actionsSinceStartup = (self._totalSewerActions 
                                       - self._startupSewerActions)
                minutesSinceStartup = int(
                        (time.time() - self._startupTime) // 60)
                if minutesSinceStartup < 5:
                    return ("I haven't been online long enough to know "
                            "if anyone is in the cage. Sorry!")
                elif actionsSinceStartup < 20:
                    return ("There hasn't been enough sewer activity "
                            "since I've been online to know if anyone "
                            "is in the cage. Sorry!")
                else:
                    return ("I can't tell for sure, but there have been {} "
                            "sewer actions in the last {} minutes and no "
                            "cage activity."
                            .format(actionsSinceStartup, minutesSinceStartup))
        return None


    def reset(self, _events):
        # need a special reset: we KNOW that the cage is empty
        
        self.inCage = ""
        self._inCageHoboActions = None
        self._inCageFreedTime = None
        self._startupSewerActions = 0
        self._startupTime = time.time() #time at startup
        self._totalSewerActions = 0
        self.log("Cage reset.")
    
        
    def setImprisoned(self, playerName):
        self.inCage = playerName
        self._updateInCageActions = True
        self._inCageFreedTime = None
        self.log("{} trapped".format(self.inCage))
    
        
    def setEscaped(self):
        self.inCage = ""
        self._inCageHoboActions = None
        self._inCageFreedTime = None
        self.log("Cage now empty.")
    
        
    def setReleased(self, playerName):
        self.inCage = playerName
        self.log("{} freed".format(self.inCage))
        self._inCageFreedTime = time.time()
        if self._inCageHoboActions is None:
            self._updateInCageActions = True
    
            
    def setUnknown(self):
        self.inCage = None
        self._inCageHoboActions = None
        self._inCageFreedTime = None
        self.log("Cage set to unknown state")
    
        
    def getHoboActions(self, playerName, events):
        turnsInHobopolis = 0
        for playerevent in (item for item in events 
                            if item['userName'] == playerName):
            if "stared at" not in playerevent['event']:
                turnsInHobopolis += playerevent['turns']
        return turnsInHobopolis

    
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            self._eventReply(self.state)
        elif s == "done":
            d = {}
            d['done'] = ({EMPTY: "Cage empty",
                          RELEASED: "Cage occupied (player released)",
                          TRAPPED: "Cage occupied (player trapped)"}
                          .get(self.getCageState(), "Cage unknown"))
            self._eventReply(d)


    def _availableCommands(self):
        return {'cage': "!cage: Display if anyone is trapped in the cage.",
                'caged': None}
