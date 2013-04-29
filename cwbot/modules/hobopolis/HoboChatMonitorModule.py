import collections
import datetime
import pytz #@UnresolvedImport
import threading
from cwbot.modules.BaseHoboModule import BaseHoboModule
from cwbot.util.textProcessing import stringToBool
from cwbot.common.kmailContainer import Kmail

tz = pytz.timezone('America/Phoenix')
utc = pytz.utc


def utcToArizona(dt, fmtStr=None):
    dt_arizona = tz.normalize(dt.astimezone(tz))
    if fmtStr is None:
        return dt_arizona
    return dt_arizona.strftime(fmtStr)


def dtToStr(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def strToDt(s):
    t = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    t = t.replace(tzinfo=utc)
    return t
    

class ChatEvent(object):
    """ container used for tracking violations/cleared """
    
    def __init__(self, playerName, isViolation, data={}):
        self.time = datetime.datetime.now(utc)
        self.uname = playerName
        # True if violation, False if player is "cleared"
        self.violation = isViolation
        self.data = data
        

    def __repr__(self):
        s = "CLEAR" if self.violation else "X"
        return ("{1}{{t={0.time}, name={0.uname}, data={0.data}}}"
                .format(self, s))
    
    def __str__(self):
        return "X" if self.violation else "."
    
    
    def toDict(self):
        d = {'uname': self.uname, 'data': self.data, 
             'isViolation': self.violation, 'time': dtToStr(self.time)}
        return d
    
        
    @classmethod
    def fromDict(cls, d):
        obj = cls(d['uname'], d['isViolation'], d['data'])
        obj.time = strToDt(d['time'])
        return obj 
    
        
def numViolations(playerEventList):
    """How many violations has a player committed since they have been tracked?
    """
    return sum(1 for ce in playerEventList if ce.violation)


def cleared(playerEventList):
    """ return if a player is cleared (should no longer be monitored) """
    return any(not ce.violation for ce in playerEventList)


def violationTimeRanges(playerEventList):
    """ 
    Returns a list of time ranges in which a player was in violation. 
    Violations within 10 minutes of each other are considered to be in the 
    same time range.
    """
    violationTimes = [ce.time for ce in playerEventList if ce.violation]
    violationTimes.sort()
    if not violationTimes:
        return []
    elif len(violationTimes) == 1:
        return [(violationTimes[0], violationTimes[0])]
    
    # make a list of lists, each inner list has violation times in the 
    # same time range
    violationRanges = [[violationTimes[0]]]
    for t in violationTimes[1:]:
        lastTime = violationRanges[-1][-1]
        if (t - lastTime).total_seconds() <= 60 * 10:
            # add to same time range
            violationRanges[-1].append(t)
        else:
            # begin new time range
            violationRanges.append([t])
            
    # convert this list of lists to a list of tuples (beginTime, endTime)
    timeRanges = [(t[0], t[-1]) for t in violationRanges]
    return timeRanges
            

class HoboChatMonitorModule(BaseHoboModule):
    """ 
    A module that monitors /hobopolis to make sure that anyone adventuring
    in Hobopolis is also in the chat channel. A daily dispatch is sent to
    anyone with the hobo_mon_daily permission, with the names of players
    who are in violation.
    
    Configuration options:
    send_empty: if true, send a notification to administrators even if nobody
                violated hobopolis chat policy [default = false]
    num_warnings: the number of "strikes" a player must receive before
                  being marked in violation. Note that these strikes/warnings
                  are silent. They are there to make sure that players have
                  a few minutes to correct themselves if they accidentally
                  clicked something wrong. Note that a player is marked in
                  violation after they have used all their strikes and are
                  detected in hobopolis again. [default = 4]
    monitor_interval: how often, in seconds, to check chat to see what 
                      players are present. Don't set this too high, since it
                      requires sending a synchronous chat. 
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "hobochatmonitor"
    
    
    numWarnings = None
    checkDelay = None
    zones = ['Sewers', 
             'Town Square', 
             'Burnbarrel Blvd.', 
             'Exposure Esplanade', 
             'The Heap', 
             'The Ancient Hobo Burial Ground', 
             'The Purple Light District']
    
    
    def __init__(self, manager, identity, config):
        self._hoboAdventureCounts = collections.defaultdict(lambda: 0)
        self._sendEmpty = False
        self._violations = {}
        self._lastDispatch = None
        self._lastCheck = datetime.datetime.now(utc)
        self._lastEvents = {}
        self._newEvents = threading.Event()
        self._lock = threading.RLock()
        super(HoboChatMonitorModule, self).__init__(manager, identity, config)
    
    
    def _configure(self, config):
        try:
            self.numWarnings = int(config.setdefault('num_warnings', 4))
            self.checkDelay = int(config.setdefault('monitor_interval', 55))
        except ValueError:
            raise Exception(
                    "Error in module config: (HoboChatMonitorModule) "
                    "num_warnings, monitor_interval must be integral")
        try:
            self._sendEmpty = stringToBool(
                    config.setdefault('send_empty', 'false'))
        except ValueError:
            raise Exception(
                    "Error in module config: (HoboChatMonitorModule) "
                    "send_empty must be boolean")

        
    def initialize(self, state, initData):
        self._lastEvents = initData['events']
        self._hoboAdventureCounts.clear()
        
        for hobopolisevent in (item for item in self._lastEvents 
                               if item['category'] in self.zones):
            uname = hobopolisevent['userName']
            self._hoboAdventureCounts[uname] += hobopolisevent['turns']
            
        Now = datetime.datetime.now(utc)
        self._lastDispatch = strToDt(state['lastDispatch'])
        self._violations = dict((uname, map(ChatEvent.fromDict, vList))
                                for uname,vList in state['violations'].items()) 
        if (Now - self._lastDispatch) > datetime.timedelta(hours=25):
            self.cleanup()
            

    @property
    def state(self):
        with self._lock:
            st = {'lastDispatch': dtToStr(self._lastDispatch), 
                  'lastCheck': dtToStr(self._lastCheck)}
            v = dict((uname, map(ChatEvent.toDict, vList))
                     for uname,vList in self._violations.items())
            st['violations'] = v
            return st

    
    @property
    def initialState(self):
        return {'lastDispatch': dtToStr(datetime.datetime.now(utc)),
                'lastCheck': None,
                'violations': {}}

                    
    def getWho(self, chatRoom):
        """ Perform a /who query """
        whoVals = self.chat("/who {}".format(chatRoom), 
                            "DEFAULT", waitForReply=True, raw=True)
        allNames = set([item['userName'] for item in whoVals[0]['users']])
        self.debugLog("Users in /{}: {}".format(chatRoom, ', '.join(allNames)))
        return allNames

    
    def _processLog(self, events):
        with self._lock:
            self._lastEvents = events
            self._newEvents.set()
        return True

        
    def _processCommand(self, msg, cmd, args):
        if cmd in ["chatmonitor"]:
            if "dispatch" in args.lower():
                try:
                    self.dispatchKmail(msg['userId'], 
                                       dailyDigest=True, noThrow=False)
                    return "Dispatch done."
                except Exception as e:
                    return "Error dispatching ({}).".format(e.args[0])
            else:
                lastD = self._lastDispatch
                lastDStr = ("unknown time" if lastD is None 
                            else utcToArizona(lastD, '%c'))
                violators = [u for u,v in self._violations.items() 
                             if numViolations(v) > self.numWarnings]
                nViolations = len(violators)
                if nViolations == 0:
                    return ("No violations since last daily dispatch at {}."
                            .format(lastDStr))
                else:
                    return ("{} players in violation since last daily "
                            "dispatch at {}: {}"
                            .format(nViolations, lastDStr, 
                                    ', '.join(violators)))
            if "clear" in args.lower():
                self._violations.clear()
                return ("Violations cleared.")
        return None

    
    def reset(self, _events):
        with self._lock:
            self._hoboAdventureCounts.clear()
            self._newEvents.set()


    def dispatch(self):
        with self._lock:
            self.log("Dispatching chat monitor Kmails...")
            admins = self.properties.getAdmins('hobo_mon_daily')
            n = 0
            for uid in admins:
                success = self.dispatchKmail(uid, 
                                             dailyDigest=self._sendEmpty, 
                                             noThrow=True)
                if success:
                    n += 1
            return n


    def dispatchKmail(self, uid, dailyDigest=False, noThrow=False):
        with self._lock:
            now_ = datetime.datetime.now(utc)
            txt = ("Hobopolis chat monitor violations for {} "
                   "(* indicates player in clan chat):\n\n"
                   .format(utcToArizona(now_, '%x')))
            tf1 = "%d %b %I:%M %p"
            tf2 = "%I:%M %p"
            
            violators = [u for u,v in self._violations.items() 
                         if numViolations(v) > self.numWarnings]    
            if len(violators) == 0 and not dailyDigest:
                return    
            if len(violators) > 0:
                violateStrs = []
                self.log("Violators: {}".format(violators))
                for uname in violators:
                    vList = self._violations[uname]
                    timeRanges = [[utcToArizona(rBegin, tf1),
                                   utcToArizona(rEnd, tf2)]
                                   for rBegin,rEnd 
                                       in violationTimeRanges(vList)]
                    s = uname + " in time range(s): "
                    s += ", ".join("({0[0]} - {0[1]})".format(range_)
                                   for range_ in timeRanges)
                    
                    # mark players in clan chat (but not in hobopolis)
                    if any(v.violation and v.data.get('inClan', False) 
                           for v in vList):
                        s = "*" + s
    
                    # note if they joined /hobopolis
                    timeJoin = next((v.time for v in vList if not v.violation), 
                                    None)
                    if timeJoin is not None:
                        s += ("; joined /hobopolis at {}"
                              .format(utcToArizona(timeJoin, tf1)))
                        
                    violateStrs.append(s)
                txt += "\n".join(violateStrs)
            else:
                txt += "No users were in violation of Hobopolis chat rules."
            k = Kmail(uid=uid, text=txt)
            self.log("Sending HoboChatMon kmail to {}...".format(uid))
            self.sendKmail(k)
            return True

        
    def registerViolation(self, userName, inClanChat):
        with self._lock:
            violations = self._violations.get(userName, [])
            violations.append(
                            ChatEvent(userName, True, {'inClan': inClanChat}))
            numV = numViolations(violations)
            self.log("Detected {} adventuring in hobopolis without being "
                     "in channel (violation number #{})!"
                     .format(userName, numV))
            self._violations[userName] = violations 


    def registerClear(self, userName):
        with self._lock:
            violations = self._violations.get(userName, [])
            violations.append(ChatEvent(userName, False))
            self._violations[userName] = violations 
        self.debugLog("Detected {} adventuring in hobopolis while in channel."
                      .format(userName))


    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            if eData.to is None:
                self._eventReply({
                        'warning': '(omitted for general state inquiry)'})
            else:
                self._eventReply(self.state)
        elif s == "shutdown" and eData.fromIdentity == "__system__":
            if not self.properties.debug:
                with self._lock:
                    self._lastDispatch = datetime.datetime.now(utc)
                    nDispatch = self.dispatch()
                    if nDispatch > 0:
                        self._violations.clear()
    
    
    def _availableCommands(self):
        return {'chatmonitor': "Display players who have violated Hobopolis "
                               "chat rules. Use '!chatmonitor dispatch' to "
                               "immediately run the daily dispatch. Use "
                               "'!chatmonitor clear' to clear violator list."}


    def _getAdventureCounts(self, events):
        """ Get a defaultdict of (userName: turn) pairs of turns spent in
        Hobopolis. """
        advCounts = collections.defaultdict(lambda: 0)
        for hobopolisevent in (item for item in events 
                               if item['category'] in self.zones):
            uname = hobopolisevent['userName']
            advCounts[uname] += hobopolisevent['turns']
        return advCounts
        

    def _getUsersToCheck(self, events, adventureCounts):
        """ Return a pair (toCheck, cleared) of sets: toCheck is a set of
        usernames to check if they are in chat; cleared is a set of usernames
        that have already been cleared. """
        toCheck = set([])
        clearedSet = set([])
        for uname,turns in adventureCounts.items():
            if turns > self._hoboAdventureCounts.get(uname, 0):
                if cleared(self._violations.get(uname, [])):
                    clearedSet.add(uname)
                else:
                    toCheck.add(uname)
        return (toCheck, clearedSet)
      

    def _heartbeat(self):
        # we do the actual checking here
        with self._lock:
            # check if enough time has elapsed
            Now = datetime.datetime.now(utc)
            timeDiff = (Now - self._lastCheck).total_seconds()
            if timeDiff < self.checkDelay:
                return
            self._lastCheck = Now
            
            # check if new events have arrived 
            if not self._newEvents.is_set():
                return
            
            # check if anyone needs to be checked 
            self._newEvents.clear()
            advCounts = self._getAdventureCounts(self._lastEvents)
            toCheck = self._getUsersToCheck(self._lastEvents, advCounts)[0]
            if len(toCheck) == 0:
                return        
        # check users in chat -- this is done outside of a lock context
        # to avoid blocking the main thread 
        allNames = self.getWho("hobopolis")
        clanNames = self.getWho("clan")

        with self._lock:
            # re-read the events, in case they changed
            self._newEvents.clear()
            advCounts = self._getAdventureCounts(self._lastEvents)
            (toCheck, clearedSet) = self._getUsersToCheck(self._lastEvents, 
                                                          advCounts)
    
            self._hoboAdventureCounts = advCounts
            self.debugLog("hobomon to check: {}; cleared: {}"
                          .format(', '.join(toCheck), ', '.join(clearedSet)))

            violation = False
            for uname in toCheck:
                if uname not in allNames:
                    inClanChat = uname in clanNames
                    self.registerViolation(uname, inClanChat)
                    violation = True
                else:
                    self.registerClear(uname)
            if violation:
                self.debugLog("Currently in channel: {}".format(allNames))
