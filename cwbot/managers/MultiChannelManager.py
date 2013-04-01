import re
from BaseChatManager import BaseChatManager



class MultiChannelManager(BaseChatManager):
    """ A Chat Manager that monitors a single channel. Any PM messages are 
    also (optionally) processed. 
    """
    capabilities = ['chat', 'inventory', 'admin']
    
    def _chatApplies(self, x, _checkNum):
        """ Override of _chatApplies. Here, only chats from a single channel
        (or optionally, a PM) are accepted. """
        return ((self._respondToWhisper and x['type'] == 'private') or 
                 (x['type'] in ['normal', 'listen', 'emote'] and 
                  x['channel'].lower() in self._channelName))
        
    
    def __init__(self, parent, name, iData, config):
        """ Initialize the SingleChannelManager """
        self._channelName = []
        super(MultiChannelManager, self).__init__(parent, name, iData, config)
        
        
    def _configure(self, config):
        """ Additional configuration for SingleChannelManager """
        super(MultiChannelManager, self)._configure(config)
        channelList = config.setdefault('channel', "UNKNOWN")
        self._channelName = map(str.strip,  
                                map(str.lower, 
                                    re.split(r'\s*,\s*', channelList)))
        if not self._channelName or self._channelName == ["unknown"]:
            raise ValueError("Channel not set for {}".format(self.identity))
        self._log.debug("Set channels to {}"
                        .format(', '.join(self._channelName)))
        
            
    def defaultChannel(self):
        return self._channelName[0]


    def _showCommandSummary(self, msg, availableCommands, availableAdmin):
        """ Override for _showCommandSummary to show a more specialized !help
        message """
        txt = []
        pmText = " (and PM)" if self._respondToWhisper else ""
        if availableCommands is not None and len(availableCommands) > 0:
            txtChannelList = ("/{}".format(self._channelName[0]))
            if len(self._channelName) == 2:
                txtChannelList = ("/{0[0]} and /{0[1]}"
                                  .format(self._channelName))
            elif len(self._channelName) > 2:
                txtChannelList = ("/{}, and /{}"
                                  .format(', /'.join(self._channelName[:-1]),
                                          self._channelName[-1]))
                
            txt.append("Commands available in {}{}: !{}."
                       .format(txtChannelList, pmText,
                               ', !'.join(item for item in availableCommands)))
        if availableAdmin is not None and len(availableAdmin) > 0:
            txt.append("Admin commands available to {} in {}{}: !{}"
                       .format(msg.get('userName', msg['userId']),
                               txtChannelList, pmText,
                               ', !'.join(item for item in availableAdmin)))
        return txt
