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

    _balance = {0: ['B', 'W'], 1: ['G', 'Z'], 2: ['S', 'V']}
    
    def __init__(self, manager, identity, config):
        self._woodsDone, self._villageDone, self._castleDone = None, None, None
        self._drunk = None
        self._woodsKilled = None
        self._villageKilled = None
        self._castleKilled = None
        self._kisses = None
        
        self._woodsBal, self._villageBal, self._castleBal = None, None, None
        super(DreadOverviewModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._processLog(initData)


    @property
    def state(self):
        return {}

    
    @property
    def initialState(self):
        return {}

    
    def getTag(self, areaNum):
        killed = {0: self._woodsKilled, 
                  1: self._villageKilled, 
                  2: self._castleKilled}[areaNum]
        done = {0: self._woodsDone,
                1: self._villageDone,
                2: self._castleDone}[areaNum]
        balance = {0: self._woodsBal,
                   1: self._villageBal,
                   2: self._castleBal}[areaNum]
        areaName = {0: "Woods", 1: "Village", 2: "Castle"}[areaNum]
        
        # area
        txt = areaName + " "
        
        # completion
        if done:
            return txt + " done"
        if killed >= 1000:
            txt += " BOSS"
        else:
            txt += " {}%".format(int(killed/10))
        
        # balance
        if balance == 0:
            txt += " ="
        else:
            idx = 0 if balance < 0 else 1
            txt += " " + self._balance[areaNum][idx] + "+"
            txt += "{}".format(abs(balance))
        return txt


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._woodsDone   = any(eventFilter(events, r"""(?i)defeated\s+(The Great Wolf of the Air|Falls-From-Sky)"""))
        self._villageDone = any(eventFilter(events, r"""(?i)defeated\s+(the Zombie Homeowners' Association|Mayor Ghost)"""))
        self._castleDone  = any(eventFilter(events, r"""(?i)defeated\s+(The Unkillable Skeleton|Count Drunkula)"""))
        self._drunk = raidlog['dread']['drunkenness']
        self._woodsKilled   = raidlog['dread'].get('forest', 0)
        self._villageKilled = raidlog['dread'].get('village', 0)
        self._castleKilled  = raidlog['dread'].get('castle', 0)
        
        self._woodsBal = (  sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+werewolf'))
                          - sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+bugbear')))
        self._villageBal = (  sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+zombie'))
                            - sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+ghost')))
        self._castleBal = (  sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+vampire'))
                           - sum(e['turns'] for e in eventFilter(events, r'defeated\s+(?:hot|cold|spooky|stench|sleaze)\s+skeleton')))
        
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
                    ctxt = self.getTag(2)

            if not self._villageDone:
                if self._drunk < 1000:
                    vtxt = ("[+{} drunk to open Village]"
                            .format(1000 - self._drunk))
                    if not self._castleDone:
                        ctxt = "[Castle closed]"
                else:
                    vtxt = self.getTag(1)
                    
            if not self._woodsDone:
                wtxt = self.getTag(0)
            txt = ", ".join([ktxt, wtxt, vtxt, ctxt])
            return txt
        return None
        
                
    def _availableCommands(self):
        return {'dread': "!dread: Display an overview of Dreadsylvania."}
    