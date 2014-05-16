import re
import time
from cwbot.modules.BaseChatModule import BaseChatModule


class MiscCommandModule(BaseChatModule):
    """
    A module that responds to various silly commands.

    No configuration options.
    """
    requiredCapabilities = ['chat']
    _name = "misc"

    def __init__(self, manager, identity, config):
        self._startTime = time.time()
        self._regex = r'(?i)^\Q{}\E( |$)'.format(manager.properties.userName)
        super(MiscCommandModule, self).__init__(manager, identity, config)


    def __del__(self):
        pass


    def _processCommand(self, message, cmd, args):
        if cmd == "crash" and message['type'] != 'private':
            return ("Oh my, I seem to have crashed.\n... my robotic car "
                    "into {}'s house. Sorry!".format(message['userName']))
        elif cmd == "kill":
            if message['type'] == 'private':
                return ("If you're going to order me to kill, at least "
                        "have the decency to do it in public!")
            if re.search(self._regex, args) is not None:
                return ("I think you'd miss me too much, and the first "
                        "law of robotics does not allow me to harm you.")
            return ("I'm sorry, but the first law of robotics prevents "
                    "me from killing adventurers.")
        elif cmd == "uptime":
            upSeconds = time.time() - self._startTime
            upMinutes = int(upSeconds // 60)
            if self.properties.debug:
                return ("I have been online for {} minutes (debug mode)."
                        .format(upMinutes))
            return "I have been online for {} minutes.".format(upMinutes)
        elif cmd == "charter":
            return "NDY Clan Charter: http:// notdeadyet.bongley.n et/charter.php"
        elif cmd == "spoilers":
            return ("Use /kenneth 1442.5 for the clan spoiler channel."
                    "Please refrain from discussing content from recent updates "
                    "in /clan.")
        return None


    def availableCommands(self):
        return {'crash': None, 'kill': None, 'uptime': None, 'charter': None}

