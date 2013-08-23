import re
from cwbot.modules.BaseChatModule import BaseChatModule

__compiled = {}

def eventFilter(events, *text):
    """
    This function is often used in dungeon module parsing. It returns a 
    generator that returns log entries that have an event that matches 
    any of the regexes passed in. It is used so commonly that this function
    is very convenient. Regexes are automatically compiled and cached.
    """
    regexText = '|'.join(text)
    regex = __compiled.setdefault(regexText, re.compile(regexText))
    return (e for e in events if regex.search(e['event']) is not None)


def eventDbMatch(events, *categoryDicts):
    """
    This function is often used in dungeon module parsing. It returns a 
    generator that returns log entries that have an event that matches 
    any of the regexes passed in. It is used so commonly that this function
    is very convenient. Regexes are automatically compiled and cached.
    """
    sets = [set(d.items()) for d in categoryDicts]
    return (e for e in events 
            if any(s.issubset(set(e['db-match'].items()))
                   for s in sets))

    
class BaseDungeonModule(BaseChatModule):
    """This class extends BaseChatModule to process Hobopolis information, 
    including Dungeon messages and raid logs. In addition to those in
    BaseChatModule, there are two extended calls: 
    process_dungeon -> _processDungeon is called when dungeon chat is received;
    process_log -> _processLog is called periodically when the dungeon log
    is reread. It's also advised to call this function inside of 
    _processDungeon.
    """
    requiredCapabilities = []
    _name = None

    
    def __init__(self, manager, identity, config):
        """
        Initialize BaseDungeonModule
        """
        super(BaseDungeonModule, self).__init__(manager, identity, config)
        self._registerExtendedCall('process_dungeon', self._processDungeon)
        self._registerExtendedCall('process_log', self._processLog)

        
    def _dungeonActive(self):
        """ Is dungeon alive? """
        return self.parent.active()


#####################################
# Only override the functions below
#####################################
    
        
    def initialize(self, lastKnownState, initData):
        """
        Initialize hobo module state. initData should contain the 
        event log. This function is called by the manager after construction
        with the last known state of the Hobo Module. If a NEW hobopolis 
        instance is detected, lastKnownState == self.initialState.
        
        Any initialization processing should be done here.
        """
        pass

    
    def _processDungeon(self, dungeonText, lastRaidLog):
        """
        Process chat from the Dungeon messages.
        All Dungeon messages are sent to this function. The derived class 
        should process those that apply and ignore the others.

        This function must return either a string, which will be printed in 
        chat; or None, to do nothing.
        
        Also, at some point in this function, self._processLog(lastRaidLog) 
        should be called. Probably.
        
        Unlike _processCommand, the HoboChatManager calls _processDungeon
        for EVERY module it controls. This is because some dungeon
        announcements affect more than one zone; for example, the Dugneon
        message "X flimflammed some hobos..." affects the number of available
        dances in the AHBG and also the popularity of the nightclub in the
        PLD.
        """
        pass


    def _processLog(self, lastRaidLog):
        """
        Process new information from the most recent log reading here.
        """
        pass
