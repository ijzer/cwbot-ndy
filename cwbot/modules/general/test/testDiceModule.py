import unittest
from cwbot.modules.test.MockChatManager import MockChatManager
from cwbot.modules.general.DiceModule import DiceModule

class Test(unittest.TestCase):
     
    @classmethod
    def setUpClass(cls):
        cls._manager = MockChatManager()
        cls._manager.setProperty('debug', False)
        m = DiceModule(cls._manager, "A", {})
        cls._manager.addModule(m)
        
    @classmethod
    def tearDownClass(cls):
        cls._manager.cleanup()
        
    def test(self):
        r = self._manager.processCommand({}, 'roll', 
                    "2^(1+1*2d1)/(1/2)-1+1+2*3d1+(-2d1)+2*(3+4d1^2)^2/3")
        txt = r[0]
        self.assertTrue("260.66" in txt)
        
        r = self._manager.processCommand({'text': "!roll (1+2)+3"}, 
                                         'roll', "1+2")
        self.assertEqual(r[0][-2:], " 6")
        
        r = self._manager.processCommand({'text': "!roll (1+2)RAWR"}, 
                                         'roll', "1+2")
        self.assertEqual(r[0][-2:], " 3")
        

if __name__ == '__main__':
    unittest.main()