from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter
from cwbot.common.exceptions import FatalError
from collections import defaultdict


def _nameKey(x):
    return "".join(x.split()).strip().lower()


class DreadKillsModule(BaseDungeonModule):
    """ 
    Displays which choice adventures a player may use in dreadsylvania.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-kills"
    
    def __init__(self, manager, identity, config):
        self._userKills = None
        self._userBosses = None
        self._properUserNames = None
        super(DreadKillsModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._userKills = {}
        self._userBosses = {}
        self._processLog(initData)


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._userKills = defaultdict(int)
        self._userBosses = defaultdict(int)
        self._properUserNames = {}
        for e in events:
            user = _nameKey(e['userName'])
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
        if cmd in ["kills", "killed"]:
            self._properUserNames[_nameKey(msg['userName'])] = msg['userName']

            if args.strip() == "":
                args = msg['userName']
            user = _nameKey(args)
            properName = self._properUserNames.get(user, args)
            kills = self._userKills.get(user, 0)
            bosses = self._userBosses.get(user, 0)
            if kills + bosses == 0:
                return ("Player {} has not adventured in this Dreadsylvania "
                        "instance.".format(properName))
            
            if bosses > 0:
                return ("{}: {} monsters and {} bosses defeated."
                        .format(properName))
            else:
                return ("{}: {} monsters defeated."
                        .format(properName, kills))
        return None
        
                
    def _availableCommands(self):
        return {'kills': "!kills: Display how many monsters you have killed "
                         "in this Dreadsylvania instance. "
                         "(or another player with !kills PLAYERNAME)."}
    