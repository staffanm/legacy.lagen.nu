#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import sys
import os
import time
import unittest
sys.path.append('..')
sys.path.append('.')
sys.path.append('../3rdparty')
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
        Robot.ClearCache(CacheLocation="testcache")
        data = Robot.GetExtended("http://lagen.nu/cgi-bin/unittest.py",
                                 RespectThrottling=False,
                                 RespectRobotsTxt=False,
                                 UseCache=True,
                                 CacheLocation="testcache")
        self.assertRaises(KeyError,data.info['x-cache'])
        data = Robot.GetExtended("http://lagen.nu/cgi-bin/unittest.py",
                                 RespectThrottling=False,
                                 RespectRobotsTxt=False,
                                 UseCache=True,
                                 CacheLocation="testcache")
        self.assertEquals(data.info['x-cache'], "abcd.txt")

        
if __name__ == "__main__":
    #suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.BasicTests.testGet")
    suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.Cache")
    unittest.TextTestRunner(verbosity=2).run(suite)
