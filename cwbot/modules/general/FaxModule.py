import time
import calendar
import re
import urllib2
import socket
import pytz #@UnresolvedImport
from urllib2 import HTTPError, URLError
from collections import defaultdict
from fuzzywuzzy import fuzz #@UnresolvedImport
from cwbot.modules.BaseChatModule import BaseChatModule
import kol.util.Report
from kol.request.ClanLogRequest import ClanLogRequest, CLAN_LOG_FAX
import cwbot.util.DebugThreading as threading
from cwbot.util.textProcessing import stringToBool


tz = pytz.timezone('America/Phoenix')
utc = pytz.utc

def utcTime():
    """ Epoch time in UTC """
    return calendar.timegm(time.gmtime())


class FaxMonsterEntry(object):
    """ container class used to hold fax codes """
    def __init__(self, name, code):
        self.name = name.strip()
        self.code = code.strip().lower()
        self._otherNames = []
    
    @property
    def nameList(self):
        """ list of all possible names to reference this object, including
        the .name, .code, and all the ._otherNames """
        return [self.name.lower(), self.code] + self._otherNames
    
    def addAlias(self, name):
        """ an alias -- not the name or code, but another name for reference 
        """
        self._otherNames.append(name.strip().lower())

    def contains(self, name):
        return name.strip().lower() in self.nameList
    
    def __repr__(self):
        return "{{{}: {}}}".format(self.nameList[0], 
                                 ', '.join(self.nameList[1:]))
        
    def toDict(self):
        return {'name': self.name, 'code': self.code, 
                'other': self._otherNames}
        
    @classmethod
    def fromDict(cls, d):
        obj = cls(d['name'], d['code'])
        obj._otherNames = d['other']
        return obj


