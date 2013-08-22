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
        self._choiceCategories = None
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
            self._userAdventures.setdefault(userName, [])
            self._properUserNames[userName] = e['userName']
            if zone in self._choiceLocations:
                self._userAdventures[userName].append(e['db-match'])
            
                
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
            isSelf = False
            if not self._dungeonActive():
                return ("How can you choose what doesn't exist?")
            if args == "":
                isSelf = True
                args = msg['userName']
            user = "".join(args.split()).strip().lower()
            choices = self._userAdventures.get(user)
            if isSelf and choices is None:
                choices = []
                self._properUserNames[user] = msg['userName']
            elif choices is None:
                return ("Player {} has not adventured in this Dreadsylvania "
                        "instance.".format(args))
            
            playerChoicesLeft = []
            playerChoicesMade = []
            for zone in self._choiceLocations:
                zoneMatches = [e for e in choices if e['zone'] == zone]
                if zoneMatches:
                    playerChoicesMade.append((zone, zoneMatches[0]['code']))
                else:
                    zoneData = self._dread[self._choiceCategories[zone]]
                    if zoneData['status'] not in ["done", "boss"]:
                        playerChoicesLeft.append(zone)
                    else:
                        playerChoicesMade.append((zone, "missed"))
            txt = "{}: ".format(self._properUserNames[user])
            if playerChoicesMade:
                txt += "[{}] ".format(", ".join("{0[0]}: {0[1]}"
                                                .format(args)
                                                for args in playerChoicesMade))
            if playerChoicesLeft:
                txt += "Still available: {}.".format(
                                                ", ".join(playerChoicesLeft))
            else:
                txt += "None left."
            return txt
        return None
        
                
    def _availableCommands(self):
        return {'choices': "!choices: Display the Dreadsylvania choice "
                           "adventures that are still available to you "
                           "(or another player with !choices PLAYERNAME)."}
    