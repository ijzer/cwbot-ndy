from cwbot.modules.BaseKmailModule import BaseKmailModule 
from cwbot.common.exceptions import FatalError 
from cwbot.util.textProcessing import stringToList 
from kol.request.StatusRequest import StatusRequest 
import random 
import threading
import time
import calendar 
import math
import re

def _epochTime():
    return calendar.timegm(time.gmtime())


class PeriodicAnnouncementModule(BaseKmailModule): 
    """ 
    A simple module that broadcasts a chat message at regular intervals. 
        The chat can be chosen from a group of messages, either randomly or 
        cycled. 
        
        Additionally, an administrator can set up recurring messages through 
        kmail. 
    
    Configuration format: 
        [[[[unique_group_name]]]] 
                        period = 240 # minutes 
                        offset = 0 # how soon after rollover is the 1st message sent 
                                                # can also be "random" (no quotes) 
                        channel = clan, hobopolis 
            mode = cycle # can be: cycle, shuffle, random 
                        message1 = Hello clan members! I am annoying you! 
                        message2 = I am still annoying you!!! 

    Configuration example: 
    [[[PAM]]] 
        type = PeriodicAnnouncementModule 
        priority = 0 
        [[[[annoy_my_users]]]] 
                        period = 240 
                        offset = 120 
                        channel = clan, hobopolis 
                        mode = cycle 
                        message1 = Hello clan members! I am annoying you! 
                        message2 = I am still annoying you!!! 
        [[[[remind_about_stuff]]]] 
                        period = 1440 
                        offset = random 
                        channel = hobopolis 
                        mode = shuffle 
                        message1 = REMINDER: Clan rules prohibit killing more than one hobo boss. 
                        message2 = REMINDER: Make sure to ask in chat before killing a boss. 
                        message3 = REMINDER: All side areas must be cleared before fighting Hodgman. 
        """ 
    requiredCapabilities = ['chat'] 
    _name = "periodic_announce" 
    
    
    _addMessageTemplate = """announcements add Kmail template

HOW TO USE: Click "quoted" above, then fill out the [[]] markers. Then click send.
Do not add newlines.

Enter a unique description: [[DESCRIPTION GOES HERE]]
Broadcast one of the following messages (leave extra messages blank):
message: [[MESSAGE GOES HERE]]
message: [[]]
message: [[]]
message: [[]]
message: [[]]
message: [[]]
message: [[]]
message: [[]]

Send on the following channels: [[clan, hobopolis]]
Send a message every [[1440]] minutes
First transmission occurs [[30]] minutes after rollover
The message ordering mode is [[cycle]] (cycle, shuffle, or random)
Show the message for the next [[9999]] days (counting today)

"""

    _messageMatcher = re.compile(
        r"unique description: \[\[(?P<description>.+?)\]\].*?"
        r"(?P<messageSection>message:.*)"
        r"following channels: \[\[(?P<channels>.+?)\]\].*"
        r"every \[\[(?P<period>\d+)\]\] minutes.*"
        r"occurs \[\[(?P<offset>random|\d+)\]\] minutes.*"
        r"mode is \[\[(?P<mode>.+?)\]\].*"
        r"the next \[\[(?P<expires>\d+)\]\]",
        re.DOTALL | re.IGNORECASE)
    _messageExtractor = re.compile("message: \[\[(.+?)\]\]", re.IGNORECASE)
    _modes = {'cycle': 0, 'shuffle': 1, 'random': 2}

    def __init__(self, manager, identity, config): 
        self._messages = {} 
        self._firstTime = True
        self._rolloverTime = 0 
        self._doFinishInit = threading.Event() 
        self._run = threading.Event() 
        super(PeriodicAnnouncementModule, self).__init__(manager, 
                                                         identity, 
                                                         config) 
        
    
    def initialize(self, lastKnownState, initData): 
        super(PeriodicAnnouncementModule, self).initialize(lastKnownState, 
                                                           initData) 
        for k,v in lastKnownState['messages'].items(): 
            if v['order'] is None:
                v['order'] = []
            if k in self._messages and v['hard']: 
                print "self.messages={}".format(self._messages)
                print "v={}".format(v)
                messageEntry = self._messages[k]
                messageEntry['last'] = int(v['last'])
                if v['mode'] != messageEntry['mode']: 
                    messageEntry.update({'order': [], 'index': 0}) 
                else: 
                    order = v['order']
                    if order:
                        for k2 in messageEntry['messages'].keys(): 
                            if k2 not in order: 
                                order.append(k2) 
                    messageEntry.update(
                        {'order': order, 
                         'index': min(v['index'], len(order))}) 
            elif not v['hard']:
                self._messages[k] = v
            
        self._doFinishInit.set() 
        
        
    def _configure(self, config): 
        for k,v in config.items(): 
            if isinstance(v, dict): 
                modeStr = v.setdefault('mode', 'cycle').lower() 
                periodStr = v.setdefault('period', 1440) 
                                        
                try: 
                    period = int(periodStr) 
                except ValueError: 
                    raise FatalError("Invalid period specified: {}" 
                                     .format(periodStr)) 
                                                                          
                offsetStr = v.setdefault('offset', 'random') 
                try: 
                    offset = int(offsetStr) 
                except ValueError: 
                    if offsetStr.lower() != "random": 
                        raise FatalError(("Invalid offset: {}, must be " 
                                          "integer or 'random'") 
                                         .format(offsetStr)) 
                    else: 
                        offset = random.randint(0, period) 

                try: 
                    mode = self._modes[modeStr] 
                except IndexError: 
                    raise FatalError("Invalid mode specified: {}" 
                                     .format(modeStr)) 
                                                                          
                channels = stringToList(v.setdefault('channel', 'clan,')) 
                                
                messages = {} 
                for key_,val_ in v.items(): 
                    if key_.lower().startswith("message"): 
                        try: 
                            keyVal = "message{:06d}".format(int(key_[7:])) 
                        except ValueError: 
                            raise FatalError(("Invalid message name: {}; " 
                                              "messages must be message1, " 
                                              "message2, ...") 
                                             .format(key_)) 
                        messages[keyVal] = val_ 
                                
                self._messages[k] = {'mode': mode, 
                                     'period': period, 
                                     'channels': channels, 
                                     'messages': messages, 
                                     'offset': offset, 
                                     'order': [], 
                                     'index': 0, 
                                     'hard': True,
                                     'last': 0,
                                     'expires': 0,
                                     'description': ""} 
                                                                                    
                                                                                    
    def _finishInitialization(self): 
        r2 = StatusRequest(self.session) 
        d2 = self.tryRequest(r2) 
        self._rolloverTime = int(d2['rollover']) 
        
        
    def _processKmail(self, message):
        if message.items:
            return None
        if message.meat:
            return None
        uid = message.uid
        msgText = message.text.strip()
        if msgText.lower().startswith("announcements delete"):
            announcementName = msgText[20:].strip()
            try:
                self._deleteSoftMessage(announcementName)
                return self.newMessage(uid, ("Message {} deleted."
                                             .format(announcementName)))
            except KeyError:
                return self.newMessage(uid, ("No such message: {}."
                                             .format(announcementName)))
        elif msgText.lower().startswith("announcements add"):
            return self.newMessage(uid, self._addMessageTemplate)
        elif msgText.lower().startswith("> announcements add"):
            return self._processAddMessageTemplate(message)
        elif msgText.lower().startswith("announcement"):
            return self._getAnnouncementsKmail(uid)
        return None
    
    
    def _getAnnouncementsKmail(self, uid):
        messageStrs = []
        for k,v in self._messages.items():
            if v['hard']:
                continue
            messageStrs.append('Announcement {}: send "{}" on channels '
                               '{} every {} minutes, starting {} minutes '
                               'after rollover'
                               .format(k,
                                       v['description'],
                                       ', '.join(v['channels']),
                                       v['period'],
                                       v['offset']))
        s = ("Periodic announcements:\n\n{}\n\n----------------\n\n"
             "To add a message, send \"announcements add\" and follow the "
             "instructions.\nTo delete an announcement, send "
             "\"announcements delete NAME\"."
             .format("\n\n".join(messageStrs)))
        return self.newMessage(uid, s)
        
        
    def _doAnnouncements(self, firstTime):
        curTime = _epochTime()
        for k,v in self._messages.items():
            if not v['order']:
                continue
            period = max(v['period'] * 60, 1)
            offset = v['offset'] * 60
            prevRollover = self._rolloverTime - 60 * 60 * 24
            tPastRolloverLast = v['last'] - (prevRollover + offset)
            tPastRolloverCurrent = curTime - (prevRollover + offset)
            periodCount = lambda x: int(math.floor(x / period))
            periodsPastRolloverLast = periodCount(tPastRolloverLast)
            periodsPastRolloverCurrent = periodCount(tPastRolloverCurrent)
            if periodsPastRolloverLast != periodsPastRolloverCurrent:
                success = firstTime or self._makeAnnouncement(k, v)
                if success:
                    v['last'] = curTime
                
                
    def _makeAnnouncement(self, k, v):
        idx = v['index']
        messageName = v['order'][idx]
        self.log("Making announcement {}:{}".format(k, messageName))
        try:
            messageText = v['messages'][messageName]
        except IndexError:
            self.log("No such announcement.")
            v['index'] += 1
            return False

        for channel in v['channels']:
            self.chat(messageText, channel)
        v['index'] += 1
        return True
                
                
    def _checkOrdering(self):
        for k,v in self._messages.items():
            if v['index'] >= len(v['order']):
                v['index'] = 0
                
                mode = v['mode']
                if mode == 0:
                    v['order'] = sorted(v['messages'].keys())
                elif mode == 1:
                    newList = v['messages'].keys()
                    random.shuffle(newList)
                    v['order'] = newList
                else:
                    idx = random.randint(0, len(v['messages']))
                    v['order'] = [v['messages'].keys()[idx]]
                self.log("Order for {} is {}".format(k, v['order']))


    def _deleteSoftMessage(self, messageName):
        del self._messages[messageName]
        
        
    def _processAddMessageTemplate(self, message):
        uid = message.uid
        text = message.text
        failMessage = self.newMessage(uid, 
                                      "Your kmail was not in a valid format.")
        m = self._messageMatcher.search(text)
        if m is None:
            return failMessage 
        print "m1"
        newMessages = self._messageExtractor.findall(m.group("messageSection"))
        if not newMessages:
            return failMessage
        print "m2"
        messageName = "m{}".format(int(_epochTime()))
        newMessage = {'last': 0,
                      'hard': False,
                      'order': [],
                      'index': 0}
        try:
            newMessage['mode'] = self._modes[m.group("mode")]
            newMessage['period'] = int(m.group("period"))
            newMessage['offset'] = int(m.group("offset"))
            newMessage['channels'] = stringToList(m.group("channels"))
            newMessage['description'] = m.group("description")
            newMessage['messages'] = {"m{}".format(k): v 
                                      for k,v in enumerate(newMessages)}
            days = int(m.group("expires"))
            newMessage['expires'] = _epochTime() + days * 24 * 60 * 60
        except (KeyError, IndexError, ValueError):
            return failMessage
        
        self._messages[messageName] = newMessage
        return self.newMessage(uid, "Your announcement has been added.")
            
            
    def _deleteExpired(self):
        keepMe = lambda t: t == 0 or t > self._rolloverTime
        self._messages = {k: v for k,v in self._messages.items()
                          if keepMe(v.setdefault('expires', 0))} 
            
            
    @property
    def state(self):
        return {'messages': self._messages}
            
            
    @property 
    def initialState(self): 
        return {'messages': {}} 


    def _heartbeat(self): 
        if self._doFinishInit.is_set(): 
            self._doFinishInit.clear() 
            self._finishInitialization() 
            self._run.set() 
        if self._run.is_set(): 
            self._checkOrdering()
            self._deleteExpired()
            self._doAnnouncements(self._firstTime)
            self._firstTime = False
            
            
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "state":
            self._eventReply(self.state)
