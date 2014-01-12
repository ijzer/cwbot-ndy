from cwbot.modules.BaseDungeonModule import BaseDungeonModule
from cwbot.kolextra.request.ClanDungeonLootRequest import ClanDungeonLootRequest

def _nameKey(x):
    return "".join(x.split()).strip().lower()

class DreadLootModule(BaseDungeonModule):
    """
    This is a module which kmails a list of who gets what to the dungeon manager
    who invokes it. This should be used after the dungeon is finished, and reads
    from the logs.

    No configuration options
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-loot"

    def __init__(self, manager, identity, config):
        self._userKills = None
        self._userBosses = None
        self._properUserNames = None
        super(DreadLootModule, self).__init__(manager, identity, config)


    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._userKills = {}
        self._userBosses = {}
        self._processLog(initData)


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._userKills = {}
        self._userBosses = {}
        self._properUserNames = {}
        for e in events:
            user = _nameKey(e['userName'])
            if e['category'] != "Miscellaneous":
                self._userKills.setdefault(user, 0)
                self._userBosses.setdefault(user, 0)
                self._properUserNames[user] = e['userName']
                zone = e['db-match'].get('zone')
                if zone == "(combat)":
                    subzone = e['db-match'].get('subzone')
                    if subzone == "normal":
                        self._userKills[user] += e['turns']
                    elif subzone == "boss":
                        self._userBosses[user] += e['turns']
        return True


    def _processCommand(self, msg, cmd, args):
        if cmd in ["loot"]:
            r = ClanDungeonLootRequest(self.session)
            ul = self.tryRequest(r)
            killList = []
            uid = msg["userId"]
            if args.strip() == "":
                args = msg['userName']
            for name in sorted(self._properUserNames.values()):
                user = _nameKey(name)
                kills = self._userKills.get(user)
                bosses = self._userBosses.get(user)
                total = kills + bosses
                for k in ul["hardMode"].values():
                    if k == user:
                        total += 50
                if total == 0:
                   continue

                killList.append("{}: {} turns."
                            .format(name, total))
#            sendDreadLoot(msg, uid)
            return "\n".join(killList)
        return None


    def sendDreadLoot(self, msg, uid):
        pass


    def _availableCommands(self):
        return {"loot": "!loot: compiles a list of how many kills each user"
                        " in the dungeon has and kmails it to the caller."
                        }