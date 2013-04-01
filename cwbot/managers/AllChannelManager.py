from cwbot.managers.BaseChatManager import BaseChatManager
 
    
class AllChannelManager(BaseChatManager):
    """ A simple Manager that accepts chats on all channels. """
    capabilities = ['chat', 'inventory', 'admin']
        
    def __init__(self, parent, name, iData, config):
        """ Initialize the AllChannelManager """
        super(AllChannelManager, self).__init__(parent, name, iData, config)
        self._currentChannel = self.chatManager.currentChannel


    def defaultChannel(self):
        return self._currentChannel

    
    def _showCommandSummary(self, msg, availableCommands, availableAdmin):
        """ Override of _showCommandSummary to show "all channels" """
        txt = []
        pmText = " (and PM)" if self._respondToWhisper else ""
        if availableCommands is not None and len(availableCommands) > 0:
            txt.append("Commands available on all channels{}: !{}."
                       .format(pmText, 
                               ', !'.join(item for item in availableCommands)))
        if availableAdmin is not None and len(availableAdmin) > 0:
            txt.append("Admin commands available to {} on all channels{}: !{}"
                       .format(msg.get('userName', msg['userId']), pmText,
                               ', !'.join(item for item in availableAdmin)))
        return txt

        
    def parseChat(self, msg, checkNum):
        """ Override of parseChat. Sets the current channel to the same as
        the most recent received chat. This way we always reply on the
        same channel that the message was received. """
        self._currentChannel = msg.get('channel', self._currentChannel) 
        return super(AllChannelManager, self).parseChat(msg, checkNum)
