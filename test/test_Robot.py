#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import sys
import os
import time
import unittest
import md5
sys.path.append('..')
sys.path.append('.')
sys.path.append('../3rdparty')
sys.path.append('3rdparty')
from ClientCookie import RobotExclusionError
from urllib2 import HTTPError

import Robot
reload(Robot)

class Get(unittest.TestCase):
    def setUp(self):
        # print "Setting up things...."
        self.responseData = Robot.Get("http://lagen.nu/cgi-bin/unittest.py",
                                      useThrottling=False,
                                      useCache=False,
                                      respectRobotsTxt=False)

    def testGet(self):
        self.assertEqual(self.responseData[:27], "Sample for testing Robot.py")

    def testI18N(self):
        self.assertTrue("I18N: Iñtërnâtiônàlizætiøn" in self.responseData)
        
    def testUA(self):
        self.assertTrue("HTTP_USER_AGENT: Lagen.nu-bot" in self.responseData)

    def testStore(self):
        Robot.Store("http://lagen.nu/cgi-bin/unittest.py?key1=something&key2=and:other",
                   r'http://lagen.nu/cgi-bin/unittest.py\?key1=(\w+)&key2=(\w+):(\w+)',
                   r'\1/\3/\2.txt',
                   useThrottling=False,
                   useCache=False,
                   respectRobotsTxt=False)
        self.assert_(os.path.exists("something/other/and.txt"))
        fileContents = open("something/other/and.txt").read()
        self.assertEqual(fileContents[:27], "Sample for testing Robot.py")
        self.assertTrue("I18N: Iñtërnâtiônàlizætiøn" in fileContents)
        os.unlink("something/other/and.txt")

        

class Post(unittest.TestCase):
    def setUp(self):
        self.responseData = Robot.Post("http://lagen.nu/cgi-bin/unittest.py",
                                       {'key1':'val1','key2':'räksmörgås','key3':''},
                                       useThrottling=False,
                                       useCache=False,
                                       respectRobotsTxt=False)

    def testPost(self):
        self.assertTrue("key1=val1" in self.responseData)
        self.assertTrue("key2=r%E4ksm%F6rg%E5s" in self.responseData)
        self.assertTrue("key3=" in self.responseData)

        
class Throttling(unittest.TestCase):
    def testThrottle(self):
        Robot.Get("http://lagen.nu/cgi-bin/unittest.py",
                  useCache=False,
                  throttleDelay=2,
                  respectRobotsTxt=False)
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          useCache=False,
                          respectRobotsTxt=False,
                          throttleDelay=2)
        self.assert_('x-throttling' in resp.info())
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          useCache=False,
                          respectRobotsTxt=False,
                          throttleDelay=2)
        self.assert_('x-throttling' in resp.info())
        time.sleep(2)
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          useCache=False,
                          respectRobotsTxt=False,
                          throttleDelay=2)
        self.assert_('x-throttling' not in resp.info())
        

class RobotsTxt(unittest.TestCase):
    def testDisallowed(self):
        # can't seem to get self.asserRaises to work -- this is
        # a low-tech way of achieving same
        try:
            Robot.Get("http://lagen.nu/notallowed",
                      useCache=False,
                      useThrottling=False)
        except RobotExclusionError:
            return
        self.fail("RobotExclusionError never recieved")
            
    def testAllowed(self):
        try:
            Robot.Get("http://lagen.nu/notallowed",
                      userAgent="Somethingelse/0.1",
                      useCache=False,
                      useThrottling=False)
        except RobotExclusionError:
            self.fail("RobotExclusionError recieved even though the User-Agent should have been allowed")
        except HTTPError:
            # this is probably a 404 - that's OK
            return


class Cache(unittest.TestCase):

    def testCache(self):
        Robot.ClearCache(cacheLocation="testcache")

        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                         useThrottling=False,
                         respectRobotsTxt=False,
                         useCache=True,
                         cacheLocation="testcache")
        self.assert_('x-cache' not in resp.info())
        html1 = resp.read()
        check1 = md5.new(html1).hexdigest()

        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                         useThrottling=False,
                         respectRobotsTxt=False,
                         useCache=True,
                         cacheLocation="testcache")
        self.assert_('x-cache' in resp.info())
        html2 = resp.read()
        check2 = md5.new(html2).hexdigest()
        header2 = str(resp.info())
        headercheck2 = md5.new(header2).hexdigest()
        self.assertEqual(check1,check2)

        # third time to catch any possible "every other time" type errors
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                         useThrottling=False,
                         respectRobotsTxt=False,
                         useCache=True,
                         cacheLocation="testcache")
        self.assert_('x-cache' in resp.info())
        html3 = resp.read()
        check3 = md5.new(html3).hexdigest()
        header3 = str(resp.info())
        headercheck3 = md5.new(header3).hexdigest()
        self.assertEqual(check1,check3)
        self.assertEqual(headercheck2,headercheck3)
        
    def testPost(self):
        Robot.ClearCache(cacheLocation="testcache")

        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          method="POST",
                          useThrottling=False,
                          respectRobotsTxt=False,
                          useCache=True,
                          cacheLocation="testcache")
        self.assert_('x-cache' not in resp.info())

        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          method="POST",
                          useThrottling=False,
                          respectRobotsTxt=False,
                          useCache=True,
                          cacheLocation="testcache")
        self.assert_('x-cache' not in resp.info())

class Combined(unittest.TestCase):
    def testThrottleAndCache(self):
        Robot.ClearCache(cacheLocation="testcache")
        Robot.Get("http://lagen.nu/cgi-bin/unittest.py",
                  useThrottling=True,
                  useCache=True,
                  cacheLocation="testcache",
                  respectRobotsTxt=False)
        print "initial GET finished"
        # the second request should trigger the cache, thereby bypassing
        # the throttling mechanism alltogether
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                         useThrottling=True,
                         useCache=True,
                         cacheLocation="testcache",
                         respectRobotsTxt=False)
        self.assert_('x-cache' in resp.info())
        self.assert_('x-throttling' not in resp.info())
    
    def testThrottleAndCacheMiss(self):
        Robot.ClearCache(cacheLocation="testcache")
        Robot.ClearThrottleTimeouts()
        Robot.Get("http://lagen.nu/cgi-bin/unittest.py",
                  useThrottling=True,
                  useCache=True,
                  cacheLocation="testcache",
                  respectRobotsTxt=False)
        print "initial GET finished"
        Robot.ClearCache(cacheLocation="testcache")
        # the second request should trigger the throttling, but not the cache (now that we've cleared it)
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                         useThrottling=True,
                         useCache=True,
                         cacheLocation="testcache",
                         respectRobotsTxt=False)
        self.assert_('x-cache' not in resp.info())
        self.assert_('x-throttling' in resp.info())
        
    
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot")
    # suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.Combined.testThrottleAndCacheMiss")
    # suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.Throttling.testThrottle")
    unittest.TextTestRunner(verbosity=2).run(suite)
