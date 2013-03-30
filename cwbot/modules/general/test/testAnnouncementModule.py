import unittest
from cwbot.modules.test.MockChatManager import MockChatManager
from cwbot.modules.general.AnnouncementModule import AnnouncementModule

class Test(unittest.TestCase):
     
    @classmethod
    def setUpClass(cls):
        cls._manager = MockChatManager()
        cls._manager.setProperty('debug', False)
        m = AnnouncementModule(cls._manager, "A", {'clan': 
            {'event1': 'E%arg%', 'event2': 'E2'}})
        cls._manager.addModule(m)
        
    @classmethod
    def tearDownClass(cls):
        cls._manager.cleanup()
        
    def test(self):
        self._manager.raiseSystemEvent("event2")
        self.assertEqual(len(self._manager.operations), 1, 
                         "Event2 not detected")
        self.assertEqual(self._manager.operations[0]['type'], 'chat', 
                         "Event2 operation non-chat")
        self.assertEqual(self._manager.operations[0]['channel'], 'clan', 
                         "Event2 chat non-clan")
        self.assertEqual(self._manager.operations[0]['text'], "E2", 
                         "Event2 chat wrong text")
        self._manager.raiseSystemEvent("event1", data={'args': 'DATA'})
        self.assertEqual(len(self._manager.operations), 2, 
                         "Event1 not detected")
        self.assertEqual(self._manager.operations[1]['type'], 'chat', 
                         "Event1 operation non-chat")
        self.assertEqual(self._manager.operations[1]['channel'], 'clan', 
                         "Event1 chat non-clan")
        self.assertEqual(self._manager.operations[1]['text'], "EDATA", 
                         "Event1 bad substitution")
        self._manager.raiseSystemEvent("event3")
        self.assertEqual(len(self._manager.operations), 2, 
                         "Event3 should not be detected")

if __name__ == '__main__':
    unittest.main()