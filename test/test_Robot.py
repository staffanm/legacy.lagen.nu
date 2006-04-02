#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import sys
import os
import time
import unittest
sys.path.append('..')
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
#        Robot.Store("http://lagen.nu/1960:729",
#                    r"http://lagen.nu/(\d+):(\d+)",
#                    r"store/\1/\2.html")
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
                  throttleDelay=5,
                  respectRobotsTxt=False)
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          useCache=False,
                          respectRobotsTxt=False,
                          throttleDelay=5)
        self.assert_('x-throttling' in resp.info())
        time.sleep(6)
        resp = Robot.Open("http://lagen.nu/cgi-bin/unittest.py",
                          useCache=False,
                          respectRobotsTxt=False,
                          throttleDelay=5)
        self.assert_('x-throttling' not in resp.info())
        

class RobotsTxt(unittest.TestCase):
    def textRobotTxt(self):
        self.assertRaises(RobotsTxtError,Robot.Get("http://lagen.nu/notallowed"))
        self.assertSuccess(RobotsTxt,Robot.Get("http://lagen.nu/notallowed",
                                               UserAgent="Somethingelse/0.1"))

class Cache(unittest.TestCase):

    def testCache(self):
        Robot.ClearCache(CacheLocation="testcache")
        data = Robot.GetExtended("http://lagen.nu/cgi-bin/unittest.py",
                                 RespectThrottling=False,
                                 RespectRobotsTxt=False,
                                 UseCache=True,
                                 CacheLocation="testcache")
        self.assertRaises(KeyError,data.info['X-cache'])
        data = Robot.GetExtended("http://lagen.nu/cgi-bin/unittest.py",
                                 RespectThrottling=False,
                                 RespectRobotsTxt=False,
                                 UseCache=True,
                                 CacheLocation="testcache")
        self.assertEquals(data.info['X-cache'], "abcd.txt")

        
if __name__ == "__main__":
    #suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.BasicTests.testGet")
    suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.Throttling")
    unittest.TextTestRunner(verbosity=2).run(suite)
