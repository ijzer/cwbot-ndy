from cwbot.modules.BaseHoboModule import BaseHoboModule, eventFilter


def dreadPercent(n):
    if n >= 1000:
        return "BOSS"
    return "{}%".format(max(0, min(99, int(n/10))))

class DreadOverviewModule(BaseHoboModule):
    """ 
    Displays an overview of Dreadsylvania
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-overview"
    
    def __init__(self, manager, identity, config):
        self._woodsDone = None
        self._villageDone = None
        self._castleDone = None
        self._drunk = None
        self._woodsKilled = None
        self._villageKilled = None
        self._castleKilled = None
        self._kisses = None
        super(DreadOverviewModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._processLog(initData)


    @property
    def state(self):
        return {}

    
    @property
    def initialState(self):
        return {}

    
    def getTag(self):
        return ""


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._woodsDone   = any(eventFilter(events, r"""(?i)defeated\s+(The Great Wolf of the Air|Falls-From-Sky)"""))
        self._villageDone = any(eventFilter(events, r"""(?i)defeated\s+(the Zombie Homeowners' Association|Mayor Ghost)"""))
        self._castleDone  = any(eventFilter(events, r"""(?i)defeated\s+(The Unkillable Skeleton|Count Drunkula)"""))
        self._drunk = raidlog['dread']['drunkenness']
        self._woodsKilled   = raidlog['dread'].get('forest', 0)
        self._villageKilled = raidlog['dread'].get('village', 0)
        self._castleKilled  = raidlog['dread'].get('castle', 0)
        self._kisses = raidlog['dread'].get('kisses', 0)
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["dread"]:
            if not self._dungeonActive():
                return ("Dreadsylvania has disappeared for this century.")
            wtxt = "Woods done"
            vtxt = "Village done"
            ctxt = "Castle done"
            ktxt = "{} kisses".format(self._kisses)

            if not self._castleDone:
                if self._drunk < 2000:
                    ctxt = ("[+{} drunk to open Castle]"
                            .format(2000 - self._drunk))
                else:
                    ctxt = "Castle {}".format(
                                            dreadPercent(self._castleKilled))

            if not self._villageDone:
                if self._drunk < 1000:
                    vtxt = ("[+{} drunk to open Village]"
                            .format(1000 - self._drunk))
                    if not self._castleDone:
                        ctxt = "[Castle closed]"
                else:
                    vtxt = "Village {}".format(
                                            dreadPercent(self._villageKilled))
                    
            if not self._woodsDone:
                wtxt = "Woods {}".format(
                                        dreadPercent(self._woodsKilled))                
            txt = ", ".join([ktxt, wtxt, vtxt, ctxt])
            return txt
        return None
        
                
    def _availableCommands(self):
        return {'dread': "!dread: Display an overview of Dreadsylvania."}
    