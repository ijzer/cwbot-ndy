import math
import re
from cwbot.modules.BaseHoboModule import (BaseHoboModule, killPercent, 
                                          eventFilter)


class AhbgModule(BaseHoboModule):
    """ 
    A module for tracking Ancient Hobo Burial Ground dances and observations.
    
    This module is essentially stateless, since all information about zone
    progress is obtainable from the logs.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "burial"
    
    # approximate values of dances. computed from a collection of logs
    # using a least-squares linear regression
    danceVals = [1.0, 
                 4.0, 4.5, 4.5, 4.5,
                 7.5, 7.5, 7.5,
                 11 , 11 , 11 , 11 , 11 , 11,
                 7.5, 7.5, 7.5,
                 4.5, 4.5, 4.0, 4.0,
                 1.0, 1.0] # the 1's should really be 0.5, but I rounded them
    cumDanceVals = [sum(danceVals[0:i]) for i in range(len(danceVals)+1)]

    
    def __init__(self, manager, identity, config):
        self._watches = {} # maps playerName -> # of watches (0, 1, 2, 3)
        self._dances = {}  # maps playerName -> # of dances (0 to 22)
        self._availableDances = None
        self._killed = None
        self._open = False
        self._ahbgDone = False
        super(AhbgModule, self).__init__(manager, identity, config)


    def initialize(self, state, initData):
        self._open = state['open']
        self._processLog(initData)

            
    @property
    def state(self):
        return {'watches': dict((u,w) for u,w in self._watches.items() 
                                      if w != 0),
                'dances': self._dances,
                'availableDances': self._availableDances,
                'open': self._open}

    
    @property
    def initialState(self):
        return {'open': False}

    
    def getTag(self):
        ahbgPercent = killPercent(self.getDone())
        if self._ahbgDone:
            return "[AHBG done]"
        if self._open:
            return "[AHBG %d%%]" % (ahbgPercent)
        return "[AHBG closed]"
            

    def _processLog(self, raidlog):
        events = raidlog['events']
        # first: check number of dances available 
        #        = 5 * flim-flams - dances so far
        # also see who has danced so far.
        self._watches = dict((w['userName'], w['turns']) 
                             for w in eventFilter(
                                 events, "watched some zombie hobos dance"))
        self._dances = dict((d['userName'], d['turns']) 
                            for d in eventFilter(events, r'busted .* move'))

        self._availableDances = (
                5 * sum(f['turns'] for f in eventFilter(
                    events, "flimflammed some hobos"))
                -   sum(e['turns'] for e in eventFilter(
                    events, "watched some zombie hobos dance",
                            r'busted .* move',
                            "failed to impress as a dancer")))

        # any player in hobopolis is added to watch list             
        for hoboplayer in set(item['userName'] for item in events 
                              if 'userName' in item):
            if hoboplayer not in self._watches:
                self._watches[hoboplayer] = 0

        self._killed = (      
                  sum(k['turns'] for k in eventFilter(
                      events, r'defeated +Spooky hobo'))
            - 9 * sum(t['turns'] for t in eventFilter(
                      events, r'raided .* tomb')))

        self._ahbgDone = any(eventFilter(events, r'defeated +Zombo'))

        if not self._open:
            if any(item['category'] == 'The Ancient Hobo Burial Ground' 
                   for item in events):
                self._open = True
        return True


    def getDanceDamage(self, numDancesFromPlayer):
        if numDancesFromPlayer < 0:
            numDancesFromPlayer = 0
        if numDancesFromPlayer > 23:
            numDancesFromPlayer = 23
        return self.cumDanceVals[numDancesFromPlayer]
        

    def getDone(self):
        doneAmt = self._killed
        for _user,dances in self._dances.items():
            doneAmt += self.getDanceDamage(dances)
        return round(doneAmt)
    
    
    def danceProgressStr(self, uname):
        watches = self._watches.get(uname, 0)
        dances = self._dances.get(uname, 0)
        if watches < 3:
            return ("{} {} has watched {}/3 zombie dances. "
                    "{} dances available."
                    .format(self.getTag(), uname, watches, 
                            self._availableDances))                
        elif dances == 0:
            return ("{} {} can start busting a move! {} dances available."
                    .format(self.getTag(), uname, self._availableDances))                
        elif dances < 23:
            playerDamage = math.floor(self.getDanceDamage(dances))
            return ("{} {} has danced {}/23 times, defeating a total "
                    "of {} hobos. {} dances available."
                    .format(self.getTag(), uname, dances, 
                            int(round(playerDamage)), self._availableDances))
        else:
            return ("{} {}'s dances are no longer effective. "
                    "{} dances available."
                    .format(self.getTag(), uname, self._availableDances))

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if self._ahbgDone:
            return None
        # these don't do anything but change the number of dances available
        if any(item in txt for item in [
                "flim-flammed some hobos in the Purple Light District",
                "failed to bust a move"]):
            return ("{} {} dances available."
                    .format(self.getTag(), self._availableDances))
        
        elif ("busted a move in the Burial Ground" in txt or
              "spent some time observing zombie dancers" in txt):
            m = re.search(r'^(.*) (?:busted a move|spent some time)', txt)
            if m is not None:
                uname = m.group(1)
                return self.danceProgressStr(uname)
        return None


    def getUname(self, args):
        # get the username from the `!ahbg playername` command 
        
        matches = []
        arg = ''.join(args.lower().split()) # remove spaces, do lower case
        for dancename in (item for item in self._watches.keys()):
            currentName = ''.join(dancename.lower().split())
            if currentName == arg:
                return dancename
            if arg in currentName:
                matches.append(dancename)
        if len(matches) == 1:
            return matches[0]
        return None

        
    def _processCommand(self, msg, cmd, args):
        if cmd in ["ahbg", "burial"]: 
            if not self._dungeonActive():
                return ("The ghostly apparition of Hodgman is haunting the "
                        "burial ground now! Best to leave it alone.")
            if self._ahbgDone:
                return ("{} Zombo is dead now. Undead? Redead? "
                        "Don't think about it too hard.".format(self.getTag()))
            uname = self.getUname(args) 
            if uname is None and args is None or args.strip() == "":
                if 'userName' not in msg: 
                    return ("{} {} dances available."
                            .format(self.getTag(), self._availableDances))
                uname = msg['userName']
            elif uname is None:
                    return ("{} There is no unique username matching '{}' "
                            "with any Hobopolis activity. (If you want your "
                            "own activity, use '!ahbg' or '!ahbg()'.)" 
                            .format(self.getTag(), args))
            return self.danceProgressStr(uname)
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
        return {'ahbg': "!ahbg: Display information about the Ancient Hobo "
                        "Burial Ground.",
                'burial': None}
