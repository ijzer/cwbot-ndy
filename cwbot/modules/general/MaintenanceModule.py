import datetime
from cwbot.modules.BaseChatModule import BaseChatModule
import kol.Error
from cwbot.common.kmailContainer import Kmail
from kol.request.StatusRequest import StatusRequest


class MaintenanceModule(BaseChatModule):
    """ 
    A module that has various maintenance capabilities. This module should
    be protected with a permission setting.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'admin']
    _name = "maintenance"
    
    def __init__(self, manager, identity, config):
        self._startTime = datetime.datetime.now()
        super(MaintenanceModule, self).__init__(manager, identity, config)


    def _processCommand(self, message, cmd, args):
        if cmd == "die":
            args = args.strip()
            if args == "":
                args = "0"
            try:
                t = int(args)
                e = kol.Error.Error("Manual crash")
                e.timeToWait = t * 60 + 1
                self.chat("Coming online in {} minutes.".format(t))
                raise e
            except kol.Error.Error:
                raise
            except:
                pass
            return "Invalid argument to !die '{}'".format(args)
        elif cmd == "simulate":
            self.parent.director._processChat([{'text': args, 
                                               'userName': "Dungeon", 
                                               'userId': -2,
                                               'channel': "hobopolis",
                                               'type': "normal",
                                               'simulate': True}])
            return "Simulated message: {}".format(args)
        elif cmd == "spam":
            return "\n".join(["SPAM"] * 15)
        elif cmd == "restart":
            self._raiseEvent("RESTART", "__system__")
        elif cmd == "raise_event":
            r = self._raiseEvent(args)
            return "Reply to event '{}': {}".format(args, r)
        elif cmd == "kmail_test":
            n = 1000
            try:
                n = int(args)
            except Exception:
                pass
            
            text = ""
            count = 0
            startChar = "A"
            while n >= 100:
                count += 100
                n -= 100
                newText = "A" * 100 + "{}".format(count)
                newText = startChar + newText[-99:]
                text += newText 
                startChar = " "
            k = Kmail(message['userId'], text)
            self.sendKmail(k)
        elif cmd == "bot_status":
            r = StatusRequest(self.session)
            d = self.tryRequest(r)
            return "\n".join("{}: {}".format(k,v) for k,v in d.items()
                             if k not in ["pwd", "eleronkey"])
        elif cmd == "inclan":
            tf = self.parent.checkClan(int(args))
            return str(tf)
        elif cmd == "plist":
            return str(self.properties.getPermissions(int(args)))
        return None


    def _availableCommands(self):
        return {'die': "!die: Crash the bot. Seriously. This will raise an "
                       "exception and the bot will crash. '!die N' crashes "
                       "for N minutes.",
                'simulate': "!simulate: treat the following message as if it "
                            "were coming from Dungeon on /hobopolis.",
                'restart': "!restart: restarts the bot. This actually "
                           "restarts the process instead of just restarting "
                           "the main loop, and reloads all code.",
                'spam': None,
                'raise_event': None,
                'kmail_test': None,
                'inclan': None,
                'plist': None,
                'bot_status': "!bot_status: Show the status information of "
                              "the bot. Spammy."}

