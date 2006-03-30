import sys
import time
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
    def __init__(self,throttleDelay):
        self.throttleDelay = throttleDelay
        
    def http_request(self,request):
        time.sleep(5) # FIXME: throttle smarter
        return request


class CacheHandler(ClientCookie.BaseHandler):
    def __init__(self,cacheLocation):
        self.cacheLocation = cacheLocation
        
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

def GetExtended(url,
                respectRobotsTxt=True,
                useThrottling=True,
                throttleDelay=5,
                useCache=True,
                cacheLocation="cache"):
    handlers=[]
    if useCache:
        handlers.append(CacheHandler(cacheLocation))
    if respectRobotsTxt:
        handlers.append(ClientCookie.HTTPRobotRulesProcessor)
    if useThrottling:
        handlers.append(ThrottlingProcessor(throttleDelay))
    opener = ClientCookie.build_opener(*handlers)
    opener.addheaders = [('User-agent', 'Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)')]
    response = opener.open(url)
    return response

def Get(url,
        respectRobotsTxt=True,
        useThrottling=True,
        throttleDelay=5,
        useCache=True,
        cacheLocation="cache"):
    return GetExtended(url,
                       respectRobotsTxt,
                       useThrottling,
                       throttleDelay,
                       useCache,
                       cacheLocation).read()

def GetStore(url,
             urlPattern,
             filePattern,
             respectRobotsTxt,
             useThrottling,
             throttleDelay,
             useCache,
             cacheLocation):
    pass
