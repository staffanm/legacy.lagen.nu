import sys
sys.path.append('3rdparty')
import ClientCookie

import StringIO
# the robot should
# * throttle traffic
# * respect robots.txt
# * handle cookies
# * automatically cache everything (incl index pages), based on URL,
#   POST variables and maybe cookies, and check this cache before
#   doing actual HTTP requests
#
# All of the above should be optional
#
# * Be able to save things using a configurable naming scheme
#   eg URL  http://somesite.com/data.cgi?year=%s&id=%s
#      FILE documents/%s/%s.html

__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"


#class Robot:
#
#    # Using a Borg design pattern (similar to a Singleton, but simpler
#    # implementation, at the expense of more objects for the GC to
#    # keep track of). Implementation from
#    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66531
#    __shared_state = {}
#    def __init__(self):
#        self.__dict__ = self.__shared_state
#        # create a urllib object
#        # init cookie and robots.txt stuff
#        

class ThrottlingProcessor(ClientCookie.BaseHandler):
    def http_request(self,request):
        print "ThrottlingProcessor called"
        print dir(request)
        return request

class CacheHandler(ClientCookie.BaseHandler):
    def default_open(self,request):
        print "CacheProcessor called"
        import mimetools
        msg = mimetools.Message(
            StringIO.StringIO("Server: Fake cache\r\n\r\n"))

        return CachedResponse(200, "OK", msg, "This is the response body", "http://fakeurl.com/")

class CachedResponse(StringIO.StringIO):
    def __init__(self, code, msg, headers, data, url=None):
        StringIO.StringIO.__init__(self, data)
        self.code, self.msg, self.headers, self.url = code, msg, headers, url
    def info(self):
        return self.headers
    def geturl(self):
        return self.url
    
def Get(url,method="GET",parameters={},RespectRobotsTxt=True,RespectThrottling=True,UseCache=True):
    # check cache
    # check robots.txt
    # check throttling timeout
    # construct the request, stream
        
    print "%sting %s" % (method, url)

    handlers = []

    if UseCache:
        handlers.append(CacheHandler)

    if RespectRobotsTxt:
        handlers.append(ClientCookie.HTTPRobotRulesProcessor)

    if RespectThrottling:
        handlers.append(ThrottlingProcessor)

    opener = ClientCookie.build_opener(*handlers)

    response = opener.open(url)
    print response.info()
    print response.read(100)
    


def GetStore(url,method="GET", parameters={}):
    pass
