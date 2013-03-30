from cwbot.modules.BaseModule import BaseModule


class AnnouncementModule(BaseModule):
    """ 
    A simple module that broadcasts a chat message when a system event is 
    detected. No messages are shown if the bot is in debug mode.
    The text %arg% is replaced with any additional information.
    
    Current system events:
    startup, shutdown, crash, manual_stop, manual_restart

    Configuration format:
        [[[[channelname]]]]
            signalname = message

    Configuration example:
    [[[AnnouncementModule1]]]
        type = AnnouncementModule
        priority = 0
        [[[[clan]]]]
            startup = All systems online.
            shutdown = Happy rollover!
            crash = Oh my, I seem to have crashed. (%arg%)
            manual_stop = I am going offline for some maintenance.
        [[[[hobopolis]]]]
            startup = Hobo-detection engaged.
            shutdown = Happy rollover!
            crash = Oh my, I seem to have crashed. (%arg%)
            manual_stop = I am going offline for some maintenance.
    """
    requiredCapabilities = ['chat']
    _name = "announce"

    def __init__(self, manager, identity, config):
        self._messages = {}
        super(AnnouncementModule, self).__init__(manager, identity, config)
        
        
    def _configure(self, config):
        for k,v in config.items():
            if isinstance(v, dict):
                self._messages[k] = dict(v.items())


    def _eventCallback(self, eData):
        if self.parent.properties.debug:
            return
        if eData.fromIdentity == "__system__":
            args = eData.data.get('args', "")
            for channel,msgDict in self._messages.items():
                txt = msgDict.get(eData.subject, "")
                if txt != "":
                    txt = txt.replace("%arg%", args)
                    self.chat(txt, channel)
