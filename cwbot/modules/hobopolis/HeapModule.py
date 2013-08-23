from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventDbMatch


def killPercent(n):
    return int(max(0, min(99, 100*n / 500.0)))


class HeapModule(BaseDungeonModule):
    """ 
    A module that tracks the stench level of the Heap. The logic is somewhat
    complicated, but not nearly as much as the BurnbarrelModule.
    
    There are two operating states: KNOWN and UNKNOWN. 
    
    In KNOWN mode, the stench level of the Heap is known and is actively
    tracked. 
    
    If the bot is offline and it misses an I Refuse dive, it goes into UNKNOWN
    mode, unless there also haven't been any trashcanos (in which case, it
    is set to 0 stench). In UNKNOWN mode, it is implssible to tell the true
    stench level of the heap. The mode is reset to KNOWN when there is a new
    dive.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "heap"
    
    def __init__(self, manager, identity, config):
        # current heap stench lvl (negative is Oscus is dead, None if unknown)
        self._stench = None
        # stench level, but does not reset when I REFUSE is done
        self._totalStench = None 
        self._numDives = None # number of "i refuse" dives
        # number of stench hobos killed (trashcano = 5 killed)
        self._killed = None 
        self._heapLastNotify = None
        self._open = False
        self._heapDone = False
        self._initStench = None
        super(HeapModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        events = initData['events']
        self._db = initData['event-db']
        self._chatStrings = {d['heap_code']: d['chat'] for d in self._db
                             if d['heap_code']}
        self._unstenchStrings = [d['chat'] for d in self._db
                                 if d['heap_code'] == "unstench"]

        
        self._heapDone = False
        self._open = state['open']
        self._numDives = sum(d['turns'] for d in eventDbMatch(
                                 events, {'heap_code': "dive"}))

        self._totalStench = (
                4 + sum(t['turns'] for t in eventDbMatch(
                            events, {'heap_code': "trashcano"}))
                  + sum(t['turns'] for t in eventDbMatch(
                            events, {'heap_code': "stench"}))                             
                  - sum(f['turns'] for f in eventDbMatch(
                            events, {'heap_code': "unstench"})))
        self._initStench = self._totalStench
        self.log("OldDives: {}, NewDives: {}"
                 .format(state['dives'], self._numDives))
        self.log("Detected {} trashcanos".format(self._totalStench - 4))
                 
        if state['dives'] == self._numDives and state['stench'] is not None:
            # there have been no trashcanos since we went online
            # add stench difference
            self._stench = (state['stench'] 
                            + self._totalStench 
                            - state['totalstench'])
            self.log("Restored stench state to {}".format(self._stench))
        elif (state['dives'] != self._numDives and 
              state['totalstench'] == self._totalStench):
            # there has been a dive, but no other trashcanos
            self._stench = 0
            self.log("Restored stench state to 0, dives present without "
                     "any more stench")
        else:
            # there have been dives and more trashcanos
            self._stench = None
            self.log("...but it doesn't matter because we can't "
                     "tell when the last treasure dive was")
        self._heapLastNotify = self._stench
        self._processLog(initData)


    @property
    def state(self):
        return {'dives': self._numDives,
                'totalstench': self._totalStench,
                'stench': self._stench,
                'open': self._open}

    
    @property
    def initialState(self):
        return {'dives': 0, 
                'stench': 4, 
                'totalstench': 4, 
                'open': False}

    
    def getTag(self):
        if self._heapDone:
            return "[Heap done]"
        if not self._open:
            return "[Heap closed]"
        heapPercent = killPercent(self._killed)
        return "[Heap {}%]".format(heapPercent)


    def _processLog(self, raidlog):
        events = raidlog['events']
        # check stench hobos killed
        self._killed = (sum(stenchhobo['turns'] for stenchhobo in eventDbMatch(
                                            events, {'heap_code': "combat"}))
                        + 5 * sum(trash['turns'] for trash in eventDbMatch(
                                        events, {'heap_code': "trashcano"})))
            
        self._totalStench = (
                4 + sum(t['turns'] for t in eventDbMatch(
                            events, {'heap_code': "trashcano"}))
                  + sum(t['turns'] for t in eventDbMatch(
                            events, {'heap_code': "stench"}))                             
                  - sum(f['turns'] for f in eventDbMatch(
                            events, {'heap_code': "unstench"})))
            
        # if Oscus is dead, set the heap to finished
        self._heapDone = any(eventDbMatch(events, {'heap_code': "boss"}))
                
        if self._killed > 0:
            self._open = True  
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if self._heapDone:
            return None
        if self._chatStrings['dive'] in txt:
            self._numDives += 1
            self._stench = 0
            self.debugLog("New heap level = {}".format(self._stench))
            if self._heapLastNotify != 0:
                self._heapLastNotify = 0
                return "{} Stench level reset (0/8).".format(self.getTag())
        elif (self._chatStrings['trashcano'] in txt 
              or self._chatStrings['stench'] in txt):
            if (self._totalStench == self._initStench and 
                    self._initStench is not None):
                # no change from startup
                return None
            else:
                self._initStench = -999999
                
            if self._stench is not None and self._stench >= -1000:
                self._stench += 1
                self._totalStench += 1
                self.debugLog("New heap level = {}".format(self._stench))
                if self._heapLastNotify != self._stench:
                    self._heapLastNotify = self._stench
                    if self._stench < 8:
                        return ("{} Stench level increased ({}/8)."
                                .format(self.getTag(), self._stench))
                    else:
                        return ("{} Stench level increased to {} "
                                "(dive support for {} players)."
                                .format(self.getTag(), self._stench, 
                                        self._stench - 7))
            elif self._stench is None:
                return ("{} Stench level increased (total stench unknown)."
                        .format(self.getTag()))
        elif any(s in txt for s in self._unstenchStrings):
            if self._stench is not None and self._stench >= -1000:
                self._stench -= 1
                self._totalStench -= 1
                self.debugLog("New heap level = {}".format(self._stench))
                if self._heapLastNotify != self._stench:
                    self._heapLastNotify = self._stench
                    if self._stench < 8:
                        return ("{} Stench level decreased ({}/8)."
                                .format(self.getTag(), self._stench))
                    else:
                        return ("{} Stench level decreased to {} "
                                "(dive support for {} players)."
                                .format(self.getTag(), self._stench, 
                                        self._stench - 7))
            elif self._stench is None:
                return ("{} Stench level decreased (total stench unknown)."
                        .format(self.getTag()))
        return None

        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["heap", "trash"]:
            if not self._dungeonActive():
                return ("Hodgman has been defeated, so you can't play "
                        "in any more trash.")
            elif self._heapDone:
                return ("{} Oscus has been defeated, so the Heap just isn't " 
                "that stinky anymore.".format(self.getTag()))
            if self._stench is None:
                return ("{} I haven't been online long enough to know what "
                        "the stench level is. Sorry!".format(self.getTag()))
            if self._stench < 8:
                return ("{} Stench level {}/8"
                        .format(self.getTag(), self._stench))
            else:
                return ("{} Stench level {}/8 (dive support for {} players)"
                        .format(self.getTag(), self._stench, self._stench - 7))
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
        return {'heap': "!heap: Display the stench level of the Heap.",
                'trash': None}
