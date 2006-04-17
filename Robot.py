"""Fetch content from websites in a simple, efficient fashion.

This module wraps urllib2 and ClientCookie in easy-to-use wrapper, and
adds support for Request throttling, caching and robots.txt
support. It contains only static methods, no Robot object is ever
created."""

import sys
import time
import re
import os
import urllib # for urllib.urlencode
import urllib2
import httplib
import md5
# import mimetools

sys.path.append('3rdparty')
sys.path.append('../3rdparty')
import ClientCookie

import StringIO

__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"


class ThrottlingProcessor(urllib2.BaseHandler):
    """Prevents overloading the remote web server by delaying requests.

    Causes subsequent requests to the same web server to be delayed
    a specific amount of seconds. The first request to the server
    always gets made immediately"""
    __shared_state = {}
    def __init__(self,throttleDelay=5):
        """The number of seconds to wait between subsequent requests"""
        # Using the Borg design pattern to achieve shared state
        # between object instances:
        self.__dict__ = self.__shared_state
        self.throttleDelay = throttleDelay
        if not hasattr(self,'lastRequestTime'):
            self.lastRequestTime = {}
        
    def default_open(self,request):
        currentTime = time.time()
        if ((request.host in self.lastRequestTime) and
            (time.time() - self.lastRequestTime[request.host] < self.throttleDelay)):
            self.throttleTime = (self.throttleDelay -
                                 (currentTime - self.lastRequestTime[request.host]))
            print "ThrottlingProcessor: Sleeping for %s seconds" % self.throttleTime
            time.sleep(self.throttleTime)
        self.lastRequestTime[request.host] = currentTime

        return None

    def http_response(self,request,response):
        if hasattr(self,'throttleTime'):
            response.info().addheader("x-throttling", "%s seconds" % self.throttleTime)
            del(self.throttleTime)
        return response

class CacheHandler(urllib2.BaseHandler):
    """Stores responses in a persistant on-disk cache.

    If a subsequent GET request is made for the same URL, the stored
    response is returned, saving time, resources and bandwith"""
    def __init__(self,cacheLocation):
        """The location of the cache directory"""
        self.cacheLocation = cacheLocation
        if not os.path.exists(self.cacheLocation):
            os.mkdir(self.cacheLocation)
            
    def default_open(self,request):
        if ((request.get_method() == "GET") and 
            (CachedResponse.ExistsInCache(self.cacheLocation, request.get_full_url()))):
            print "CacheHandler: Returning CACHED response for %s" % request.get_full_url()
            return CachedResponse(self.cacheLocation, request.get_full_url(), setCacheHeader=True)	
        else:
            return None # let the next handler try to handle the request

    def http_response(self, request, response):
        if request.get_method() == "GET":
            if 'x-cache' not in response.info():
                CachedResponse.StoreInCache(self.cacheLocation, request.get_full_url(), response)
                return CachedResponse(self.cacheLocation, request.get_full_url(), setCacheHeader=False)
            else:
                return CachedResponse(self.cacheLocation, request.get_full_url(), setCacheHeader=True)
        else:
            return response
    
class CachedResponse(StringIO.StringIO):
    """An urllib2.response-like object for cached responses.

    To determine wheter a response is cached or coming directly from
    the network, check the X-cache header rather than the object type."""
    import md5
    
    def ExistsInCache(cacheLocation, url):
        hash = md5.new(url).hexdigest()
        return (os.path.exists(cacheLocation + "/" + hash + ".headers") and 
                os.path.exists(cacheLocation + "/" + hash + ".body"))
    ExistsInCache = staticmethod(ExistsInCache)

    def StoreInCache(cacheLocation, url, response):
        hash = md5.new(url).hexdigest()
        f = open(cacheLocation + "/" + hash + ".headers", "w")
        headers = str(response.info())
        f.write(headers)
        f.close()
        f = open(cacheLocation + "/" + hash + ".body", "w")
        f.write(response.read())
        f.close()
    StoreInCache = staticmethod(StoreInCache)
    
    def __init__(self, cacheLocation,url,setCacheHeader=True):
        self.cacheLocation = cacheLocation
        hash = md5.new(url).hexdigest()
        StringIO.StringIO.__init__(self, file(self.cacheLocation + "/" + hash+".body").read())
        self.url     = url
        self.code    = 200
        self.msg     = "OK"
        headerbuf = file(self.cacheLocation + "/" + hash+".headers").read()
        if setCacheHeader:
            headerbuf += "x-cache: %s/%s\r\n" % (self.cacheLocation,hash)
        self.headers = httplib.HTTPMessage(StringIO.StringIO(headerbuf))

    def info(self):
        return self.headers
    def geturl(self):
        return self.url


