from fuzzywuzzy import process
from cwbot.modules.BaseChatModule import BaseChatModule

class DreadSignupModule(BaseChatModule):
    requiredCapabilities = ["chat"]
    _name = "dread-signup"

    def __init__(self, manager, identity, config):
        super(DreadSignupModule, self).__init__(manager, identity, config)
        self._signupList = {}
        self._bosses = {}

    def initialize(self, state, iData):
        self._signupList = state
        self._bosses = ["Great Wolf of the Air",
                        "Falls-From-Sky",
                        "Mayor Ghost",
                        "Zombie Homeowner's Association",
                        "The Unkillable Skeleton",
                        "Count Drunkula"]

    @property
    def initialState(self):
        return {"Great Wolf of the Air" : [],
                "Falls-From-Sky" : [],
                "Mayor Ghost" : [],
                "Zombie Homeowner's Association" : [],
                "The Unkillable Skeleton" : [],
                "Count Drunkula" : []}

    @property
    def state(self):
        return self._signupList

#    def reset(self, initData):
#        pass

    def dungeonReset(self, initData):
        self.initialize(self.initialState, initData)

    def processBoss(self, args):
        boss = process.extractOne(args, self._bosses)
        if boss:
            return boss[0]
        else:
            return None

    def printBossList(self, boss):
        msg = boss + ": "
        if self._signupList[boss] == []:
            msg += "no one. go for a normal mode kill, if you'd like."
        else:
            for user in self._signupList[boss]:
                msg += "{} (#{}), ".format(user[0], user[1])
        return msg

    def addToSignup(self, user, boss):
        if boss == None:
            return "sorry, i don't know which boss you mean."
        self._signupList[boss].append(user)
        return ("user {} (#{}) added to list of hardmode killers for {}"
                .format(user[0], user[1], boss))
            
    def removeFromSignup(self, user, boss):
        if boss == None:
            return "sorry, i don't know which boss you mean."
        try:
            self._signupList[boss].remove(user)
            return ("user {} (#{}) removed from list of hardmode killers for {}"
                    .format(user[0], user[1], boss))
        except ValueError:
            return ("user {} (#{}) was not on the list of hardmode killers for {}"
                    .format(user[0], user[1], boss))

    def sendSignup(self, boss):
        if boss == None:
            msg = ""
            for boss in self._signupList.keys():
                msg += "{}\n".format(self.printBossList(boss))
        else:
            msg = self.printBossList(boss)
        return msg

    def _processCommand(self, msg, cmd, args):
        if cmd == "signup":
            user = (msg["userName"], msg["userId"])
            argsp = args.partition(" ")
            if args == "reset":
                admins = self.properties.getAdmins("dungeon_master")
                if user[1]  in admins:
                    self.dungeonReset(None)
                    return "resetting signup list"
                else:
                    return "you don't have permission to reset the signup list. ask a dungeon master"
            if argsp[0] == "add":
                return self.addToSignup(user, self.processBoss(argsp[2]))
            elif argsp[0] == "remove":
                return self.removeFromSignup(user, self.processBoss(argsp[2]))
            elif argsp[0] == "list":
                return self.sendSignup(self.processBoss(argsp[2]))
            else:
                return self.sendSignup(self.processBoss(args))
        return None

    def _availableCommands(self):
        return {"signup":"!signup: print signup list for hardmode boss kills. !signup add <boss> to add yourself to a list, !signup remove <boss> to remove yourself."}
