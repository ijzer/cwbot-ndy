from cwbot.modules.BaseDungeonModule import BaseDungeonModule, eventFilter


def killPercent(n):
    return int(max(0, min(99, 100*n / 500.0)))


class ExposureModule(BaseDungeonModule):
    """ 
    A module that tracks Exposure Esplanade. EE is not well spaded, so
    this module just uses a linear approximation.
    
    No configuration options.
    """
    requiredCapabilities = ['chat', 'hobopolis']
    _name = "exposure"
    
    def __init__(self, manager, identity, config):
        super(ExposureModule, self).__init__(manager, identity, config)
        self._exposureDone = False
        self._open = False
        self._killed = None
        self._yodel = None
        self._pipes = None


    def initialize(self, state, initData):
        self._open = state['open']
        self._yodel = state['yodel']
        self._pipes = state['pipes']
        self._exposureDone = False
        self._processLog(initData)

            
    @property
    def state(self):
        return {'killed': self._killed,
                'yodel': self._yodel,
                'pipes': self._pipes,
                'open': self._open,
                'done': self._exposureDone}

    
    @property
    def initialState(self):
        return {'open': False,
                'yodel': [0, 0, 0],
                'pipes': 0}

    
    def getDone(self):
        # this formula is VERY approximate, and is a bit of a low-ball
        d = self._killed
        d += 1.2 * self._pipes
        d += 8 * self._yodel[0]
        d += 10.75 * self._yodel[1]
        d += 53 * self._yodel[2]
        
        # subtract 1 (2)? standard deviations
        c = 23
        d -= c * d/(500.0 + c)
        return d

    
    def getTag(self):
        if self._exposureDone:
            return "[Exposure done]"
        if not self._open:
            return "[Exposure closed]"
        percent = killPercent(self.getDone())
        return "[Exposure >{}%]".format(percent)


    def _processLog(self, raidlog):
        events = raidlog['events']
        # hobos killed by non-yodels
        oldYodel = self._yodel
        oldPipes = self._pipes
        
        self._killed = sum(
                coldhobo['turns'] for coldhobo in eventFilter(
                    events, r'defeated +Cold hobo'))
            
        self._yodel = (
                [sum(yodel0['turns'] for yodel0 in eventFilter(
                    events, "yodeled a little bit")),
                 sum(yodel1['turns'] for yodel1 in eventFilter(
                    events, "yodeled quite a bit")),
                 sum(yodel2['turns'] for yodel2 in eventFilter(
                    events, "yodeled like crazy"))])

        self._pipes = sum(pipeevent['turns'] for pipeevent in eventFilter(
                              events, r'broke .* water pipe'))

        self._exposureDone = any(eventFilter(events, r'defeated +Frosty'))

        if self._killed > 0 or self._pipes > 0 or sum(self._yodel) > 0:
            self._open = True
            
        if oldPipes < self._pipes and oldPipes is not None:
            #self.log("Added {} pipes".format(self._pipes - oldPipes))
            pass
           
        if oldYodel is not None: 
            yodelDiff = [new-old for new,old in zip(self._yodel, oldYodel)]
            for _idx,diff in enumerate(yodelDiff):
                if diff > 0:
                    #self.log("Added {} yodel{}".format(diff,_idx), 'exposure')
                    pass
        return True


    def _processDungeon(self, txt, raidlog):
        self._processLog(raidlog)
        if self._exposureDone:
            return None
        return None


    def _processCommand(self, msg, cmd, args):
        if cmd in ["exposure", "ee"]: 
            if not self._dungeonActive():
                return "Hodgman is dead. Stop playing in the snow!."
            if self._exposureDone:
                return "{} Frosty melted. Gross!".format(self.getTag())
            return "{} Brrrrr!".format(self.getTag())
        return None


    def reset(self, _events):
        self._exposureDone = False
        self._open = False
        self._killed = 0
        self._yodel = [0, 0, 0]
        self._pipes = 0
        #self.log("reset!", 'exposure')

        
    def _eventCallback(self, eData):
        s = eData.subject
        if s == "done":
            self._eventReply({'done': self.getTag()[1:-1]})
        elif s == "open":
            self._open = True
        elif s == "state":
            self._eventReply(self.state)
    
    
    def _availableCommands(self):
        return {'exposure': "!exposure: Display information about Exposure "
                            "Esplanade.",
                'ee': None}
