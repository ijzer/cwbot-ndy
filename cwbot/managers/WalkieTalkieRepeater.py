import re
import time
import random
import hashlib
from math import floor
from collections import defaultdict
from cwbot.managers.BaseChatManager import BaseChatManager
from cwbot.util.textProcessing import stringToList
from cwbot.common.exceptions import FatalError
from kol.request.UseItemRequest import UseItemRequest 
from cwbot.util.tryRequest import tryRequest
from kol.Error import Error
 
    
class WalkieTalkieRepeater(BaseChatManager):
    """ A manager that relays between /clan and /talkie on a randomly-
        selected frequency. """
    capabilities = ['inventory']
    
    def _chatApplies(self, x, _checkNum):
        """ Override of _chatApplies. Here, only chats from a single channel
        (or optionally, a PM) are accepted. """
        return ((x['type'] in ['normal', 'listen', 'emote'] and 
                 x['channel'].lower() in ['clan', 'talkie'])
                or x['type'] == 'private')
        
        
    def __init__(self, parent, name, iData, config):
        """ Initialize the manager """
        self._playerDb = None
        self._numChanges = 0
        self._ready = False
        self._otherBots = None
        self._myFreq = None
        self._numPlayersForFreqChange = None
        self._freqChangeTimeout = None
        self._format, self._emoteFormat = None, None
        super(WalkieTalkieRepeater, self).__init__(parent, name, iData, config)
        self._invMan.refreshInventory()
        self._lastOutsiderCheck = 0
        self._changeFreqRequests = {}
        inventory = self._invMan.inventory()
        numTalkies = inventory.get(6846, 0)
        if numTalkies == 0:
            numUnusedTalkies = inventory.get(6845, 0)
            if numUnusedTalkies > 0:
                try:
                    r = UseItemRequest(self._s, 6845)
                    d = tryRequest(r)
                    numTalkies = 1
                except Error:
                    raise FatalError("Could not use unused walkie talkie.")
            else:
                raise FatalError("Cannot use WalkieTalkieRepeater with "
                                 "no walkie talkie!")
        replies = self.sendChatMessage("/kenneth", None, 
                                   waitForReply=True, raw=True)
        for reply in replies:
            txt = reply['text']
            freq = re.search(r"The frequency is (\d+.\d), Mr. Rather", txt)
            if freq:
                self._myFreq = freq.group(1)
                self._log.info("My walkie talkie frequency is {}"
                                .format(freq.group(1)))
        if self._myFreq is None:
            raise RuntimeError("Could not determine walkie talkie frequency.")
        self._ready = True
        
        
    def _initialize(self):
        if self._modules:
            raise FatalError("WalkieTalkieRepeater cannot use modules.")
        if "__numchanges__" in self._persist:
            self._numChanges = self._persist["__numchanges__"]
        lastKey = self._persist.get('__lastKey__', None)
        if lastKey != self._key:
            self._changeFrequencies(self._numChanges)
        self._playerDb = defaultdict(lambda: [None] * len(self._otherBots))
            
        
    def _configure(self, config):
        BaseChatManager._configure(self, config)
        try:
            otherBots = stringToList(config.setdefault('other_bots', "none"))
            self._otherBots = map(int, otherBots)
        except ValueError:
            raise FatalError("Error configuring WalkieTalkieRepeater: "
                             "other_bots must be list of integers (userIds)")
        try:
            self._numPlayersForFreqChange = int(config.setdefault(
                                                 'num_players_to_change', 3))
            self._freqChangeTimeout = int(config.setdefault('change_timeout',
                                                            10))
        except ValueError:
            raise FatalError("Error configuring WalkieTalkieRepeater: "
                             "num_players_to_change and change_timeout must "
                             "be integral")
        self._format = config.setdefault('format', 
                                         "[[%username%]] %text%")
        self._emoteFormat = config.setdefault('emote_format',
                                        "[[%username% %text%]]")
        self._key = str(config.setdefault('key', random.randint(0,999999)))
        if self._key.strip() == "":
            config['key'] = random.randint(0,999999)
            self._key = str(config['key'])


    def defaultChannel(self):
        return "clan"

    
    def _showCommandSummary(self, msg, availableCommands, availableAdmin):
        """ Override of _showCommandSummary """
        if self.director.clanMemberInfo(msg['userId']):
            return ["!newfrequency to request walkie-talkie change; "
                    "!frequency to get the current walkie-talkie channel."]
        else:
            return []

        
    def parseChat(self, msg, checkNum):
        """ Say text in opposite channel """
        if not self._chatApplies(msg, checkNum):
            return []
        
        clanMember = self.director.clanMemberInfo(msg['userId'])
        text = msg['text']
        userId = msg['userId']
        if msg['type'] != 'private':
            inChannel = msg.get('channel', self.defaultChannel).lower()
            outChannel = {'clan': "talkie", 'talkie': "clan"}[inChannel]
            userName = msg.get('userName', "???")
            if userId not in self._otherBots:
                newText = (self._format if msg['type'] != "emote" 
                           else self._emoteFormat)
                newText = (newText.replace("%username%", userName)
                                  .replace("%userid%", str(userId))
                                  .replace("%text%", text)
                                  .replace("%hash%", "#"))
            else:
                newText = text if msg['type'] != "emote" else None
            if newText is not None:
                self.sendChatMessage(newText, outChannel, False, True)
            if inChannel == "talkie" and not clanMember:
                if not any(self._playerDb[userId]):
                    self._lastOutsiderCheck = 0
        
        if clanMember:
            if re.search(r"^!(frequency|kenneth)($|\s)", text):
                return [self._handleFrequencyRequest(msg)]
            elif re.search(r"^!newfrequency($|\s)", text):
                self._handleNewFrequencyRequest(msg)
            elif re.search(r"^!help\s*$", text):
                return self._showCommandSummary(msg, None, None)
        
        if msg['userId'] in self._otherBots:
            m = re.search(r'''TALKIE \[([0-9 ])\]''', text)
            if m is not None:
                otherNumChanges = int("".join(m.group(1).split()))
                if otherNumChanges > self._numChanges:
                    self._changeFrequencies(otherNumChanges)
            
            # search for message validating in-clan status of player
            # from another bot
            m2 = re.search(r'''(IN|OUT|IS)CLAN \[(\d+)\]''', text)
            if m2 is not None:
                uid = int(m2.group(2))
                inMyClan = bool(self.director.clanMemberInfo(uid))
                if m2.group(1) == "IS":
                    self._sendPlayerInfo(uid, userId)
                    return []
                inTheirClan = (m2.group(1) == "IN")
                idx = self._otherBots.index(userId)
                self._playerDb[uid][idx] = inTheirClan
                self._log.debug("Bot {} reported clan status of {} as {}"
                                .format(userId, uid, inTheirClan))
                
                # if all other bots say this user is not in the clan, 
                # and this bot says the user is not in the clan,
                # then immediately perform another outsider check
                self._log.debug("Status for {}: my clan={}, other clans={}"
                                .format(uid, inMyClan, self._playerDb[uid]))
                if all(inclan == False for inclan in self._playerDb[uid]):
                    if not self.director.clanMemberInfo(uid):
                        self._lastOutsiderCheck = 0
        return []
    
    
    def _sendPlayerInfo(self, playerId, botId):
        inClan = bool(self.director.clanMemberInfo(playerId))
        self._log.debug("Bot {} requested clan status ({}) for {}"
                        .format(botId, inClan, playerId))
        self.whisper(botId, "{}CLAN [{}]".format("IN" if inClan else "OUT",
                                                 playerId))


    def _requestPlayerInfo(self, playerId, botId):
        self._log.debug("Requesting inclan status for {} from bot {}"
                        .format(playerId, botId))
        self.whisper(botId, "ISCLAN [{}]".format(playerId))
        
        
    def _sendChannelInfo(self, botId):
        self.whisper(botId, "TALKIE [{}]".format(self._numChanges))


    def _handleFrequencyRequest(self, msg):
        if msg.get('channel', "").lower() == "talkie":
            return "You're already here, Kenneth."
        return ("Use /kenneth {} to listen to the clan chat relay."
                .format(self._myFreq))
            
    
    def _handleNewFrequencyRequest(self, msg):
        uid = msg['userId']
        admin = self.properties.getAdmins('admin_command')
        self._changeFreqRequests[uid] = time.time()
        numRequests = len([v for v in self._changeFreqRequests.values()
                          if v >= time.time() - self._freqChangeTimeout * 60])
        
        if numRequests >= self._numPlayersForFreqChange or uid in admin:
            self._changeFreqRequests = {}
            self._changeFrequencies()
        else:
            self._dualChat("{}/{} clan members have requested a frequency "
                           "change."
                           .format(numRequests, self._numPlayersForFreqChange))


    def _changeFrequencies(self, changeNum=None):
        if changeNum is None:
            self._numChanges += 1
        else:
            self._numChanges = changeNum
        m = hashlib.sha256("{}{}".format(self._key, self._numChanges))
        newFreq = int(m.hexdigest(), 16)
        newFreq = 1 + newFreq % 99999
        self._myFreq = "{}.{}".format(int(floor(newFreq / 10)), newFreq % 10)
        self._dualChat("Changing walkie-talkie frequency to {}."
                       .format(self._myFreq),
                       "Changing walkie-talkie frequency; send '!frequency' "
                       "in a PM to get the new frequency.", waitForReply=True)
        self._log.info("Changing frequencies to {}.".format(self._myFreq))
        self.sendChatMessage("/kenneth {}".format(self._myFreq), 
                             waitForReply=True, raw=True)
        self._lastOutsiderCheck = 0
        
        
    def _handleOutsider(self, uid, userName):
        self._dualChat("Non-clan member {} (#{}) detected in /talkie."
                       .format(userName, uid))
        self._changeFrequencies()
        
        
    def _dualChat(self, txtClan, txtTalkie=None, **kwargs):
        if txtTalkie is None:
            txtTalkie = txtClan
        self.sendChatMessage(txtClan, channel="clan", **kwargs)
        self.sendChatMessage(txtTalkie, channel="talkie", **kwargs)
        
        
    def _syncState(self, force=False):
        '''Store persistent data for Hobo Modules. Here there is the 
        extra step of storing the old log and hoid. '''
        with self._syncLock:
            if self._persist is not None:
                self._persist['__numchanges__'] = self._numChanges
                self._persist['__lastKey__'] = self._key
            super(WalkieTalkieRepeater, self)._syncState(force)
    
    
    def _heartbeat(self):
        if not self._ready:
            return
        timeSinceLastOutsiderCheck = time.time() - self._lastOutsiderCheck
        if timeSinceLastOutsiderCheck >= 2 * 60:
            self._lastOutsiderCheck = time.time()
            whoVals = self.sendChatMessage("/who talkie", "DEFAULT", 
                                           waitForReply=True, raw=True)
            allUsers = whoVals[0]['users']
            self._log.debug("Users in /talkie: {}"
                            .format(', '.join(user['userName'] 
                                            for user in allUsers)))
            for user in allUsers:
                uid = int(user['userId'])
                inClan = bool(self.director.clanMemberInfo(uid))
                if not inClan:
                    if all(inclan == False for inclan in self._playerDb[uid]):
                        self._log.debug("player {}, db {}"
                                        .format(uid, 
                                                self._playerDb[uid]))
                        self._handleOutsider(uid, user['userName'])
                        break
                    for idx, botid in enumerate(self._otherBots):
                        if self._playerDb[uid][idx] is None:
                            self._requestPlayerInfo(uid, botid)
            for botId in self._otherBots:
                if not any(True for user in allUsers 
                           if int(user['userId']) == botId): 
                    self._sendChannelInfo(botId)
