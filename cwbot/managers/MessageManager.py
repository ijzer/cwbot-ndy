from cwbot.kolextra.manager.MailboxManager import MailboxManager
from cwbot.managers.BaseManager import BaseManager
from cwbot.common.kmailContainer import KmailResponse


class MessageManager(BaseManager):
    """ A manager that handles Kmails only. Unlike the chat-based managers,
    the MessageManager uses Kmail module priority cascading: only the
    highest-priority Kmail module processes the kmail. """
    capabilities = ['chat', 'inventory', 'admin', 'kmail']
        
    def __init__(self, parent, name, iData, config):
        """ Initialize the MessageManager """
        self._channelName = None
        super(MessageManager, self).__init__(parent, name, iData, config)
        self._mail = MailboxManager(self._s)
        self._chatChannel = None


    def _configure(self, config):
        """ Configuration also requests a channel name """
        super(MessageManager, self)._configure(config)
        # set to channel in config
        self._channelName = config.setdefault(
                'channel', self.chatManager.currentChannel) 


    def defaultChannel(self):
        return self._chatChannel

    
    def _processKmail(self, message):
        """ This is the main processing funciton for Kmail objects. """
        responses = []
        for m in self._modules:
            mod = m.module
            permission = m.permission
            clanOnly = m.clanOnly
            sendMessage = None
            if not clanOnly or self.checkClan(message.uid):
                if (permission is None or 
                    permission == "" or 
                    permission == "None"):
                    # no permission required
                    sendMessage = mod.extendedCall('process_message', message)
                elif permission in self.properties.getPermissions(message):
                    # checked permission!
                    sendMessage = mod.extendedCall('process_message', message)
                    if sendMessage is not None:
                        self._log.info("Administrator {} ({}) has used "
                                       "permission {} to process a kmail with "
                                       "module {}."
                                       .format(message.uid, 
                                               message.info.get(
                                                   'userName', "unknown name"), 
                                               permission, m))

            if sendMessage is not None:
                if sendMessage.uid >= 0:
                    try:
                        # add list of responses if a list was returned
                        responses.extend(
                            map(lambda m: KmailResponse(self, mod, m), 
                                sendMessage))
                    except TypeError:
                        # looks like it was just a single message
                        responses.append(KmailResponse(self, mod, sendMessage))
                break # do not continue to "lower" modules
        return responses


    def parseKmail(self, message):
        """ Process a Kmail. This function is called by the
        CommunicationDirector every time a Kmail is received. """
        if message.uid != self.session.userId:
            return self._processKmail(message)
