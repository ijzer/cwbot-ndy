import unittest
from cwbot.modules.test.MockChatManager import MockChatManager
from cwbot.modules.general.MaintenanceModule import MaintenanceModule
import kol.Error

class Test(unittest.TestCase):
     
    @classmethod
    def setUpClass(cls):
        cls._manager = MockChatManager()
        cls._manager.setProperty('debug', False)
        m = MaintenanceModule(cls._manager, "A", {})
        cls._manager.addModule(m)
        
    @classmethod
    def tearDownClass(cls):
        cls._manager.cleanup()
        
    def test(self):
        self.assertRaises(kol.Error.Error, self._manager.processCommand, 
                    {}, 'die', '10')
        self.assertEqual(len(self._manager.operations), 1, 
                         "No chat from MaintenanceModule")
        self.assertEqual(self._manager.operations[0]['type'], 'chat',
                         "Not a chat from MaintenanceModule")
        self.assertEqual(self._manager.operations[0]['text'],
                         "Coming online in 10 minutes.", "Bad message"
                         "from MaintenanceModule")
        
        self._manager.processCommand({}, 'restart', '')
        self.assertEqual(len(self._manager.operations), 2, 
                         "No event from MaintenanceModule")
        self.assertEqual(self._manager.operations[1]['type'], 'event',
                         "Not an event from MaintenanceModule")
        self.assertEqual(self._manager.operations[1]['event'].subject, 
                         "EventToSystem", 
                         "Not a system event from MaintenanceModule")
        self.assertEqual(self._manager.operations[1]['event'].data.subject, 
                         "RESTART", 
                         "Not a restart event from MaintenanceModule")

        self._manager.processCommand({}, 'raise_event', 'test1')
        self.assertEqual(len(self._manager.operations), 3, 
                         "No event from MaintenanceModule raise_event")
        self.assertEqual(self._manager.operations[2]['type'], 'event',
                         "Not an event from MaintenanceModule raise_event")
        self.assertEqual(self._manager.operations[2]['event'].subject, "test1", 
                         "Not a test1 event from MaintenanceModule")
        


if __name__ == '__main__':
    unittest.main()
    