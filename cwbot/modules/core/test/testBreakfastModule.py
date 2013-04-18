import unittest
from cwbot.modules.test.MockChatManager import MockChatManager
from cwbot.modules.general.BreakfastModule import BreakfastModule

requests = []
def doRequest(request, *args, **kwargs):
    requests.append(request)
    return {'meat': 0}

class Test(unittest.TestCase):

        
    @classmethod
    def setUpClass(cls):
        cls._manager = MockChatManager()
        cls._manager.setProperty('debug', False)
        m = BreakfastModule(cls._manager, "A", {})
        # override tryRequest to not actually try requests
        setattr(m, 'tryRequest', doRequest) 
        cls._manager.addModule(m)

        
    @classmethod
    def tearDownClass(cls):
        cls._manager.cleanup()

        
    def test(self):
        self._manager.raiseSystemEvent("startup")
        self._manager.waitForHeartbeat(2)
        self.assertGreaterEqual(len(requests), 1, 
                                "No requests from BreakfastModule")


if __name__ == '__main__':
    unittest.main()