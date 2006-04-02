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
sys.path.append('3rdparty')
sys.path.append('../3rdparty')
import ClientCookie

import StringIO

__version__ = (0,1)
__author__ = "Staffan Malmgren <staffan@tomtebo.org>"


class ThrottlingProcessor(ClientCookie.BaseHandler):
    """Prevents overloading the remote web server by delaying requests.

    Causes subsequent requests to the same web server to be delayed
    a specific amount of seconds. The first request to the server
    always gets made immediately"""
    __shared_state = {}
    def __init__(self,throttleDelay=5):
        """The number of seconds to wait between subsequent requests"""
        # Using the Borg design pattern to achieve shared state between object instances:
        self.__dict__ = self.__shared_state
        self.throttleDelay = throttleDelay
        if not hasattr(self,'lastRequestTime'):
            self.lastRequestTime = {}
        
    def http_request(self,request):
        currentTime = time.time()
        if ((request.host in self.lastRequestTime) and
            (time.time() - self.lastRequestTime[request.host] < self.throttleDelay)):
            self.throttleTime = (self.throttleDelay -
                                 (currentTime - self.lastRequestTime[request.host]))
            # print "Sleeping for %s seconds" % self.throttleTime
            time.sleep(self.throttleTime)

        self.lastRequestTime[request.host] = currentTime
        return request

    def http_response(self,request,response):
        if hasattr(self,'throttleTime'):
            response.info().addheader("x-throttling", "%s seconds" % self.throttleTime)
            del(self.throttleTime)
        return response

class CacheHandler(ClientCookie.BaseHandler):
    """Stores responses in a persistant on-disk cache.

    If a subsequent GET request is made for the same URL, the stored
    response is returned, saving time, resources and bandwith"""
    def __init__(self,cacheLocation):
        """The location of the cache directory"""
        self.cacheLocation = cacheLocation
        
    def default_open(self,request):
        print "CacheProcessor called"
        import mimetools
        msg = mimetools.Message(
            StringIO.StringIO("Server: Fake cache\r\n\r\n"))

        return CachedResponse(200, "OK", msg, "This is the response body", "http://fakeurl.com/")

class CachedResponse(StringIO.StringIO):
    """An urllib2.response-like object for cached responses.

    To determine wheter a response is cached or coming directly from
    the network, check the X-cache header rather than the object type."""
    
    def __init__(self, code, msg, headers, data, url=None):
        StringIO.StringIO.__init__(self, data)
        self.code, self.msg, self.headers, self.url = code, msg, headers, url
    def info(self):
        return self.headers
    def geturl(self):
        return self.url

def Open(url,
         method="GET",
         parameters={},
         respectRobotsTxt=True,
         useThrottling=True,
         throttleDelay=5,
         useCache=True,
         cacheLocation="cache"):
    """Returns the contents of a URL as a file-like object.

    To find out more about the response, use the .info() and .geturl() methods.
    """
    handlers=[]
    if useCache:
        handlers.append(CacheHandler(cacheLocation))
    if respectRobotsTxt:
        handlers.append(ClientCookie.HTTPRobotRulesProcessor)
    if useThrottling:
        handlers.append(ThrottlingProcessor(throttleDelay))
    opener = ClientCookie.build_opener(*handlers)
    opener.addheaders = [('User-agent', 'Lagen.nu-bot/0.1 (http://lagen.nu/om/bot.html)')]
    ### here we need to build smart retry functionality
    if (method == "POST"):
        data = urllib.urlencode(parameters)
        #print "POSTing data: %s" % data
        response = opener.open(url,data)
    else:
        response = opener.open(url)
    
    return response

def Get(url,
        respectRobotsTxt=True,
        useThrottling=True,
        throttleDelay=5,
        useCache=True,
        cacheLocation="cache"):
    """Returns the content of a given URL."""
    return Open(url,
                "GET",
                {},
                respectRobotsTxt,
                useThrottling,
                throttleDelay,
                useCache,
                cacheLocation).read()

def Post(url,
         parameters,
         respectRobotsTxt=True,
         useThrottling=True,
         throttleDelay=5,
         useCache=True,
         cacheLocation="cache"):
    """Returns the content of a given URL."""
    return Open(url,
                "POST",
                parameters,
                respectRobotsTxt,
                useThrottling,
                throttleDelay,
                useCache,
                cacheLocation).read()

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
          cacheLocation="cache"):
    """Fetch the contents of a given URL, and store it on disk.

    The urlPattern is a regexp that should match the URL being
    used. It should contain at least one paranthesided expression. The
    filePattern is a template that is used with the matches from the
    urlPattern regexp, eg:

    url         =  'http://lagen.nu/1960:729'
    urlPattern  = r'http://lagen.nu/(\d+):(\d+)$'
    filePattern = r'downloaded/\1/\2.html'

    should create a file called 'downloaded/1960/729.html'.

    This method only handles GET requests -- for POSTS you need to
    roll your own using Open()
    """
    # print "        url: %s" % url
    # print " urlPattern: %s" % urlPattern
    # print "filePattern: %s" % filePattern
    pattern = re.compile(urlPattern)
    assert(pattern.match(url))
    filename = pattern.sub(filePattern,url)
    # print "Let's store stuff as %s" % filename
    _mkdir(os.path.dirname(filename))
    fp = open(filename,"w")
    resp = Open(url,"GET",{}, respectRobotsTxt, useThrottling, throttleDelay,
                useCache, cacheLocation)
    fp.write(resp.read())
    fp.close()
        
    
    
