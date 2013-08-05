from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter
from cwbot.common.exceptions import FatalError


class DreadChoicesModule(BaseDungeonModule):
    """ 
    Displays which choice adventures a player may use in dreadsylvania.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-choices"
    
    def __init__(self, manager, identity, config):
        self._choiceLocations = None
        self._userAdventures = None
        self._properUserNames = None
        super(DreadChoicesModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._db = initData['event-db']
        self._choiceLocations = []
        self._choiceCategories = {}
        for record in self._db:
            zone = record['zone']
            if not zone.startswith("("):
                if zone not in self._choiceLocations:
                    self._choiceLocations.append(zone)
                self._choiceCategories[zone] = record['category']
        self._processLog(initData)


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._userAdventures = {}
        self._properUserNames = {}
        for e in events:
            zone = e['db-match'].get('zone')
            userName = "".join(e['userName'].split()).strip().lower()
            self._userAdventures.setdefault(userName, set())
            self._properUserNames[userName] = e['userName']
            if zone in self._choiceLocations:
                self._userAdventures[userName].add(zone)
            
                
        try:
            replies = self._raiseEvent("dread", "dread-overview", 
                                       data={'style': 'dict',
                                             'keys': ['status']})
            self._dread = replies[0].data
        except IndexError:
            raise FatalError("DreadChoicesModule requires a "
                             "DreadOverviewModule with higher priority")
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, msg, cmd, args):
        if cmd in ["choice", "choices"]:
            if not self._dungeonActive():
                return ("How can you choose what doesn't exist?")
            if args == "":
                args = msg['userName']
            user = "".join(args.split()).strip().lower()
            isSelf = (msg['userName'] == self._properUserNames.get(user, ""))
            choices = self._userAdventures.get(user)
            if isSelf and choices is None:
                choices = []
            elif choices is None:
                return ("Player {} has not adventured in this Dreadsylvania "
                        "instance.".format(args))
            
            playerChoicesLeft = []
            for zone in self._choiceLocations:
                if zone not in choices:
                    zoneData = self._dread[self._choiceCategories[zone]]
                    if zoneData['status'] not in ["done", "boss"]:
                        playerChoicesLeft.append(zone)
            if not playerChoicesLeft:
                return ("Player {} has no more choice adventures available "
                        "in Dreadsylvania."
                        .format(self._properUserNames[user]))
            return ("Choices available to {}: {}"
                    .format(self._properUserNames[user],
                            ", ".join(playerChoicesLeft)))
        return None
        
                
    def _availableCommands(self):
        return {'choices': "!choices: Display the Dreadsylvania choice "
                           "adventures that are still available to you "
                           "(or another player with !choices PLAYERNAME)."}
    