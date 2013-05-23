import time
import re
import logging
import random
import threading
from collections import defaultdict
from cwbot.common.objectContainer import ManagerEntry
from cwbot.util.importClass import easyImportClass
from cwbot.common.InitData import InitData
from cwbot.sys.eventSubsystem import EventSubsystem
from cwbot.sys.heartbeatSubsystem import HeartbeatSubsystem
from cwbot.sys.mailHandler import MailHandler
from cwbot.common.kmailContainer import Kmail
from cwbot.util.tryRequest import tryRequest
from cwbot.kolextra.request.GetEventMessageRequest \
                     import GetEventMessageRequest
from kol.request.ClanWhitelistRequest import ClanWhitelistRequest
from cwbot.kolextra.request.ClanDetailedMemberRequest \
                     import ClanDetailedMemberRequest


class CommunicationDirector(EventSubsystem.EventCapable,
                            HeartbeatSubsystem.HeartbeatCapable):
    """ The CommunicationDirector is the top tier of the three-tiered
    communication system. The Director is in charge of sending and receiving
    chats and kmails. There is only one Director, but the Director may have
    many managers that belong to it.
    
    The Director reads chats and kmails and then passes them to each of its
    managers. It then collects the replies from each manager and transmits
    them either by chat or kmail. It is NOT the job of the Director to filter
    chats/kmails; every chat or kmail is passed to each manager, with the
    notable exception of chat-based system messages and unknown messages, 
    which are ignored.
    
    The Director also handles a few auxilliary tasks: It transmits a periodic
    /who chat to keep chat from going into "away mode", and it raises an
    event when a system message about rollover is detected.
    """
    logChannel = 'main'
    debugLogChannel = 'main'
    def __init__(self, parent, iData, config):
        self._log = logging.getLogger()
        self._initialized = False
        self._mailHandler = None
        self._running = True
        self._chatIteration = 0
        super(CommunicationDirector, self).__init__(
                                            name="sys.comms", 
                                            identity="comms", 
                                            evSys=parent.eventSubsystem,
                                            hbSys=parent.heartbeatSubsystem)
        self._parent = parent
        self._s = iData.session
        self._c = iData.chatManager
        self._inv = iData.inventoryManager
        self._props = iData.properties
        self._db = iData.database
        self._mailHandler = MailHandler(self._s, self._props, self._inv, 
                                        self._db)
        self._mailHandler.start()
        self._managers = []
        self._log.info("******** Initializing Communications ********")
        try:
            self._loadManagers(config)
        except:
            self._mailHandler.stop()
            raise
        self._mailDelay = config['mail_check_interval']
        self._clanMembers = defaultdict(dict)

        # add random times to refreshes to prevent server hammering
        self._lastChatRefresh = time.time() + random.randint(0, 300)
        self._lastKmailRefresh = time.time() + random.randint(0, 
                                                              self._mailDelay)
        self._lastEventRefresh = time.time() + random.randint(0, 15)
        self._lastGreenEventAzTime = None

        self._clanMemberCheckInterval = 3600
        self._clanMemberLock = threading.Lock()
        self._refreshClanMembers()
        self._lastClanMemberRefresh = (
            time.time() + random.randint(-self._clanMemberCheckInterval/2, 
                                          self._clanMemberCheckInterval/4))

        self._log.info("******** Communications Online ********")
        self._initialized = True
        
        
    def _loadManagers(self, config):
        """ Import managers, as specified in config file """
        base = config['base']
        # loop through managers
        iData = InitData(self._s, self._c, self._props, self._inv, self._db)
        for k,v in config.items():
            if isinstance(v, dict):
                cfg = v
                
                # import class
                ManagerClass = easyImportClass(base, v['type'])                
                self._managers.append(ManagerEntry(
                        ManagerClass, v['priority'], self, k, 
                        iData, cfg))
        self._managers.sort(key=lambda x: -x.priority)
        for m in self._managers:
            self._log.debug("== Initializing {0.className} with priority "
                            "{0.priority} ==".format(m))
            m.createInstance()
            self._log.debug("== Finished initializing {} =="
                            .format(m.className)) 


    def cleanup(self):
        """ Unregister components in preparation for shutdown """
        for m in reversed(self._managers):
            man = m.manager
            self._log.debug("Cleaning up manager: {}".format(m.className))
            man.cleanup()
        self.heartbeatUnregister()
        self.eventUnregister()
        self._log.info("Closing mail handler...")
        self._mailHandler.stop()
        self._mailHandler.join()
        self._log.info("Mail handler closed.")
        self._mailHandler = None
        self._managers = None

    
    def processNewCommunications(self):
        """ This function is called every second or two (as specified in
        modules.ini) and downloads and processes new chats/kmails. """
        msgs = self._c.getNewChatMessages()
        self._processChat(msgs)

        # check for mail handler issues
        if self._mailHandler.exception.is_set():
            self._mailHandler.join()
        # get new mail
        newKmail = Kmail.fromPyKol(self._mailHandler.getNextKmail())
        while newKmail is not None:
            responses = self._processKmail(newKmail)
            try:
                # send responses to MailHandler
                kmails = [r.kmail for r in responses]
                self._mailHandler.respondToKmail(newKmail.info['id'],  
                                                 map(Kmail.toPyKol, kmails))
            except Exception as e:
                for r in responses:
                    r.manager.kmailFailed(r.module, r.kmail, e)
                raise
            newKmail = Kmail.fromPyKol(self._mailHandler.getNextKmail())


    def _processChat(self, msgs):
        """ Process a list of chat messages, in pyKol format. Unlike the
        "dual" function processKmail, this function handles transmission as
        well as processing. """
        self._chatIteration += 1
        newKmail = False
        for x in msgs:
            if x.get('type', "").lower() == "unknown":
                self._raiseEvent("unknown_chat")
                
            ignoreMessage = False
            whisper = False
            
            # check if it's a rollover alert
            m = re.search(r'nightly maintenance in (\d+) minutes?',
                          x.get('text', ""))
            if (m is not None and (x['type'].lower() == "system message" or
                                   x['userName'].lower() == "dungeon")):
                    self._log.debug("Rollover in {} minutes."
                                    .format(m.group(1)))
                    timeLeft = int(m.group(1))
                    if timeLeft >= 5:
                        newKmail = True
                    self._raiseEvent("rollover", None, 
                                     {'time': timeLeft})
                    ignoreMessage = True
            # reject if no message type
            elif 'type' not in x:
                self._log.debug("rejected: no type: {}".format(x))
                ignoreMessage = True
            # handle kmail notification
            elif x['type'].lower() == "notification:kmail":
                self._log.debug("New kmail notification.")
                newKmail = True
                ignoreMessage = True
            # reject message from self
            elif x.get('userId', -1) == self._s.userId:
                self._log.debug("rejected: message from myself: {}".format(x))
                ignoreMessage = True
            # reject message with no text
            elif 'text' not in x:
                self._log.debug("rejected: no text: {}".format(x))
                ignoreMessage = True
            # detect private messages
            elif 'channel' not in x or x.get('type', "") == "private":
                x['channel'] = x['type']
                whisper = True
            
            # check if this is a clan message from a new member
            if x['channel'] == "clan":
                if x['userId'] not in self._clanMembers:
                    self._log.debug("New clan member detected: {}"
                                    .format(x['userId']))
                    self._refreshClanMembers()
            
            # actually handle message
            if not ignoreMessage:
                self._log.debug("<< {}"
                                .format(' '.join("<{}> {}"
                                                 .format(k,v) 
                                                 for k,v in x.items())))
                # get replies from each manager
                chats = []
                for m in self._managers:
                    man = m.manager
                    chats.extend(man.parseChat(x, self._chatIteration))
                # transmit responses
                for txtLine in chats:
                    if whisper:
                        self.whisper(x['userId'], txtLine)
                    else:
                        self.sendChat(x['channel'], txtLine)

        # send /who message to keep us out of away mode
        if time.time() - self._lastChatRefresh > 300:
            self._c.sendChatMessage("/who")
            self._lastChatRefresh = time.time()
        
        # force full refresh of new mail if we haven't checked recently
        if time.time() - self._lastKmailRefresh > self._mailDelay:
            newKmail = True
        
        # check for new kmails
        if newKmail or time.time() - self._lastEventRefresh > 15:
            self._checkForNewKmails(force=newKmail)
            self._lastEventRefresh = time.time()
    
    
    def sendChat(self, channel, text, waitForReply=False, useEmote=True):
        """ Send a chat message. Messages with useEmote == True are sanitized
        to prevent chat command injection. If waitForReply is False, this
        should always immediately return an empty object (None or [] or {}), 
        and the chat is sent asynchronously. If waitForReply is True, 
        execution will block until a response is available. """
        # sanitize text if not using raw mode
        if useEmote and len(text) > 0 and text[0] == "/":
            tList = list(text)
            tList[0] = "\\"
            text = "".join(tList)
        
        self._raiseEvent("chat", None, {'channel': channel, 'text': text})
        # add channel to chat if necessary
        if (channel.lower().strip() != self._c.currentChannel.lower().strip()):
            text = "/{} {}".format(channel, text)
        return self._c.sendChatMessage(text, waitForReply, useEmote)
        
    
    def whisper(self, uid, text, waitForReply=False):
        """ Send a private message. """
        txt = "/w " + str(uid) + " " + text;
        return self._c.sendChatMessage(txt, waitForReply, False)
    
    
    def _processKmail(self, message):
        """ Process a single Kmail message. Unlike _processChat, this method
        only returns a list of replies; it doesn't actually transmit them. """
        self._log.debug("Processing kmail with items: {}"
                        .format(', '.join("{} x{}"
                                         .format(k,v) 
                                         for k,v in message.items.items())))
        responses = []
        if message.uid > 0:
            for m in self._managers:
                self._inv.refreshInventory()
                man = m.manager
                responses.extend(man.parseKmail(message))
        self._inv.refreshInventory()
        return responses
        

    def sendKmail(self, kmail):
        """ Send a Kmail that is not a response. Do not use this function to
        reply to another Kmail; use a response inside _processKmail instad. """
        self._mailHandler.sendNonresponseKmail(kmail.toPyKol())


    def cashout(self, uid):
        """ Send withheld items to a user. Items are automatically withheld
        by the MailHandler if a user is in HC/Ronin and must be manually
        released. """
        self._mailHandler.sendDeferredItems(uid)
        
    
    def balance(self, uid):
        """ Send a balance of withheld items to a user. Items are 
        automatically withheld by the MailHandler if a user is in HC/Ronin
        and must be manually released. """ 
        return self._mailHandler.getDeferredItems(uid)


    def __del__(self):
        if self._mailHandler is not None:
            self._mailHandler.stop()
            self._mailHandler.join()
            
    
    def _checkForNewKmails(self, force=False):
        """ Check if any new kmails have arrived, and notify the MailHandler
        if so. This check is done using the KoL API to check for new
        "green message" events. If force is true, the MailHandler is notified
        of new mail even if no mail is present. This doesn't do any harm,
        the handler will just find an empty inbox if nothing's there. """
        azTime = None if force else self._lastGreenEventAzTime
        r = GetEventMessageRequest(self._s, azTime)
        events = tryRequest(r)['events']
        if events:
            self._lastGreenEventAzTime = max(e.get('azunixtime', 0)
                                             for e in events)
        if force or any(True for e in events
                        if "New message received" in e.get('message', "")):
            self._log.debug("Checking kmail...")
            self._lastKmailRefresh = time.time()
            self._mailHandler.notify()
            
            
    def _refreshClanMembers(self):
        n = len(self._clanMembers)
        self._log.debug("Updating clan member list...")
        
        r1 = ClanWhitelistRequest(self._s)
        d1 = tryRequest(r1)
        r2 = ClanDetailedMemberRequest(self._s)
        d2 = tryRequest(r2)
        self._log.debug("{} members on whitelist".format(len(d1['members'])))
        self._log.debug("{} members in clan".format(len(d2['members'])))
        with self._clanMemberLock:
            self._clanMembers = defaultdict(dict)
            for record in d1['members']:
                uid = int(record['userId'])
                entry = {'userId': uid,
                         'userName': record['userName'],
                         'rankName': record['rankName'],
                         'whitelist': True}
                self._clanMembers[uid] = entry
            for record in d2['members']:
                uid = int(record['userId'])
                entry = {'userId': uid,
                         'userName': record['userName'],
                         'rankName': record['rankName'],
                         'inClan': True,
                         'karma': record['karma']}
                self._clanMembers[uid].update(entry)
            for uid, record in self._clanMembers.items():
                if 'karma' not in record:
                    record['karma'] = 0
                    record['inClan'] = False
                if 'whitelist' not in record:
                    record['whitelist'] = False
            self._lastClanMemberRefresh = time.time()
            n2 = len(self._clanMembers)
            self._log.debug("There are {} clan members (previous count: {})"
                            .format(n2, n))
            self._raiseEvent("new_member_list", None)
        
        
    def clanMemberInfo(self, uid):
        with self._clanMemberLock:
            if uid not in self._clanMembers:
                return {}
            return self._clanMembers[uid]
            
        
    def _eventCallback(self, eData):
        if (eData.subject in ["crash", "manual_stop", "manual_restart"] and
            eData.fromIdentity == "__system__"):
            if self._mailHandler is not None:
                # stop the mail handler early, for quicker shutdown
                self._mailHandler.stop()
            
            
    def _heartbeat(self):
        if not self._initialized:
            return
        if (time.time() - self._lastClanMemberRefresh 
                >= self._clanMemberCheckInterval):
            self._refreshClanMembers()
            