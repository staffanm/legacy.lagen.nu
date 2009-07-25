# # run a specific test of a specific test class
# python LegalRef RunTest Parse test/data/LegalRef/sfs-foo.txt # test specific
# 
# # run all tests for a specific test class
# python LegalRef RunTest Parse
# 
# # run all tests for all test classes in a module
# python LegalRef RunTest
# 
# # run all tests for all modules - this should also run
# # unittest-based tests:
# python Manager RunTest
# 
# # another example
# python SFS Test Template test/data/SFS/some-objects.dat
# 
# # use like so:
# class SFSManager(LegalSource.Manager, FilebasedTester):
#
#     testparameters = {'Parse': {'dir': 'test/data/SFS',
#                                 'testsuffix': '.txt',
#                                 'answersuffix': '.xml'},
#                       'Templ': {'dir': 'test/data/SFSTempl',
#                                 'testsuffix': '.xml',
#                                 'answersuffix', '.xht2'}}
import os
import glob
import sys
import re
import traceback
import codecs
from difflib import Differ
import locale
locale.setlocale(locale.LC_ALL,'') 

import Util      

class FilebasedTester:
    TEST_NOTIMPLEMENTED = "N"
    TEST_FAILED = "F"
    TEST_EXCEPTION = "E"
    TEST_OK = "."
    def RunTest(self, method=None, file=None):
        if file:
            if os.path.exists(file):
                return self.__run_single_test(method, file)
            else:
                files = glob.glob(file)
                if not files:
                    print "No testfile named %s" % file
                else:
                    for f in files:
                        self.__run_single_test(method, file)
                    return True
                    
        elif method:
            return self.__run_single_testclass(method)
        else:
            return self.__run_all_testclasses()

    def __run_all_testclasses(self):
        all_cnt = 0
        all_fail = 0
        for method in self.testparams.keys():
            sys.stdout.write("%s.%s:" % (self.__class__.__name__,method))
            (fail, cnt) = self.__run_single_testclass(method, True)
            all_cnt += cnt
            all_fail += fail
        sys.stdout.write("%s: %s tests of %s passed\n" % (self.__class__.__name__,all_cnt-all_fail, all_cnt))
        if cnt > 0 and fail == 0:
            sys.stdout.write("AWESOME!")
        return (all_fail,all_cnt)
                         
            
    def __run_single_testclass(self, method, quiet=False):
        cnt = 0
        failed = []
        for file in sorted(list(Util.listDirs(self.testparams[method]['dir'],
                                              self.testparams[method]['testext']))):
            res = self.__run_single_test(method, file, True)
            cnt += 1
            if res != self.TEST_OK:
                failed.append(file)
            sys.stdout.write(res)
        sys.stdout.write(" %s/%s\n" % (cnt-len(failed), cnt))
        if not quiet and len(failed) > 0:
            sys.stdout.write("Failed tests:\n")
            sys.stdout.write("\n".join(failed))
            sys.stdout.write("\n")
        return (len(failed), cnt)

    def __run_single_test(self, method, testfile, quiet=False):
        # quiet = False
        if 'testencoding' in self.testparams[method]:
            encoding=self.testparams[method]['testencoding']
        else:
            encoding = 'iso-8859-1'
        if 'answerext' in self.testparams[method]:
            answerfile = testfile.replace(self.testparams[method]['testext'],
                                          self.testparams[method]['answerext'])
            #print "reading %s as %s" % (testfile, encoding)
            testdata = codecs.open(testfile,encoding=encoding).read()
            if not os.path.exists(answerfile):
                answer = ""
            else:
                if 'answerencoding' in self.testparams[method]:
                    ansenc=self.testparams[method]['answerencoding']
                else:
                    ansenc=encoding
                #print "reading %s as %s" % (testfile, ansenc)
                answer = codecs.open(answerfile,encoding=ansenc).read()
        else:
            # all = open(testfile).read()
            all = codecs.open(testfile,encoding=encoding).read()
            parts = re.split('\r?\n\r?\n',all,1)
            if len(parts) == 1:
                testdata = all
                answer = u''
            else:
                (testdata, answer) = parts
            
        methodname = "Test%s" % method
        assert methodname in dir(self)
        callable_method = getattr(self,methodname)
	try:
            res = callable_method(testdata)
            if not answer:
                if not quiet:
                    print "NOT IMPLEMENTED: %s" % testfile
                    print "----------------------------------------"
                    print "GOT:"
                    print res
                    print "----------------------------------------"
                return self.TEST_NOTIMPLEMENTED

            res = res.strip().replace("\r\n","\n")
            answer = answer.strip().replace("\r\n","\n")
            if res != answer:
                if not quiet:
                    difflines = list(Differ().compare(answer.split('\n'),res.split('\n')))
                    diff = '\n'.join(difflines)
                    print "FAILED: %s" % testfile
                    print "----------------------------------------"
                    sys.stdout.write(diff+"\n")
                    print "----------------------------------------"
                return self.TEST_FAILED
            else:
                if not quiet:
                    print "OK: %s" % testfile
                return self.TEST_OK
        except Exception:
            tb = sys.exc_info()[2]
            formatted_tb = [x.decode('iso-8859-1') for x in traceback.format_tb(sys.exc_info()[2])]
            if not quiet:
                sys.stdout.write (u" EXCEPTION:\nType: %s\nValue: %s\nTraceback:\n %s" %
                       (sys.exc_info()[0],
                        sys.exc_info()[1],
                        u''.join(formatted_tb)))

            return self.TEST_EXCEPTION
    
