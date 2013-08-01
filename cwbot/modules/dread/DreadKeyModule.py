from cwbot.modules.BaseHoboModule import BaseHoboModule, eventFilter

class DreadKeyModule(BaseHoboModule):
    """ 
    Displays which paths have been opened in Dreadsylvania
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-keys"
    
    _areas = {0: {'attic': "unlocked the attic of the cabin",
                  'fire tower': "unlocked the fire watchtower"},
              1: {'suite': "unlocked the master suite",
                  'school': "unlocked the schoolhouse"},
              2: {'ballroom': "unlocked the ballroom",
                  'lab': "unlocked the lab"}}
    
    def __init__(self, manager, identity, config):
        self._woodsDone = None
        self._villageDone = None
        self._castleDone = None
        self._woodsKilled = None
        self._villageKilled = None
        self._castleKilled = None
        self._drunk = None
        self._unlocked = None
        super(DreadKeyModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._processLog(initData)


    @property
    def state(self):
        return {}

    
    @property
    def initialState(self):
        return {}

    
    def getTag(self):
        return ""


    def _processLog(self, raidlog):
        events = raidlog['events']
        self._woodsDone   = any(eventFilter(events, r"""(?i)defeated\s+(The Great Wolf of the Air|Falls-From-Sky)"""))
        self._villageDone = any(eventFilter(events, r"""(?i)defeated\s+(the Zombie Homeowners' Association|Mayor Ghost)"""))
        self._castleDone  = any(eventFilter(events, r"""(?i)defeated\s+(The Unkillable Skeleton|Count Drunkula)"""))
        self._drunk = raidlog['dread']['drunkenness']
        self._woodsKilled   = raidlog['dread'].get('forest', 0)
        self._villageKilled = raidlog['dread'].get('village', 0)
        self._castleKilled  = raidlog['dread'].get('castle', 0)
        self._unlocked = set()
        for advs in self._areas.values():
            for advName, advRegex in advs.items():
                if any(eventFilter(events, advRegex)):
                    self._unlocked.add(advName)
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
        
        
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["key", "keys"]:
            if not self._dungeonActive():
                return ("Dreadsylvania has disappeared into the mists. Don't "
                        "worry though, the keys transfer between dungeons "
                        "like in the first Legend of Zelda. They fixed that "
                        "in A Link to the Past.")
            doneAreas = [self._woodsDone or self._woodsKilled >= 1000, 
                         self._villageDone or self._villageKilled >= 1000, 
                         self._castleDone or self._castleKilled >= 1000]
            closedAreas = [False, self._drunk < 1000, self._drunk < 2000]
            txt = []
            
            for areaIdx, advs in self._areas.items():
                for advName in advs.keys():
                    if doneAreas[areaIdx] or closedAreas[areaIdx]:
                        txt.append("{} inaccessible".format(advName))
                    elif advName in self._unlocked:
                        txt.append("{} open".format(advName))
                    else:
                        txt.append("{} locked".format(advName))
            
            return ", ".join(txt)
        return None
        
                
    def _availableCommands(self):
        return {'keys': "!keys: Show which Dreadsylvanian areas are unlocked."}
    