from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventDbMatch
from cwbot.common.exceptions import FatalError
from cwbot.common.kmailContainer import Kmail
from cwbot.kolextra.request.UserProfileRequest import UserProfileRequest
import pytz
from copy import deepcopy
import itertools
from collections import defaultdict
import datetime
import time
import re
import threading
from pastebin_python import PastebinPython
from pastebin_python.pastebin_exceptions \
                     import (PastebinBadRequestException,
                             PastebinNoPastesException, PastebinFileException)
from pastebin_python.pastebin_constants import PASTE_PUBLIC, EXPIRE_1_MONTH
from pastebin_python.pastebin_formats import FORMAT_NONE



def _nameKey(x):
    return "".join(x.split()).strip().lower()


_maxLen = 33
_format = "{:33}{:33}{:33}"
_areas = {0: 'The Woods', 1: 'The Village', 2: 'The Castle'}
_shortestName = 4
_tz = pytz.timezone('America/Phoenix')

class DreadTimelineModule(BaseDungeonModule):
    """ 
    creates a timeline of dreadsylvania.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-timeline"
    
    def __init__(self, manager, identity, config):
        self._snapshots = None
        self._lastComplete = None
        self._lastRaidlog = None
        self._apikey = None
        self._pastes = None
        self._initialized = False
        self._readyForTimeline = threading.Event()
        self._timelineLock = threading.Lock()
        super(DreadTimelineModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._snapshots = state['snapshots']
        self._lastComplete = state['last']
        pastes = state.get('pastes', {})
        self._pastes = {k: v for k,v in pastes.items()
                        if v.get('time', 0) > time.time() - 31 * 24 * 60 * 60}
        self._processLog(initData)
        self._initialized = True
        
    
    def _configure(self, config):
        self._apikey = config['pastebin_api_key']
        
    
    @property
    def initialState(self):
        return {'snapshots': [], 
                'last': [0, 0, 0], 
                'pastes': {}}
    
    
    @property
    def state(self):
        return {'snapshots': self._snapshots,
                'last': self._lastComplete,
                'pastes': self._pastes}


    def _processLog(self, raidlog):
        with self._timelineLock:
            events = deepcopy(raidlog['events'])
            self._lastRaidlog = deepcopy(raidlog)
            dvid = raidlog.get('dvid')
            if not self._dungeonActive():
                if dvid is not None and str(dvid) not in self._pastes:
                    if self._initialized:
                        self._readyForTimeline.set() 
            d = self._raiseEvent("dread", "dread-overview", 
                                           data={'style': 'list',
                                                 'keys': ['killed']})
            killed = [data['killed'] for data in d[0].data]
            roundedKilled = map(lambda x: (x // 50) * 50, killed)
            if roundedKilled > self._lastComplete:
                self._lastComplete = roundedKilled
                self._snapshots.append(self._getNewEvents(events))
            return True
    
    
    def _getNewEvents(self, events):
        t1 = time.time()

        newEvents = []
        
        # first, get a list of all db entries and players
        dbEntries = []
        players = set()
        for e in events:
            if e['db-match'] not in dbEntries:
                dbEntries.append(e['db-match'])
            players.add(e['userId'])
                
        # now, loop over all players and db entries
        for dbm in dbEntries:
            
            # skip unmatched events
            if not dbm:
                continue
            
            matchingDoneEvents = list(eventDbMatch(
                                    itertools.chain.from_iterable(
                                                self._snapshots), dbm))
            matchingNewEvents = list(eventDbMatch(events, dbm))
            for uid in players:
                matchesUser = lambda x: x['userId'] == uid
                playerEvents = filter(matchesUser, matchingNewEvents)
                doneEvents = filter(matchesUser, matchingDoneEvents)
                playerTotalEvents = sum(pe['turns'] for pe in playerEvents)
                doneTotalEvents = sum(de['turns'] for de in doneEvents)
                eventDiff = playerTotalEvents - doneTotalEvents
                if eventDiff < 0:
                    self._log.warn("Snapshot: {}\nevents: {}"
                                   .format(self._snapshots, events))
                    raise RuntimeError("Error: detected {} events but "
                                       "{} in snapshot for user {} and "
                                       "db entry {}"
                                       .format(playerTotalEvents,
                                               doneTotalEvents,
                                               uid,
                                               dbm))

                if eventDiff > 0:
                    newEvent = deepcopy(playerEvents[0])
                    newEvent['turns'] = eventDiff
                    newEvents.append(newEvent)
        self.debugLog("Built new DB entries in {} seconds"
                      .format(time.time() - t1))
        return newEvents
    
    
    def _timelineHeader(self, events, nameShorthands):
        r = UserProfileRequest(self.session, self.properties.userId)
        d = self.tryRequest(r)
        clanName = d.get('clanName')
        kisses = self._lastRaidlog.get('dread', {}).get('kisses', "?")

        users = {e['userId']: e['userName'] for e in events if e['db-match']}
        timeString = (datetime.datetime.now()
                      .strftime("%A, %B %d %Y %I:%M%p UTC"))
        timeHeader = ("Timeline for {}-kiss Dreadsylvania instance "
                      "in {}\nReport generated {}\n\n"
                      .format(kisses, clanName, timeString))
        nameHeader = ("The following name abbreviations are used in this "
                      "report:\n\n{}\n\n"
                      .format("\n".join("{} = {} (#{})"
                                        .format(shortName, users[uid], uid)
                                        for uid, shortName
                                            in nameShorthands.items())))
        topHeader = _format.format(_areas[0], _areas[1], _areas[2]) + "\n"
        return timeHeader + nameHeader + topHeader
    
    
    # create a timeline.
    # the timeline is a list of time entries.
    # each timeentry looks like this:
    # {'kills': [K1, K2, K3], # kills in 3 areas
    #  'text': [[txt1, txt2], [txt1, txt2], [txt1, txt2]]} # text for 3 areas
    def _eventTimeline(self, events, nameShorthands):
        timeline = []
        timelineKills = [0,0,0]
        newEvents = self._getNewEvents(events)
        t1 = time.time()
        snapshots = deepcopy(self._snapshots)
        snapshots.append(newEvents)
        for snapshot in snapshots:
            timelineText = []
            for area in range(3):
                txtList = []
                areaName = _areas[area]
                
                # first, let's find kills
                kills = defaultdict(int)
                killEvents = eventDbMatch(snapshot, {'category': areaName,
                                                     'zone': "(combat)",
                                                     'subzone': "normal"})
                for e in killEvents:
                    timelineKills[area] += e['turns']
                    kills[e['userId']] += e['turns']
                for uid, k in kills.items():
                    txtList.append(" {}: {} kills"
                                   .format(nameShorthands[uid], k))
                    
                bossEvents = eventDbMatch(snapshot, {'category': areaName,
                                                     'zone': "(combat)",
                                                     'subzone': "boss"},
                                                    {'category': areaName,
                                                     'zone': "(combat)",
                                                     'subzone': "boss_defeat"})
                for e in bossEvents:
                    txtList.append("*{} {}"
                                   .format(nameShorthands[e['userId']], 
                                           e['event']))
                    
                allEvents = eventDbMatch(snapshot, {'category': areaName})
                for e in allEvents:
                    dbm = e['db-match']
                    if dbm.get('zone') == "(combat)":
                        continue
                    if dbm.get('unique_text', "").strip() != "":
                        txtList.append("*{} got {} at {}"
                                       .format(nameShorthands[e['userId']],
                                               dbm['code'],
                                               dbm['zone']))
                    elif dbm.get('zone') == "(unlock)":
                        txtList.append("-{} unlocked {}"
                                       .format(nameShorthands[e['userId']],
                                               dbm['subzone']))                        
                    else:
                        txtList.append("-{} did {} at {}"
                                       .format(nameShorthands[e['userId']],
                                               dbm['code'],
                                               dbm['zone']))
                txtList.sort()
                timelineText.append(txtList)
            timeline.append({'kills': deepcopy(timelineKills), 
                             'text': timelineText})
        self.debugLog("Built timeline in {} seconds"
                      .format(time.time() - t1))
        return timeline
    
    
    # convert a timeline to a multiline string to display.
    def _timelineString(self, timeline):
        def balanceLines(alines, extendString):
            totalLines = map(len, alines)
            maxLines = max(totalLines)
            for lines in alines:
                lines.extend([extendString] * (maxLines - len(lines)))

        t1 = time.time()
        areaLines = [["-+- 0% complete"], 
                     ["-+- 0% complete"], 
                     ["-+- 0% complete"]] * 3
        lastKills = [0, 0, 0]
        for t in timeline:
            for area in range(3):
                for txt in t['text'][area]:
                    areaLines[area].append(" | {}".format(txt))
            balanceLines(areaLines, " |")
            for area in range(3):
                roundedKills = (t['kills'][area] // 50) * 50
                if roundedKills > lastKills[area]:
                    print("Area {}, last={}, new={}"
                          .format(area, lastKills[area], roundedKills))
                    lastKills[area] = roundedKills
                    areaLines[area].append("-+- {}% complete"
                                           .format(int(roundedKills // 10)))
                else:
                    print("Area {}, last={}, current={}"
                          .format(area, lastKills[area], roundedKills))
            balanceLines(areaLines, "-+-")
        
        # now format it correctly
        for a in range(3):
            areaLines[a] = map(lambda x: x[:_maxLen], areaLines[a])
        lines = zip(*areaLines)
        txtLines = [_format.format(*t) for t in lines]
        self.debugLog("Built timeline string in {} seconds"
                      .format(time.time() - t1))
        return "\n".join(line.rstrip() for line in txtLines)
            

    def _getShortenedNames(self, events):
        users = {e['userId']: e['userName'] for e in events if e['db-match']}
        userNamesFixed = {uid: ''.join(name.split()) 
                          for uid,name in users.items()}
        userNamesDone = {}
        nameLength = _shortestName
        while userNamesFixed:
            counts = defaultdict(int)
            # shorten names
            newUserNames = {uid: name[:nameLength]
                            for uid, name in userNamesFixed.items()}
            for name in newUserNames:
                counts[name] += 1
            userNamesDone.update({uid: name 
                                  for uid, name in newUserNames.items()
                                  if counts[name] <= 1})
            userNamesFixed = {uid: name 
                              for uid, name in userNamesFixed.items()
                              if counts[newUserNames[uid]] > 1}
        return userNamesDone
            
                
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
    
    
    def _processCommand(self, message, cmd, args):
        if cmd == "timeline":
            dvid = self._lastRaidlog.get('dvid')
            if (self._dungeonActive() 
                    or dvid is None
                    or str(dvid) not in self._pastes):
                return ("You can't get the timeline while the dungeon is "
                        "active.")
            data = self._pastes[str(dvid)]
            if data['error']:
                return ("Error with timeline: {}".format(data['url']))
            return "Timeline for current instance: {}".format(data['url'])
        elif cmd == "timelines":
            timelines = self._pastes.values()
            timelines.sort(key=lambda x: x['time'], reverse=True)
            strings = []
            for item in timelines:
                urlText = item['url'] if not item['error'] else "ERROR"
                dvidText = item['dvid']
                dt_utc = datetime.datetime.fromtimestamp(item['time'],
                                                         pytz.utc)
                dt_az = dt_utc.astimezone(_tz)
                timeText = dt_az.strftime("%a %d %b %y")
                kisses = item['kisses']
                strings.append("{} - {} [{} kisses]: {}"
                               .format(timeText, dvidText, kisses, urlText))
            sendString = ""
            for string in strings:
                if len(string) + len(sendString) > 1500:
                    break
                sendString += string + "\n"
            if sendString == "":
                return "No timelines in memory."
            self.sendKmail(Kmail(message['userId'], 
                                 "Here are the most recent Dreadsylvania "
                                 "instances:\n\n{}".format(sendString)))
            return "Timelines sent."
            
    
    def _heartbeat(self):
        if self._readyForTimeline.is_set():
            with self._timelineLock:
                self._readyForTimeline.clear()
                dvid = self._lastRaidlog.get('dvid')
                if dvid is None or str(dvid) in self._pastes:
                    return
                self._createTimeline()
                
                
    def _createTimeline(self):
        dvid = self._lastRaidlog.get('dvid')
        kisses = self._lastRaidlog.get('dread', {}).get('kisses', "?")
        if dvid is None:
            return
        shortNames = self._getShortenedNames(self._lastRaidlog['events'])
        header = self._timelineHeader(self._lastRaidlog['events'], shortNames)
        timeline = self._eventTimeline(self._lastRaidlog['events'], shortNames)
        body = self._timelineString(timeline)
        pbin = PastebinPython(api_dev_key=self._apikey)
        try:
            result = pbin.createPaste(header + body, 
                                  api_paste_format=FORMAT_NONE,
                                  api_paste_private=PASTE_PUBLIC,
                                  api_paste_expire_date=EXPIRE_1_MONTH)
            resultError = re.search(r'https?://', result) is None
            self._pastes[str(dvid)] = {'url': result,
                                       'time': time.time(),
                                       'dvid': dvid,
                                       'error': resultError,
                                       'kisses': kisses}
            if resultError:
                self.log("Error with timeline: {}".format(result))
        except (PastebinBadRequestException, 
                PastebinFileException, 
                PastebinNoPastesException) as e:
            self._pastes[str(dvid)] = {'url': e.message,
                                       'time': time.time(),
                                       'dvid': dvid,
                                       'error': True,
                                       'kisses': kisses}
            self.log("Error with timeline: {}".format(e.message))
            
            
    def reset(self, initData):
        self._readyForTimeline.clear()
        newState = self.initialState
        newState['pastes'] = self._pastes
        self.initialize(newState, initData)
        
        
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            if eData.to is None:
                self._eventReply({
                        'warning': '(omitted for general state inquiry)'})
            else:
                self._eventReply(self.state)

        
    def _availableCommands(self):
        return {'timeline': "!timeline: Show a timeline of the Dreadsylvania "
                            "instance."}
    