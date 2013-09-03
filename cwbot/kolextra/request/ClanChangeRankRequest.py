from kol.request.GenericRequest import GenericRequest

class ClanChangeRankRequest(GenericRequest):
    def __init__(self, session, userId, title, level=None):
        super(ClanChangeRankRequest, self).__init__(session)
        self.url = session.serverURL + "clan_members.php"
        self.requestData['pwd'] = session.pwd
        self.requestData['action'] = 'modify'
        self.requestData['begin'] = '1'
        self.requestData['pids[]'] = userId
        if level is not None:
            self.requestData['level%s' % userId] = str(level)
        self.requestData['title%s' % userId] = str(title)
