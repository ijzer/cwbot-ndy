from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventDbMatch
from cwbot.kolextra.request.GetScareHoboPartsRequest \
                     import GetScareHoboPartsRequest


def scareHobosCreated(oldPartCount, newPartCount):
    """ Number of scarehobos created = maximum part DECREASE """
    partDecrease = max(oldPart-newPart 
                       for oldPart,newPart in zip(oldPartCount, newPartCount))
    return max(0, partDecrease) 


UNKNOWN = 0
GUESSED = 1
KNOWN = 2

class TownScarehoboModule(BaseDungeonModule):
    """ 
    A module that keeps track of the scarehobo status in Hobopolis and
    announces when any are created. Players do not directly communicate
    with this module; instead, the TownModule passes events to get information
    from this module. However, the module does send chats when scarehobo
    events occur.
    
    NOTE: This module must be loaded **before** the TownModule; it is a
    dependency. 
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "town_scarehobo"
    

    def __init__(self, manager, identity, config):
        self._scareHoboParts = [None] * 6
        self._scareHofboDamage = None
        self._killed = None
        self._guessState = None
        self._initialized = False
        super(TownScarehoboModule, self).__init__(manager, identity, config)


    def getTag(self):
        # get the town tag from the TownModule
        tagMsg = self._raiseEvent("tag", "town")
        if len(tagMsg) != 1:
            raise Exception("Invalid tagMsg: {}".format(tagMsg))
        return tagMsg[0].data['tag']


    def getParts(self):
        """ Get the number of scarehobo parts available """
        r = GetScareHoboPartsRequest(self.session)
        parts = self.tryRequest(r, nothrow=True, numTries=2, initialDelay=0.5)
        if parts is None:
            return None
        return parts['parts']

    
    def processPartChange(self, newScareHoboParts):
        """ determine how many scarehobos have been created """
        if None in self._scareHoboParts:
            return
        # calculate number of new scarehobos
        partDiff = scareHobosCreated(self._scareHoboParts, newScareHoboParts)
        if partDiff > 0:
            # find damage, send message
            self._scareHoboDamage += 8 * partDiff
            self.chat("{} {} scarehobos have been assembled, "
                      "driving {} hobos away! {} scarehobos available."
                      .format(self.getTag(), partDiff, 8 * partDiff, 
                              min(newScareHoboParts))) # add tag!
            self.log("Parts: {} -> {}; created {} scarehobos"
                     .format(self._scareHoboParts, newScareHoboParts, 
                             partDiff)) 
        elif (newScareHoboParts.count(0) == 0 and 
              self._scareHoboParts.count(0) > 0):
            self.chat("{} Scarehobos are now available for creation."
                      .format(self.getTag()))


    def initialize(self, state, initData):
        events = initData['events']
        
        # see number of scarehobos killed
        self._killed = sum(k['turns'] for k in eventDbMatch(
                               events, {'town_code': "combat"}))
        self._scareHoboDamage = state['damage']
        killDiff = self._killed - state['killed']
        
        # let's see if any scarehobos look like they were created 
        # (indicated by a decrease in parts)    
        self._guessState = state['scareHoboState']
        if killDiff > 50:
            # we missed some hobo activity, let's say the state is guessed
            # for good measure
            self._guessState = GUESSED
        self._scareHoboParts = self.getParts()
        if self._scareHoboParts is None:
            # usually, this only happens if we are in between instances
            self._scareHoboParts = state['scareHoboParts']
            self._guessState = GUESSED
        
        scareHobos = scareHobosCreated(state['scareHoboParts'], 
                                       self._scareHoboParts)
        self._scareHoboDamage = state['damage']
        if scareHobos > 0:
            guessText = ""
            if self._guessState == GUESSED:
                guessText = " (changing state to GUESSED)"
            self.log("Detected {} scarehobos ({} -> {}) {}"
                     .format(scareHobos, state['scareHoboParts'], 
                             self._scareHoboParts, guessText))
            self._scareHoboDamage += 8 * scareHobos
        self._initialized = True
        self._processLog(initData)


    @property
    def state(self):
        state = {'killed': self._killed,
                 'scareHoboParts': self._scareHoboParts, 
                 'damage': self._scareHoboDamage,
                 'scareHoboState': self._guessState}
        if state['scareHoboParts'] is None:
            state['scareHoboParts'] = [0] * 6
        return state

    
    @property
    def initialState(self):
        return {'killed': 0,
                'scareHoboParts': [0] * 6, 
                'damage': 0,
                'scareHoboState': KNOWN}


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._killed = sum(k['turns'] for k in eventDbMatch(
                               events, {'town_code': "combat"}))
            
        newScareHoboParts = self.getParts()
        if newScareHoboParts is not None:
            if newScareHoboParts != self._scareHoboParts:
                self.processPartChange(newScareHoboParts)
            self._scareHoboParts = newScareHoboParts
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None

        
    def _processCommand(self, msg, cmd, args):
        return None


    def reset(self, _events):
        self._scareHoboParts = [0] * 6
        self._guessState = KNOWN
        self._killed = 0
        self._scareHoboDamage = 0
        
    
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "damage":
            if self._initialized:
                self._eventReply({'damage': self._scareHoboDamage, 
                                  'guess': self._guessState})
        elif s == "scarehobo_available":
            if self._initialized:
                self._eventReply({'available': (min(self._scareHoboParts))})
        elif s == "state":
            self._eventReply(self.state)
    