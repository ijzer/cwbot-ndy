import kol.Error as Error
from kol.util import Report
import requests

import urllib
from cStringIO import StringIO

class GenericPartialRequest(object):
    """A generic request to a Kingdom of Loathing server. This request is 
    modified to stop streaming data after a regex matches. """

    def __init__(self, session, regexList, chunkSize):
        self.session = session
        self.regexList = regexList
        self.requestData = {}
        self.skipParseResponse = False
        self.chunkSize = chunkSize

    def doRequest(self):
        """
        Performs the request. This method will ensure that nightly maintenance is not occuring.
        In addition, this method will throw a NOT_LOGGED_IN error if the session thinks it is
        logged in when it actually isn't.
        """

        Report.debug("request", "Requesting %s" % self.url)

        self.response = self.session.opener.opener.post(self.url, self.requestData, stream=True)
        responseStr = StringIO()
        try:
            for chunk in self.response.iter_content(self.chunkSize):
                responseStr.write(chunk)
                s = responseStr.getvalue()
                
                matched = True
                for regex in self.regexList:
                    if not regex.search(s):
                        matched = False
                        break

                if matched:                    
                    break

            self.responseText = responseStr.getvalue()
            responseStr.close()
        finally:
            self.response.close()

        Report.debug("request", "Received response: %s" % self.url)
        Report.debug("request", "Response Text: %s" % self.responseText)

        if self.response.url.find("/maint.php") >= 0:
            self.session.isConnected = False
            raise Error.Error("Nightly maintenance in progress.", Error.NIGHTLY_MAINTENANCE)

        if self.response.url.find("/login.php") >= 0:
            if self.session.isConnected:
                self.session.isConnected = False
                raise Error.Error("You are no longer connected to the server.", Error.NOT_LOGGED_IN)

        # Allow for classes that extend GenericRequest to parse all of the data someone
        # would need from the response and then to place this data in self.responseData.
        self.responseData = {}
        if self.skipParseResponse == False and hasattr(self, "parseResponse"):
            self.parseResponse()
            if len(self.responseData) > 0:
                Report.debug("request", "Parsed response data: %s" % self.responseData)

        return self.responseData
