from collections import defaultdict
import time
from cwbot.modules.BaseKmailModule import BaseKmailModule


def _returnedInLast(timeList, seconds):
    now = time.time()
    then = now - seconds
    return sum(1 for t in timeList if t > then)


class UnknownKmailModule(BaseKmailModule):
    """ 
    A module that returns a kmail and says that it doesn't understand.
    
    No configuration options.
    """
    requiredCapabilities = ['kmail']
    _name = "unknown"
    
    def __init__(self, manager, identity, config):
        super(UnknownKmailModule, self).__init__(manager, identity, config)
        self._returned = defaultdict(list)

        
    def _processKmail(self, message):
        self.log("Unknown message: {}".format(message))
        self._returned[message.uid].append(time.time())
        inLastHour = _returnedInLast(self._returned[message.uid], 3600)
        sinceStartup = _returnedInLast(self._returned[message.uid], 86400)
        newMsg = self.newMessage(message.uid, 
                                 "I don't understand your request.",
                                 message.meat).addItems(message.items)
                                 
        # if too many messages are being sent, stop output. This stops a
        # ping-pong with another bot.
        if inLastHour == 5:
            newMsg.text = ("You've sent me five messages that I can't "
                           "understand in the last hour. I will still answer "
                           "your mails, but if you send another message I "
                           "can't understand, I will ignore it.")
        elif inLastHour > 5:
            newMsg.info['defer'] = True
        elif sinceStartup == 20:
            newMsg.text = ("You've sent me 20 messages that I can't "
                           "understand today. I will still answer "
                           "your mails, but if you send another message I "
                           "can't understand, I will ignore it.")
        elif sinceStartup > 20:
            newMsg.info['defer'] = True
        return newMsg
