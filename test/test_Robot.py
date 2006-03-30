#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import sys
sys.path.append('..')
import Robot
import unittest
class Get(unittest.TestCase):
    def setUp(self):
        self.responseData = Robot.Get("http://lagen.nu/cgi-bin/unittest.py",
                                      useThrottling=False,
                                      useCache=False)

    def testGet(self):
        self.assertEqual(self.responseData[:27], "Sample for testing Robot.py")

    def testI18N(self):
        self.assertTrue("I18N: Iñtërnâtiônàlizætiøn" in self.responseData)
        
    def testUA(self):
        self.assertTrue("HTTP_USER_AGENT: Lagen.nu-bot" in self.responseData)

    def testStore(self):
        self.Store("http://lagen.nu/cgi-bin/unittest.py?key1=something&key2=and:other",
                   "key1=\w+&key2=\w+:\w+",
                   "\1-\3-\2.txt",
                   useThrottling=False,
                   useCache=False,
                   respectRobotsTxt=False)
        self.assertExists("something-other-and.txt")
        

class Post(unittest.TestCase):
    def setUp(self):
        self.responseData = Robot.Post("http://lagen.nu/cgi-bin/unittest.py",
                                       {'key1':'val1','key2':'räksmörgås','key3':''},
                                       useThrottling=False,
                                       useCache=False,
                                       respectRobotsTxt=False)
        
class Throttling(unittest.TestCase):
    def testThrottle(self):
        Robot.Get("http://lagen.nu/cgi-bin/unittest.py")
        resp = Robot.GetExtended("http://lagen.nu/cgi-bin/unittest.py")
        self.assertEquals(resp.info().getheader('X-throttling','yes'))

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
    suite = unittest.defaultTestLoader.loadTestsFromName("test_Robot.BasicTests")
    unittest.TextTestRunner(verbosity=1).run(suite)
