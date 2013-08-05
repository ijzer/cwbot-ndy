from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter


class SewerModule(BaseDungeonModule):
    """ 
    A module that tracks the valves/grate status in the sewer. This
    information can be obtained from the logs, so the module is essentially
    stateless. 
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "sewer"

    
    def __init__(self, manager, identity, config):
        self._valves = None
        self._grates = None
        self._lastValveNotify = None
        self._lastGrateNotify = None
        super(SewerModule, self).__init__(manager, identity, config)

        
    def initialize(self, _state, initData):
        self._lastValveNotify = 0
        self._lastGrateNotify = 0
        self._processLog(initData)


    @property
    def state(self):
        return {'valves': self._valves, 'grates': self._grates}

    
    @property
    def initialState(self):
        return {}

        
    def _processLog(self, raidlog):
        events = raidlog['events']
        self._valves = sum(w['turns'] for w in eventFilter(
                               events, "lowered the water level"))
        self._grates = sum(g['turns'] for g in eventFilter(
                               events, "sewer grate"))
        return True
    

    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if "has lowered the water level" in txt:
            if self._valves != self._lastValveNotify:
                self._lastValveNotify = self._valves
                return ("The water has been lowered {}/20 times."
                        .format(self._valves))
        elif "opened a grate" in txt:
            if self._grates != self._lastGrateNotify:
                self._lastGrateNotify = self._grates
                return ("A total of {}/20 grates have been opened."
                        .format(self._grates))
        return None

                
    def _processCommand(self, unused_msg, cmd, _args):
        if cmd in ["sewer", "sewers", "valve", "valves", "water", 
                   "grate", "grates"]:
            if not self._dungeonActive():
                return ("Hodgman is dead. This isn't the time to be worried "
                        "about valves and grates and whatnot.")
            chattxt = ""
            if self._valves < 20:
                chattxt = ("The water level has been lowered {}/20 times and "
                           .format(self._valves))
            else:
                chattxt = "The water level is completely lowered and "
                
            if self._grates < 20:
                chattxt += ("{}/20 grates have been opened."
                            .format(self._grates))
            else:
                chattxt += "all of the grates have been opened."

            return chattxt
        return None

        
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "done":
            self._eventReply({'done': "Sewer {}/40"
                                      .format(self._grates + self._valves)})
        elif s == "state":
            self._eventReply(self.state)


    def _availableCommands(self):
        return {'sewer': "!sewer: Display the number of open valves "
                         "and grates in the sewer.",
                'sewers': None, 'valve': None, 'valves': None, 'water': None,
                'grate': None, 'grates': None}
