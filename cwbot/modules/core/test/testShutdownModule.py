import unittest
from cwbot.modules.test.MockChatManager import MockChatManager
from cwbot.modules.general.ShutdownModule import ShutdownModule
import kol.Error

class Test(unittest.TestCase):
     
    @classmethod
    def setUpClass(cls):
        cls._manager = MockChatManager(0.001)
        cls._manager.setProperty('debug', False)
        m = ShutdownModule(cls._manager, "A", {'shutdown_time': 5})
        cls._manager.addModule(m)
        
    @classmethod
    def tearDownClass(cls):
        cls._manager.cleanup()
        
    def test(self):
        self._manager.raiseSystemEvent("rollover", data={'time':10})
        self._manager.waitForHeartbeat(2)
        self.assertEqual(len(self._manager.operations), 0, 
                         "Rollover triggered too soon.")
        self._manager.raiseSystemEvent("rollover", data={'time':5})
        self._manager.waitForHeartbeat(2)
        self.assertEqual(len(self._manager.operations), 1, 
                         "Rollover not triggered.")
        self.assertEqual(self._manager.operations[-1]['type'], 'event', 
                         "Non-event raised.")
        self.assertEqual(self._manager.operations[-1]['event'].subject, 
                         "EventToSystem", 
                         "Not a system event from ShutdownModule")
        self.assertEqual(self._manager.operations[-1]['event'].data.subject, 
                         "LOGOUT", 
                         "Not a logout event from ShutdownModule")
        self._manager.raiseSystemEvent("rollover", data={'time':1})
        self._manager.waitForHeartbeat(2)
        self.assertEqual(len(self._manager.operations), 2, 
                         "Rollover not triggered.")
        self.assertEqual(self._manager.operations[-1]['type'], 'event', 
                         "Non-event raised.")
        self.assertEqual(self._manager.operations[-1]['event'].subject, 
                         "EventToSystem", 
                         "Not a system event from ShutdownModule")
        self.assertEqual(self._manager.operations[-1]['event'].data.subject, 
                         "LOGOUT", 
                         "Not a logout event from ShutdownModule")


if __name__ == '__main__':
    unittest.main()
    