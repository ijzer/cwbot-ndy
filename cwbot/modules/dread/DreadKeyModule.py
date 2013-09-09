from cwbot.modules.BaseDungeonModule import BaseDungeonModule
from cwbot.common.exceptions import FatalError

class DreadKeyModule(BaseDungeonModule):
    """ 
    Displays which paths have been opened in Dreadsylvania
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'dread']
    _name = "dread-keys"
    
    def __init__(self, manager, identity, config):
        self._areas = None
        self._dread = None
        super(DreadKeyModule, self).__init__(manager, identity, config)

        
    def initialize(self, state, initData):
        self._areas = [r for r in initData['event-db']
                       if r['zone'] == "(unlock)"]
        self._processLog(initData)


    def _processLog(self, raidlog):
        try:
            replies = self._raiseEvent("dread", "dread-overview", 
                                       data={'style': "dict",
                                             'keys': ['status', 'locked']})
            self._dread = replies[0].data
        except IndexError:
            raise FatalError("DreadKeyModule requires a DreadOverviewModule "
                             "with higher priority")
        return True

            
    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        return None
    
    
    def _processCommand(self, unused_msg, cmd, unused_args):
        if cmd in ["key", "keys", "locked", "unlocked"]:
            if not self._dungeonActive():
                return ("Dreadsylvania has disappeared into the mists. Don't "
                        "worry though, the keys transfer between dungeons "
                        "like in the first Legend of Zelda. They fixed that "
                        "in A Link to the Past.")
            
            txt = []
            for area in self._areas:
                areaData = self._dread[area['category']]
                areaname = area['subzone']
                areaStatus = areaData['status']
                if areaStatus in ["locked", "done", "boss"]:
                    txt.append("{} inaccessible".format(areaname))
                elif areaname in areaData['locked']:
                    txt.append("{} locked".format(areaname))
                else:
                    txt.append("{} unlocked".format(areaname))
            
            return ", ".join(txt)
        return None
        
                
    def _availableCommands(self):
        return {'keys': "!keys: Show which Dreadsylvanian areas are unlocked."}
    