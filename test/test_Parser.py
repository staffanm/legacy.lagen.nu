#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
# standard lib modules
import os,random
from pprint import pprint

# my own modules
import Util

class FilenameError(Exception):
    pass

class TestParser:
    
    def Run(id, cls, dir, quiet=False, guiDiff=True):
        if not id:
            return RunAll(cld,dir)
        # find out filenames for this test
        files = [f for f in os.listdir(dir) if f.startswith(id)]
        infiles = {}
        keyfile = None
        for f in files:
            try:
                (id,direction,type,order,suffix) = f.split(".")
            except ValueError: # means there was some odd file (.bak file, most probably) in the dir
                continue
            if direction == "in":
                if type in infiles:
                    infiles[type].append("%s/%s" % (dir,f))
                else:
                    infiles[type] = ["%s/%s" % (dir,f)]
            elif direction == "out":
                keyfile = "%s/%s" % (dir,f)
            else:
                raise FilenameError("incorrect name (direction should be 'in' or 'out', not '%s'" % direction)
        pprint(infiles)
        p = cls()
        res = p.Parse('fakeid',infiles)
        attemptfile = "%08d.tmp" % int(random.uniform(0,99999999))
        fp = open(attemptfile,"w")
        fp.write(res)
        fp.close()
        Util.indentXmlFile(attemptfile)
        res = file(attemptfile).read()

        if os.path.exists(keyfile):
            Util.indentXmlFile(keyfile)
            answer = file(keyfile).read() # assum
            if res.strip() == answer.strip():
                print "Pass: %s" % filename
                return True
                os.unlink(attemptfile)
            else:
                print "FAIL: %s" % id
                if not quiet:
                    if guiDiff:
                        Util.runcmd('"C:/Program Files/WinMerge/WinMergeU.exe" %s %s' % (keyfile,attemptfile))
                    else:
                        from difflib import Differ
                        differ = Differ()
                        diff = list(differ.compare(res.splitlines(), answer.splitlines()))
                        print "\n".join(diff)+"\n"
                return False
        else:
            print "FAIL: %s (no keyfile '%s' exists)" % (id, keyfile)
            #if not quiet:
            #    print res
            return False
            
    Run = staticmethod(Run)
    
    def RunAll(cls,dir,quiet=True):
        res = []
        ids = {}
        for f in os.listdir(dir):
            (id,direction,type,order,suffix) = f.split(".")
            ids[id] = True
        for id in sorted(ids.keys()):
            res.append(TestParser.Run(id,cls,dir,quiet))
                
        succeeded = len([r for r in res if r])
        all       = len(res)
                        
        print "%s/%s" % (succeeded,all)
        return(succeeded,all)

    RunAll = staticmethod(RunAll)
