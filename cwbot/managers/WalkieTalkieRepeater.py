import re
import time
import random
from math import floor
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
                self._log.debug("My walkie talkie frequency is {}"
                                .format(freq.group(1)))
        if self._myFreq is None:
            raise RuntimeError("Could not determine walkie talkie frequency.")
        self._ready = True
        
        
    def _configure(self, config):
        BaseChatManager._configure(self, config)
        try:
            otherBots = stringToList(config.setdefault('other_bots', ""))
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
                                         "%username% (%hash%%userid%): %text%")
        self._emoteFormat = config.setdefault('emote_format',
                                        "%username% (%hash%%userid%) %text%")


    def defaultChannel(self):
        return "clan"

    
    def _showCommandSummary(self, msg, availableCommands, availableAdmin):
        """ Override of _showCommandSummary """
        if self.director.clanMemberInfo(msg['userId']):
            return ["!newfrequency to request walkie-talkie change; "
                    "!frequency to get the current walkie-talkie channel"]
        else:
            return []

        
    def parseChat(self, msg, checkNum):
        """ Say text in opposite channel """
        if not self._chatApplies(msg, checkNum):
            return []
        
        clanMember = self.director.clanMemberInfo(msg['userId'])
        text = msg['text']
        if msg['type'] != 'private':
            inChannel = msg.get('channel', self.defaultChannel).lower()
            outChannel = {'clan': "talkie", 'talkie': "clan"}[inChannel]
            userName = msg.get('userName', "???")
            userId = msg['userId']
            if userId not in self._otherBots:
                newText = (self._format if msg['type'] != "emote" 
                           else self._emoteFormat)
                newText = (newText.replace("%username%", userName)
                                  .replace("%userid%", str(userId))
                                  .replace("%text%", text)
                                  .replace("%hash%", "#"))
            else:
                newText = text
            self.sendChatMessage(newText, outChannel, False, True)
            if inChannel == "talkie" and not clanMember:
                self._handleOutsider(msg['userId'], msg['userName'])
        
        if clanMember:
            if re.search(r"^!(frequency|kenneth)($|\s)", text):
                return [self._handleFrequencyRequest(msg)]
            elif re.search(r"^!newfrequency($|\s)", text):
                self._handleNewFrequencyRequest(msg)
            elif re.search(r"^!help\s*$", text):
                return self._showCommandSummary(msg, None, None)
        return []


    def _handleFrequencyRequest(self, msg):
        if msg.get('channel', "").lower() == "talkie":
            return "You're already here, Kenneth."
        return ("Use /kenneth {} to listen to the clan chat relay."
                .format(self._myFreq))
            
    
    def _handleNewFrequencyRequest(self, msg):
        uid = msg['userId']
        self._changeFreqRequests[uid] = time.time()
        numRequests = len([v for v in self._changeFreqRequests.values()
                          if v >= time.time() - self._freqChangeTimeout * 60])
        
        if numRequests >= self._numPlayersForFreqChange:
            self._changeFreqRequests = {}
            self._changeFrequencies()
        else:
            self._dualChat("{}/{} clan members have requested a frequency "
                           "change."
                           .format(numRequests, self._numPlayersForFreqChange))


    def _changeFrequencies(self):
        newFreq = random.randint(1, 99999)
        self._myFreq = "{}.{}".format(int(floor(newFreq / 10)), newFreq % 10)
        self._dualChat("Changing walkie-talkie frequency to {}."
                       .format(self._myFreq),
                       "Changing walkie-talkie frequency; send '!frequency' "
                       "in a PM to get the new frequency.", waitForReply=True)
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
        
        
    def _heartbeat(self):
        if not self._ready:
            return
        timeSinceLastOutsiderCheck = time.time() - self._lastOutsiderCheck
        if timeSinceLastOutsiderCheck >= 5 * 60:
            self._lastOutsiderCheck = time.time()
            whoVals = self.sendChatMessage("/who talkie", "DEFAULT", 
                                           waitForReply=True, raw=True)
            allUsers = whoVals[0]['users']
            self._log.debug("Users in /talkie: {}"
                            .format(', '.join(user['userName'] 
                                            for user in allUsers)))
            for user in allUsers:
                if not self.director.clanMemberInfo(user['userId']):
                    self._handleOutsider(user['userId'], user['userName'])
                    break
