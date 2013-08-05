from cwbot.modules.BaseDungeonModule import (BaseDungeonModule, eventFilter,
                                             eventDbMatch)


def dreadPercent(n):
    if n >= 1000:
        return "BOSS"
    return "{}%".format(max(0, min(99, int(n/10))))


class DreadOverviewModule(BaseDungeonModule):
    """ 
    Displays an overview of Dreadsylvania.
    NOTE: SHOULD BE HIGHER PRIORITY THAN OTHER MODULES IN DREADSYLVANIA
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-overview"

    _balance = {0: ['B', 'W'], 1: ['G', 'Z'], 2: ['S', 'V']}
    
    def __init__(self, manager, identity, config):
        nones = None, None, None
        self._woodsDone, self._villageDone, self._castleDone = nones
        self._woodsKilled, self._villageKilled, self._castleKilled = nones
        self._woodsBal, self._villageBal, self._castleBal = nones
        self._woodsLvl, self._villageLvl, self._castleLvl = nones
        self._drunk = None
        self._kisses = None
        self._lockedAreas = None
        self._locked = None
        
        super(DreadOverviewModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._lockedAreas = [r for r in self._db if r['zone'] == "(unlock)"]
        self._processLog(initData)


    def _areaInfo(self, areaNum):
        d = {}
        d['index'] = areaNum
        d['accessible'] = self._drunk >= areaNum * 1000
        d['killed'] = {0: self._woodsKilled, 
                       1: self._villageKilled, 
                       2: self._castleKilled}[areaNum]
        d['done'] = {0: self._woodsDone,
                     1: self._villageDone,
                     2: self._castleDone}[areaNum]
        d['balance'] = {0: self._woodsBal,
                        1: self._villageBal,
                        2: self._castleBal}[areaNum]
        if d['balance'] == 0:
            d['balanceWinning'] = ""
        else:
            idx = 0 if d['balance'] < 0 else 1
            d['balanceWinning'] = self._balance[areaNum][idx]
        d['level'] = {0: self._woodsLvl, 
                      1: self._villageLvl, 
                      2: self._castleLvl}[areaNum]
        d['fullname'] = {0: "The Woods", 
                         1: "The Village", 
                         2: "The Castle"}[areaNum]
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
            txt += " BOSS"
        else:
            txt += " {}%".format(int(d['killed']/10))
        
        # balance
        if d['balance'] == 0:
            txt += " ="
        else:
            txt += " " + d['balanceWinning'] + "+"
            txt += "{}".format(abs(d['balance']))
        return txt


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._woodsDone   = any(eventDbMatch(events, 
            {'category': "The Woods", 
             'zone': "(combat)",
             'subzone': "boss"}))
        self._villageDone = any(eventDbMatch(events, 
            {'category': "The Village", 
             'zone': "(combat)",
             'subzone': "boss"}))
        self._castleDone  = any(eventDbMatch(events, 
            {'category': "The Castle", 
             'zone': "(combat)",
             'subzone': "boss"}))
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
        
        self._woodsLvl   = 1 + sum(e['turns'] for e in eventFilter(events, "made the forest less"))
        self._villageLvl = 1 + sum(e['turns'] for e in eventFilter(events, "made the village less"))
        self._castleLvl  = 1 + sum(e['turns'] for e in eventFilter(events, "made the castle less"))
        
        self._kisses = raidlog['dread'].get('kisses', 0)
        
        self._locked = []
        for area in self._lockedAreas:
            if not any(eventDbMatch(events, area)):
                self._locked.append(area)
        return True

            
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
    
    
    def _eventCallback(self, eData):
        if eData.subject == "dread":
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
                self._eventReply(dict((dreadData[idx]['fullname'], 
                                       filteredData[idx]) 
                                      for idx in range(len(dreadData))))
            elif style == 'list':
                self._eventReply(dreadData)
            else:
                raise IndexError("invalid dread event style")
                
                
    def _availableCommands(self):
        return {'status': "!status: Display an overview of Dreadsylvania."}
    