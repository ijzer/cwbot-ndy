from cwbot.modules.BaseChatModule import BaseChatModule

class AboutModule(BaseChatModule):
    requiredCapabilities = ['chat']
    _name = "about"
    
    
    def _availableCommands(self):
        return {'about': '!about: show version information.'}
        
    
    def _processCommand(self, message, cmd, args):
        if cmd == "about":
            return ("cwbot version {}. http://sourceforge.net/projects/cwbot/"
                    .format(self.properties.version))
