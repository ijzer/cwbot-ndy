from BaseModule import BaseModule
from cwbot.common.kmailContainer import Kmail
    
    
class BaseKmailModule(BaseModule):
    """ A module that processes Kmails. See documentation for _processKmail. 
    Three extended calls: process_message -> _processKmail is called by the
    manager when new Kmails arrive. message_send_failed -> _messageSendFailed
    is called by the director when a message fails to send (though, most failed
    messages are still marked as "success" by the MailHandler and held for
    later sending. This function may be called at some later time, since mails
    are sent asynchronously. module_description -> _moduleDescription holds
    a description of what the module does. This isn't actually used right now
    and may be removed in the future.
    """
    requiredCapabilities = []
    _name = ""
    
    
    def __init__(self, manager, identity, config):
        super(BaseKmailModule, self).__init__(manager, identity, config)
        self._registerExtendedCall('process_message', self._processKmail)
        self._registerExtendedCall('kmail_description', self._kmailDescription)
        self._registerExtendedCall('message_send_failed', 
                                   self._messageSendFailed)

    # alias for Kmail (for compatibility)
    def newMessage(self, uid, text="", meat=0):
        """ Create a new Kmail object. """
        return Kmail(uid, text, meat)    
        
        
    def sendKmail(self, message):
        """ Send a Kmail. Do NOT use this to reply to a kmail under normal
        circumstances, since it will not be protected from double-sending
        from the MailHandler. """
        self.parent.sendKmail(message)


    def _processKmail(self, message):
        """
        Process a Kmail.

        message contains the full message in a Kmail object, with properties
        'uid' as the id number of the sender, 'text' as the string in the 
        message, 'items' is a dictionary with (itemIdNumber: quantity) entries
        of attachments, and 'meat' is the amount of meat attached. The
        property 'info' holds a dictionary that is the pyKol format of the
        message.
        
        You should return None if you don't want to process the message in 
        this module, in which case it will be passed to the next module in the
        line. If you want to respond, return Kmail object 
        (with self.newMessage). Unlike chat modules, if you respond to a 
        message, other modules will NOT get a chance to process the message. 
        The manager must call the modules in order of decreasing priority.
        If you want to accept a message but don't want to send a reply, 
        return a NewMessage object with a uid of -1.
        
        It is important to NOT use the sendKmail() method to reply to a
        kmail, if you can avoid it. If there is some sort of problem
        (e.g., a power failure or an exception), the responses sent here
        will be rolled back and the kmail will be reprocessed; 
        those using sendKmail() will not be and multiple kmails may be
        sent as a result.
        
        The MessageManager also supports multiple replies from the same module,
        so if you need to send more than one Kmail, return a list of Kmail
        objects.
        """
        return None

    
    def _messageSendFailed(self, sentMessage, exception):
        """
        This function is called if a message fails to send.
        So you can do cleanup if required.
        sentMessage is the Kmail object you sent.
        """
        pass


    def _kmailDescription(self):
        """ Return a string from this function that describes how this
        module behaves. If a user sends a "help" kmail, the MessageManager
        will compile all available descriptions and return a help kmail.
        
        To "hide" the module, return None.
        """
        return None