# ensure that the same instance of HTTPRobotRulesProcessor is reused
# -- otherwise the robots.txt file is requested for each ordinary
# request, wheter cached or not -- not that friendly
robotRulesProcessor = ClientCookie.HTTPRobotRulesProcessor()
def Open(url,
         method="GET",
         parameters={},
         respectRobotsTxt=True,
         useThrottling=True,
         throttleDelay=5,
         useCache=True,
         cacheLocation="cache",
         userAgent="Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)"):
    """Returns the contents of a URL as a file-like object.

    To find out more about the response, use the .info() and .geturl() methods.
    """
    handlers=[]
    if useCache:
        handlers.append(CacheHandler(cacheLocation))
    if respectRobotsTxt:
        handlers.append(robotRulesProcessor)
    if useThrottling:
        handlers.append(ThrottlingProcessor(throttleDelay))
    
    # ClientCookie is a extended wrapper around urllib2 that adds 
    # automatic cookie handling and other stuff. It also provides the 
    # HTTPRobotRulesProcessor. However, the other handlers (CacheHandlers,
    # and ThrottlingProcessor) can be used with vanilla urllib2 as well.
    opener = ClientCookie.build_opener(*handlers)
    # opener = urllib2.build_opener(*handlers)
    # 
    opener.addheaders = [('User-agent', userAgent)]
    retries = 3
    while retries > 0:
        try:
            if (method == "POST"):
                data = urllib.urlencode(parameters)
                #print "POSTing data: %s" % data
                response = opener.open(url,data)
            else:
                response = opener.open(url)
            return response
        except urllib2.URLError:
            retries = retries - 1
            print "WARNING: Robot.Open got a URLError, %s retries left" % retries
            


def Get(url,
        respectRobotsTxt=True,
        useThrottling=True,
        throttleDelay=5,
        useCache=True,
        cacheLocation="cache",
        userAgent="Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)"):
    """Returns the content of a given URL."""
    return Open(url,
                "GET",
                {},
                respectRobotsTxt,
                useThrottling,
                throttleDelay,
                useCache,
                cacheLocation,
                userAgent).read()

def Post(url,
         parameters,
         respectRobotsTxt=True,
         useThrottling=True,
         throttleDelay=5,
         useCache=True,
         cacheLocation="cache",
         userAgent="Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)"):
    """Returns the content of a given URL."""
    return Open(url,
                "POST",
                parameters,
                respectRobotsTxt,
                useThrottling,
                throttleDelay,
                useCache,
                cacheLocation,
                userAgent).read()

# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/82465
def _mkdir(newdir):
    """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not os.path.isdir(head):
            _mkdir(head)
        #print "_mkdir %s" % repr(newdir)
        if tail:
            os.mkdir(newdir)

def Store(url,
          urlPattern,
          filePattern,
          respectRobotsTxt=True,
          useThrottling=True,
          throttleDelay=5,
          useCache=True,
          cacheLocation="cache",
          userAgent="Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)"):
    """Fetch the contents of a given URL, and store it on disk.

    The urlPattern is a regexp that should match the URL being
    used. It should contain at least one paranthesided expression. The
    filePattern is a template that is used with the matches from the
    urlPattern regexp, eg:

    url         =  'http://lagen.nu/1960:729'
    urlPattern  = r'http://lagen.nu/(\d+):(\d+)$'
    filePattern = r'downloaded/\1/\2.html'

    should create a file called 'downloaded/1960/729.html'.

    If urlPattern is None, filePattern is treated as a normal filename.
    
    If both urlPattern and filePattern is Null, the last part of the URL path
    is used as a filename (and if that part is not usable as a filename by
    containing chars like : and &, all hell breaks loose)

    This method only handles GET requests -- for POSTS you need to
    roll your own using Open()
    """
    # print "        url: %s" % url
    # print " urlPattern: %s" % urlPattern
    # print "filePattern: %s" % filePattern
    if urlPattern == None:
        if filePattern == None:
            filename = url.split('/')[-1]
        else:
            filename = filePattern
    else:
        pattern = re.compile(urlPattern)
        assert(pattern.match(url))
        filename = pattern.sub(filePattern,url)
        
    # print "Let's store stuff as %s" % filename
    resp = Open(url,"GET",{}, respectRobotsTxt, useThrottling, throttleDelay,
                useCache, cacheLocation, userAgent)
    _mkdir(os.path.dirname(filename))
    fp = open(filename,"w")
    fp.write(resp.read())
    fp.close()
        
def ClearCache(cacheLocation="cache"):
    # print "Clearing cache..."
    if os.path.exists(cacheLocation):
        for f in os.listdir(cacheLocation):
            os.unlink("%s/%s" % (cacheLocation, f))
        # os.unlink(cacheLocation)

def ClearThrottleTimeouts():
    t = ThrottlingProcessor()
    t.lastRequestTime.clear()



    