class FaxModule(BaseChatModule):
    """ 
    A module that handles faxing, including fax lookup for unknown monster
    codes, reporting on incoming faxes, and reporting what's in the fax
    machine.
    
    Configuration options:
    announce - set to true to use announcements (uses lots of bandwidth!)
    allow_requests - allows !fax MONSTERNAME
    fax_check_interval - frequency of checking if a new fax arrived [def. = 15]
    faxbot_timeout - time to wait until giving up on a fax request [def. = 90]
    url_timeout - time to try to load forum page before timing out [def. = 15]
    faxbot_id_number - player id number of faxbot [default = 2194132]
    fax_list_url - url of kolspading faxbot list [def. = http://goo.gl/Q352Q]
    [[[[alias]]]]
        ALIASNAME - ALIAS (monster alias name)
        
    Configuration example:
    [[[[alias]]]]
        lobsterfrogman - lfm    # now you can type '!fax lfm' 
    """
        
    requiredCapabilities = ['chat']
    _name = "fax"
    
    __lock = threading.RLock()
    _faxWait = 60
    
    _checkFrequency = None
    _abortTime = None
    timeout = None
    faxbot_uid = None
    fax_list_url = None


    def __init__(self, manager, identity, config):
        self._initialized = False
        self._announce = False
        self._allowRequests = True
        self._downloadedFaxList = False
        self._faxList = {}
        self._alias = None
        super(FaxModule, self).__init__(manager, identity, config)
        # last request the bot made to FaxBot
        self._lastRequest, self._lastRequestTime = None, None
        # last monster in the fax log
        self._lastFax, self._lastFaxTime = None, None
        # username of last faxer / last time bot got a message from faxbot 
        self._lastFaxUname, self._lastFaxBotTime = None, None
        self._noMoreFaxesToday = False
        self._lastFaxCheck = 0
        self.updateLastFax()
    
    
    def _configure(self, config):
        try:
            self._checkFrequency = int(
                    config.setdefault('fax_check_interval', 15))
            self._abortTime = int(config.setdefault('faxbot_timeout', 90))
            self.timeout = int(config.setdefault('url_timeout', 15))
            self.faxbot_uid = int(
                    config.setdefault('faxbot_id_number', 2194132))
            self.fax_list_url = config.setdefault('fax_list_url', 
                                                  "http://goo.gl/Q352Q")
            self._announce = stringToBool(config.setdefault('announce', 
                                                            'false'))
            self._lite = stringToBool(config.setdefault('allow_requests',
                                                        'true'))
        except ValueError:
            raise Exception("Fax Module config error: "
                            "fax_check_interval, faxbot_timeout, "
                            "url_timeout, faxbot_id_number must be integral")
        self._alias = config.setdefault('alias', {'lobsterfrogman': 'lfm'})


    def initialize(self, state, initData):
        newFaxList = map(FaxMonsterEntry.fromDict, state['faxes'])
        self._faxList = dict((e.code, e) for e in newFaxList)


    @property
    def state(self):
        return {'faxes': map(FaxMonsterEntry.toDict, self._faxList.values())}

    
    @property
    def initialState(self):
        return {'faxes': []}
            
    
    def initializeFaxList(self):
        """ download and parse the list of fax monsters from the thread
        on kolspading.com """
        self.log("Initializing fax list...")
        numTries = 3
        success = False
        for i in range(numTries):
            try:
                # download and interpret the page
                txt = urllib2.urlopen(self.fax_list_url, 
                                      timeout=self.timeout).read()
                for c in range(32,128):
                    htmlCode = "&#{};".format(c)
                    txt = txt.replace(htmlCode, chr(c))
                matches = re.findall(r'>([^>/]+): /w FaxBot ([^<]+)<', txt)
                self._faxList = dict((b.strip().lower(), FaxMonsterEntry(a,b)) 
                                     for a,b in matches)
                self.log("Found {} available faxes."
                         .format(len(self._faxList)))
                success = True
                break
            except (HTTPError, URLError, socket.timeout) as e:
                self.log("Error loading webpage for fax list: {}: {}"
                         .format(e.__class__.__name__, e.args[0]))
                if i + 1 != numTries:
                    time.sleep(1)
        if not success:
            self.log("Failed to initialize fax list; using backup ({} entries)"
                     .format(len(self._faxList)))
        for code,alias in self._alias.items():
            code = code.strip().lower()
            if code in self._faxList:
                self._faxList[code].addAlias(alias)
            elif len(self._faxList) > 0:
                raise Exception("Invalid fax alias (no such fax code): "
                                "{} -> {}".format(alias, code))
            
        
    def checkAbort(self):
        """ Check if a request is too old and should be aborted """
        with self.__lock:
            if self._lastRequest is not None and not self._noMoreFaxesToday:
                timeDiff = utcTime() - self._lastRequestTime
                if timeDiff > self._abortTime:
                    self.chat("FaxBot has not replied to my request. "
                              "Please try again.")
                    self.log("Aborting fax request for '{}'"
                             .format(self._lastRequest))
                    self._lastRequest = None
                    self._lastRequestTime = None
    
        
    def checkForNewFax(self, announceInChat=True):
        """ See if a new fax has arrived, and possibly announce it if it has. 
        """
        with self.__lock:
            self._lastFaxCheck = utcTime()
            replyStr = None
            lastFaxTime = self._lastFaxTime
            lastFaxUname = self._lastFaxUname
            lastFaxMonster = self._lastFax
            event = self.updateLastFax()
            if (self._lastFax is not None and 
                    (lastFaxTime != self._lastFaxTime or 
                     lastFaxUname != self._lastFaxUname or 
                     lastFaxMonster != self._lastFax)):
                self.log("Received new fax {}".format(event))
                replyStr = ("{} has copied a {} into the fax machine."
                            .format(self._lastFaxUname, self._lastFax))
                if announceInChat:
                    self.chat(replyStr) 
                if event['userId'] == self.faxbot_uid:
                    self._lastRequest = None
                    self._lastRequestTime = None
            if self._noMoreFaxesToday:
                if utcTime() - self._lastRequestTime > 3600 * 3:
                    self._noMoreFaxesToday = False
                    self._lastRequestTime = None
            self.checkAbort()
            return replyStr

        
    def faxMonster(self, args, isPM):
        """Send a request to FaxBot, if not waiting on another request.
        This function is a wrapper for fax() and handles the fax lookup
        and faxbot delay. """
        with self.__lock:
            self.checkAbort()
            last = self._lastFaxBotTime
            if last is None:
                last = utcTime() - self._faxWait - 1
            if self._lastRequest is not None:
                return ("I am still waiting for FaxBot to reply "
                        "to my last request.")
            timeSinceLast = utcTime() - last
            if timeSinceLast >= self._faxWait or isPM:
                if len(self._faxList) > 0:
                    return self.faxFromList(args, isPM)
                monstername = args.split()[0]
                return self.fax(monstername, monstername, 
                                "(fax lookup unavailable) ", isPM)
            else:
                return ("Please wait {} more seconds to request a fax."
                        .format(round(self._faxWait - timeSinceLast)))
        

    def fax(self, monstercode, monstername, prependText="", 
            isPM=False, force=False):
        ''' This function actually performs the fax request '''
        stripname = re.search(r'(?:Some )?(.*)', monstername).group(1)
        if isPM:
            return ("After asking in chat, you can manually request a {} "
                    "with /w FaxBot {}".format(monstername, monstercode))
        elif not self._allowRequests:
            return ("Code to request a {}: "
                    "/w FaxBot {}".format(monstername, monstercode))
        with self.__lock:
            self.log("{}Requesting {}...".format(prependText, monstername))
            self.checkForNewFax(self._announce)
            if (self._lastFax.lower().strip() == stripname.lower().strip() 
                    and not force):
                self.log("{} already in fax.".format(monstercode))
                return ("{} There is already a(n) {} in the fax machine. "
                        "Use '!fax {} force' to fax one anyway."
                        .format(prependText, monstername, monstercode))
            if not self._noMoreFaxesToday:
                self.whisper(self.faxbot_uid, monstercode)
                self._lastRequest = monstercode
                self._lastRequestTime = utcTime()
                return ("{}Requested {}, waiting for reply..."
                        .format(prependText, monstername))
            return ("You can manually request a {} with /w FaxBot {}"
                    .format(monstername, monstercode))

    
    def faxFromList(self, args, isPM):
        '''Look up the monster code in the list using fuzzy matching, 
        then fax it. (Or, if in quiet mode, display its code)
        '''
        splitArgs = args.split()
        if any(s for s in splitArgs if s.strip().lower() == "force"):
            return self.fax(splitArgs[0], splitArgs[0], "(forcing) ", 
                            isPM, force=True)
        
        # first, check for exact code/name/alias matches
        matches = [entry.code for entry in self._faxList.values() 
                   if entry.contains(args)]
        if len(matches) == 1:
            return self.fax(matches[0], self._faxList[matches[0]].name, "", 
                            isPM)
        
        # next, check for "close" matches
        simplify = (lambda x: x.replace("'", "")
                              .replace("_", " ")
                              .replace("-", " ").lower())
        sArgs = simplify(args)
        scoreDiff = 15
        scores = defaultdict(list)
        
        # make list of all possible names/codes/aliases
        allNames = [name for entry in self._faxList.values() 
                    for name in entry.nameList] 
        for s in allNames:
            score1 = fuzz.partial_token_set_ratio(simplify(s), sArgs)
            scores[score1].append(s)
        allScores = scores.keys()
        maxScore = max(allScores)
        for score in allScores:
            if score < maxScore - scoreDiff:
                del scores[score]
        matches = []
        for match in scores.values():
            matches.extend(match)
        fuzzyMatchKeys = set(entry.code for entry in self._faxList.values() 
                             for match in matches if entry.contains(match))
        

        # also check for args as a subset of string or code
        detokenize = lambda x: ''.join(re.split(r"'|_|-| ", x)).lower()
        dArgs = detokenize(args)
        matches = [name for name in allNames if dArgs in detokenize(name)]
        subsetMatchKeys = set(entry.code for entry in self._faxList.values() 
                              for match in matches if entry.contains(match))
        
        ls = len(subsetMatchKeys)
        lf = len(fuzzyMatchKeys)
        matchKeys = subsetMatchKeys | fuzzyMatchKeys
        lm = len(matchKeys)
        
        if ls == 0 and lf == 1:
            m = matchKeys.pop()
            return self.fax(m, self._faxList[m].name, "(fuzzy match) ", isPM)
        elif lm == 1:
            m = matchKeys.pop()
            return self.fax(m, self._faxList[m].name, "(subset match) ", isPM)
        elif lm > 1 and lm < 6:
            possibleMatchStr = ", ".join(
                    ("{} ({})".format(self._faxList[k].name,k))
                     for k in matchKeys)
            return "Did you mean one of: {}?".format(possibleMatchStr)
                    
        elif lm > 1:
            return ("Matched {} monster names/codes; please be more specific."
                    .format(ls + lf))

        return ("No known monster with name/code matching '{0}'. "
                "Use '!fax {0} force' to force, or check the monster list "
                "at {1} .".format(args, self.fax_list_url))
        
        
    def updateLastFax(self):
        """ Update what's in the Fax machine """
        with self.__lock:
            
            # suppress annoying output from pyKol
            kol.util.Report.removeOutputSection("*")
            try:
                r = ClanLogRequest(self.session)
                log = self.tryRequest(r, numTries=5, initialDelay=0.25, 
                                      scaleFactor=1.5)
            finally:
                kol.util.Report.addOutputSection("*")
            faxEvents = [event for event in log['entries'] 
                         if event['type'] == CLAN_LOG_FAX]
            lastEvent = None if len(faxEvents) == 0 else faxEvents[0]
            if lastEvent is None:
                self._lastFax = None
                self._lastFaxTime = None
                self._lastFaxUname = None
            else:
                self._lastFax = lastEvent['monster']
                lastFaxTimeAz = tz.localize(lastEvent['date'])
                lastFaxTimeUtc = lastFaxTimeAz.astimezone(utc)
                self._lastFaxTime = calendar.timegm(lastFaxTimeUtc.timetuple())
                self._lastFaxUname = lastEvent['userName']
            return lastEvent 
                
    
    def processFaxbotMessage(self, txt):
        """ Process a PM from FaxBot """
        with self.__lock:
            if "I do not understand your request" in txt:
                replyTxt = ("FaxBot does not have the requested monster '{}'. "
                            "(Check the list at {} )"
                            .format(self._lastRequest, self.fax_list_url)) 
                self._lastRequest = None
                self._lastRequestTime = None
                return replyTxt
            if "just delivered a fax" in txt:
                self._lastRequest = None
                self._lastRequestTime = None
                return ("FaxBot received the request too early. "
                        "Please try again.")
            if "try again tomorrow" in txt:
                self._noMoreFaxesToday = True
                txt = ("I'm not allowed to request any more faxes today. "
                       "Request manually with /w FaxBot {}"
                       .format(self._lastRequest))
                self._lastRequest = None
                self._lastRequestTime = utcTime()
                return txt
            m = re.search(r'has copied', txt)
            if m is not None:
                self._lastRequest = None
                self._lastRequestTime = None
                self._lastFaxBotTime = utcTime()
                # suppress output from checkForNewFax since we are returning
                # the text, to be output later
                return self.checkForNewFax(False)
            self._lastRequest = None
            self._lastRequestTime = None
            return "Received message from FaxBot: {}".format(txt)

        
    def printLastFax(self):
        """ Get the chat text to represent what's in the Fax machine. """
        if self._lite:
            if utcTime() - self._lastFaxCheck >= self._checkFrequency:
                self.checkForNewFax(False)
        if self._lastFax is None:
            return "I can't tell what's in the fax machine."
        elapsed = utcTime() - self._lastFaxTime
        timeStr = "{} minutes".format(int((elapsed+59) // 60))
        return ("The fax has held a(n) {} for the last {}. "
                "(List of monsters {} )"
                .format(self._lastFax, timeStr, self.fax_list_url))
        
        
    def _processCommand(self, message, cmd, args):
        if cmd == "fax":
            if args != "":
                isPM = (message['type'] == "private")
                return self.faxMonster(args, isPM)
            else:
                return self.printLastFax()
        elif message.get('userId', 0) == self.faxbot_uid:
            self.log("Received FaxBot PM: {}".format(message['text']))
            msg = self.processFaxbotMessage(message['text'])
            if msg is not None:
                self.chat(msg)
            return None
        

    def _heartbeat(self):
        if self._initialized and not self._downloadedFaxList:
            with self.__lock:
                self.initializeFaxList()
                self._downloadedFaxList = True
        if utcTime() - self._lastFaxCheck >= self._checkFrequency:
            if self._announce:
                self.checkForNewFax(True)
        

    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            if eData.to is None:
                self._eventReply({
                        'warning': '(omitted for general state inquiry)'})
            else:
                self._eventReply(self.state)
        elif s == "startup" and eData.fromIdentity == "__system__":
            self._initialized = True
            
    
    def _availableCommands(self):
        if self._allowRequests:
            return {'fax': "!fax: check the contents of the fax machine. "
                           "'!fax MONSTERNAME' requests a fax from FaxBot."}
        else:
            return {'fax': "!fax: check the contents of the fax machine. "
                           "'!fax MONSTERNAME' shows the code to request "
                           "MONSTERNAME from FaxBot."}
