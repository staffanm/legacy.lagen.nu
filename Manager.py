#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""High-level classes that coordinates various Downloaders, Parsers
and Generators (Renderers?) to create the static HTML files and other stuff"""

from datetime import datetime
import codecs
import inspect
import os,sys
import re
import shutil
import time
import logging
from tempfile import mktemp
import xml.etree.cElementTree as ET

# 3rd party modules
from configobj import ConfigObj
from genshi.template import TemplateLoader
from mechanize import Browser, LinkNotFoundError

# my libs
from DispatchMixin import DispatchMixin
import LegalSource
import Util

log = logging.getLogger('mgr')
if not os.path.sep in __file__:
    __scriptdir__ = os.getcwd()
else:
    __scriptdir__ = os.path.dirname(__file__)

MW_NS = "{http://www.mediawiki.org/xml/export-0.3/}"
class Manager:
    def __init__(self):
        self.config = ConfigObj(__scriptdir__ + "/conf.ini")
        self.baseDir = self.config['datadir']
    
    def _pairListToDict(self,pairlist):
        """maybe this could be done w/ list comprehensions (can they
        return an dict?)"""
        a = {}
        for p in pairlist:
            a[p[0]] = p[1]
        return a
    
    def _findModules(self):
        res = {}
        for f in [f for f in os.listdir(".") if f.endswith(".py") and f != "sitecustomize.py"]:
            modulename = inspect.getmodulename(f)
            # print "importing %s from %s" % (modulename,f)
            m = __import__(modulename,globals(),locals(),[])
            c = self._findManager(m)
            if c:
                if '__shortdesc__' in dir(m):
                    res[modulename] = m.__shortdesc__
                else:
                    res[modulename] = '<no description>'
        return res

    def _findTester(self,module):
        import FilebasedTester
        classes = self._pairListToDict(inspect.getmembers(module,inspect.isclass))
        for classname in classes.keys():
            if (FilebasedTester.FilebasedTester in inspect.getmro(classes[classname])
                and (str(classes[classname]).startswith(module.__name__)
                     or classname.startswith(module.__name__))):
                return classes[classname]
        
    def _findManager(self,module):
        if module.__name__ == u'LegalSource':
            return # specialcase: LegalSource has a LegalSource.Manager class, but should not be directly instansiated
        import LegalSource
        classes = self._pairListToDict(inspect.getmembers(module,inspect.isclass))
        #print "Finding mangager of mudle %s" % module
        for classname in classes.keys():
            #print "Checking %s (%s)" % (classname, module.__name__)
            #print repr(inspect.getmro(classes[classname]))
            if (LegalSource.Manager in inspect.getmro(classes[classname])
                and classname.startswith(module.__name__)):
                # print "found a match!"
                return classes[classname]

    def _doTest(self,module):
        action = 'RunTest'
        all_fail = 0
        all_cnt = 0
        if module == 'all':
            modules = self._findModules().keys()
            modules.append('LegalRef')
            modules.append('LegalURI')
        else:
            modules = (module,)
        for m in modules:
            mod = __import__(m, globals(), locals(), [])
            testClass = self._findTester(mod)
            if testClass:
                tester = testClass()
                if hasattr(tester,action):
                    #log.info(u'%s: calling %s' % (m,action))
                    method = getattr(tester,action)
                    (fail,cnt) = method()
                    all_fail += fail
                    all_cnt  += cnt
                else:
                    log.warning(u"Module %s's tester has no %s action" % (m,action))
                    # pass
            else:
                pass
                # log.warning(u"Class %s has no test module" % m)
        print "Total: %s of %s tests succeeded" % (all_cnt-all_fail, all_cnt)
                            
    def _doAction(self,action,module):
        if module == 'all':
            modules = []
            for m in self._findModules().keys():
                # avoid running non-finished modules by only doing those
                # that have a config file section
                if m.lower() in self.config:
                    modules.append(m)

        else:
            modules = (module,)
        for m in modules:
            start = time.time()
            mod = __import__(m, globals(), locals(), [])
            mgrClass = self._findManager(mod)
                
            if mgrClass:
                mgr = mgrClass()
                if hasattr(mgr,action):
                    log.info(u'%s: calling %s' % (m,action))
                    method = getattr(mgr,action)
                    method()
                else:
                    log.warning(u"Module %s's manager has no %s action" % (m,action))
            else:
                print "Module %s has no Manager class" % m
            log.info(u'%s: %s finished in %s' % (m,action,time.strftime("%H:%M:%S", time.gmtime(time.time()-start))))
            
    def _doActionFor(self,action,module,docids):
        mod = __import__(module, globals(), locals(), [])
        mgrClass = self._findManager(mod)
        if mgrClass:
            mgr = mgrClass()
            if hasattr(mgr,action):
                for docid in docids:
                    if docid:
                        method = getattr(mgr,action)
                        method(docid)
            else:
                log.warning(u"Module %s's manager has no %s action" % (m,action))
        else:
            print "Module %s has no Manager class" % m

    def _doManagerActionFor(self,action,docids):
        method = getattr(self,action)
        for docid in docids:
            if docid:
                method(docid)

    def InitializeDB(self):
        pass
            
    def DownloadAll(self, module='all'):
        self._doAction('DownloadAll',module)

    def DownloadNew(self, module='all'):
        self._doAction('DownloadNew', module)

    def ParseAll(self,module='all'):
        self._doAction('ParseAll',module)

    def ParseSome(self,module,listfile):
        docids = codecs.open(listfile,encoding='iso-8859-1').read().split("\r\n")
        self._doActionFor('Parse',module,docids)

    def RelateAll(self,module='all'):
        self._doAction('RelateAll',module)

    def GenerateAll(self,module='all'):
        self._doAction('GenerateAll',module)
    
    def RunTest(self, module='all'):
        self._doTest(module)

    def Indexpages(self,module='all'):
        if module != 'site':
            self._doAction('Indexpages', module)
        if module in ('all','site'):
            self._static_indexpages()

    def News(self,module='all'):
        if module != 'site':
            self._doAction('News', module)
        if module in ('all','site'):
            self._static_newspages()

    def _prep_frontpage(self):
        # Step 1: Download Wiki frontpage
        browser = Browser()
        browser.set_handle_robots(False) # we can ignore our own robots.txt
        url = "http://wiki.lagen.nu/index.php/Special:Exportera/Lagen.nu:Huvudsida"
        browser.open(url)
        xml = ET.parse(browser.response())

        wikitext = xml.find("//"+MW_NS+"text").text

        # Step 2: Filter out some stuff

        marker = "= Index ="
        if marker in wikitext:
            # Step 3: Run the rest through wikiparser
            from Wiki import WikiParser
            idx = wikitext.index(marker) + len(marker)
            wikitext = wikitext[idx+1:]
            p = WikiParser()
            incfile = os.path.sep.join([self.baseDir, 'site', 'generated', 'index.inc.xht2'])
            Util.ensureDir(incfile)
            fp = open(incfile,"w")
            fp.write(p.parse_wikitext("index",wikitext))
            fp.close()
            shutil.copy2(incfile,'static')
            # Step 4: index.inc.xht2 is then incorporated through an
            # XInclude in static/index.xht2
        else:
            log.warning("Marker %s not found at %s" % (marker,url))

    def _static_indexpages(self):
        # make the front page and other static pages
        log.info("Generating site global static pages")

        self._prep_frontpage()
                       
        # we need to copy the following four file to the base dir,
        # temporarily, in order to avoid spurious xml:base elements 
        # (http://norman.walsh.name/2005/04/01/xinclude#comment0005)
        includes = [os.path.sep.join([self.baseDir,'site','generated','nyheter','site.xht2']),
                    os.path.sep.join([self.baseDir,'sfs','generated','news','lagar.xht2']),
                    os.path.sep.join([self.baseDir,'dv','generated','news','allmanna.xht2']),
                    os.path.sep.join([self.baseDir,'site','generated','index.inc.xht2'])]

        for f in includes:
            if os.path.exists(f):
                shutil.copy2(f,'static')

        for f in Util.listDirs(u'static', '.xht2'):
            basefile = f.replace('static'+os.path.sep,'')
            outfile = os.path.sep.join([self.baseDir, 'site', 'generated', basefile.replace(".xht2",".html")])
            log.info("Generating %s" % outfile)
            Util.ensureDir(outfile)
            Util.transform("xsl/static.xsl", f, outfile,validate=False,xinclude=True)

        for f in includes:
            Util.robust_remove(os.path.sep.join([self.baseDir,'static',os.path.split(f)[1]]))
            Util.robust_remove(os.path.sep.join([self.baseDir,'site','generated',os.path.split(f)[1].replace(".xht2", ".html")]))



        # copy everything in img to basedir site generated img
        for dirname in ['css', 'css/images','js','img', 'img/treeview']:
            for f in os.listdir(dirname):
                src = dirname+os.path.sep+f
                if os.path.isfile(src):
                    dest = os.path.sep.join([self.baseDir, 'site', 'generated', dirname, f])
                    Util.copy_if_different(src,dest)


    # FIXME: Maybe Manager should derive from LegalSource.Manager, in
    # order to make use of _render_newspage?
    re_news_subjectline = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)').match
    def _static_newspages(self):
        entries = []
        entry = None
        for line in codecs.open("static/nyheter/site.txt", encoding="iso-8859-1").read().splitlines():
            m = self.re_news_subjectline(line)
            if m:
                if entry:
                    paras = entry['content'].strip().split("\n\n")
                    entry['shortdesc'] = paras[0]
                    if len(paras) > 1:
                        entry['shortdesc'] += u'<p><a href="%s">Läs mer...</a></p>' % entry['uri']
                    entries.append(entry)

                timestamp = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                # we use YY-MM-DD, not YYYY-MM-DD, to be compatible with lagen.nu 1.0-style urls
                timefmt = datetime.strftime(timestamp,"%y-%m-%d")
                title = m.group(2)
                entry = {'title': title,
                         'timestamp':timestamp,
                         'timefmt':timefmt,
                         'uri':'/nyheter/%s.html' % timefmt,
                         'id': timefmt,
                         'content':''}
            else:
                entry['content'] += line+"\n"

        if entry:
            paras = entry['content'].strip().split("\n\n")
            entry['shortdesc'] = paras[0]
            if len(paras) > 1:
                entry['shortdesc'] += u'<p><a href="%s">Läs mer...</a></p>' % entry.uri
            entries.append(entry)

        outfile = "%s/site/generated/nyheter/site.html" % self.baseDir
        xht2file = "%s/site/generated/nyheter/site.xht2" % self.baseDir
        self._render_page(outfile,'etc/newspage.template.xht2',xht2file,'xsl/static.xsl','Nyheter',entries)
        outfile = "%s/site/generated/nyheter/site.atom" % self.baseDir
        self._render_page(outfile,'etc/newspage.template.atom',None,None,'Nyheter',entries)

        for entry in entries:
            del entry['shortdesc']
            title = entry['title']
            del entry['title']
            outfile = "%s/site/generated/nyheter/%s.html" % (self.baseDir, entry['timefmt'])
            self._render_page(outfile,'etc/newspage.template.xht2',
                              None,'xsl/static.xsl',title,[entry])

    def _render_page(self,outfile,template,xht2file,transform,title,entries):
        loader = TemplateLoader(['.' , os.path.dirname(__file__)], 
                                variable_lookup='lenient') 
        tmpl = loader.load(template)
        stream = tmpl.generate(title=title,
                               subtitle=u'Från lagen.nu',
                               entries=entries,
                               feeduri=u'https://lagen.nu/nyheter/site.atom',
                               pageuri=u'https://lagen.nu/nyheter/site.html')
        if xht2file:
            tmpfilename = xht2file
            Util.ensureDir(tmpfilename)
        else:
            tmpfilename = mktemp()
        fp = open(tmpfilename,"w")
        fp.write(stream.render())
        fp.close()

        if transform:
            Util.transform(transform, tmpfilename, outfile, validate=False)
        else:
            Util.replace_if_different(tmpfilename, outfile)

        log.info("rendered %s" % (outfile))
            
        
    
    def Publish(self):
        self._make_zipfiles()

        publish = "%s-publish.txt" % self.baseDir
        lastpublish = "%s-lastpublish.txt" % self.baseDir

        log.info("Listing changed files")

        if os.name == 'nt':
            findcmd = 'C:/cygwin/bin/find'
        else:
            findcmd = 'find'
        
        if os.path.exists(lastpublish):
            cmd = '%s %s -type f -cnewer %s > %s' % (findcmd, self.baseDir, lastpublish, publish)
        else:
            cmd = '%s %s > %s' % (findcmd, self.baseDir, publish)
        # print "command is '%s'" % cmd
        (ret, stdout, stderr) = Util.runcmd(cmd)
        numlines=0
        for line in file(publish):
            numlines+=1
        log.info("%d files changed" % numlines)
        if numlines == 0:
            log.info("No files to publish, we're done!")
        else:
            log.info("Copying to target server")
            localcmd    = 'tar -c -T %s --mode a+rwx -f - ' % publish
            transfercmd = 'ssh -C %s' % self.config['ssh_host']
            remotecmd   = 'cd %s && tar xf -' % self.config['remote_dir']
            cmd = '%s | %s "%s"' % (localcmd, transfercmd, remotecmd)
            # print "command is '%s'" % cmd
            (ret, stdout, stderr) = Util.runcmd(cmd)
            if (ret == 0):
                log.info("Published and done!")
                Util.robustRename(publish, lastpublish)
            else:
                log.info("Copying (tar over ssh) failed with error code %s (%s)" % (ret, stderr))

    def WikiUpdate(self, wikipage):
        import Keyword
        re_firstchar = re.compile(r'(\w)', re.UNICODE).search

        # signs of UTF8 mojibake
        if isinstance(wikipage,unicode) and u'\xc3' in wikipage:
            wikipage =  wikipage.encode('latin-1').decode('utf-8')
        import Wiki
        wikimgr = Wiki.WikiManager()
        wikimgr.Download(wikipage)
        wikimgr.Parse(wikipage) 
        wikimgr.Relate(wikipage)
        if wikipage.startswith("SFS/"):
            import SFS
            sfsnr = wikipage.split("/",1)[1]
            sfsmgr = SFS.SFSManager()
            sfsmgr.Generate(sfsnr)
        elif wikipage.startswith("Dom/"):
            pass
        elif ":" in wikipage: # not in default namespace, probably
            (namespace,localpage) = wikipage.split(":")
            if namespace == "Kategori":
                firstletter = re_firstchar(localpage).group(0)
                basefile = u'%s/%s' % (firstletter,localpage)
                kwmgr = Keyword.KeywordManager()
                kwmgr.Parse(basefile,wiki_keyword=True) # needed for new terms
                kwmgr.Generate(basefile)
            elif namespace == "Lagen.nu" and localpage == "Huvudsida":
                self._prep_frontpage()
                infile = Util.relpath(os.path.sep.join(['static','index.xht2']))
                outfile = Util.relpath(os.path.sep.join([self.baseDir,'site','generated','index.html']))
                print "in %s, out %s" % (infile,outfile)
                Util.transform("xsl/static.xsl", infile, outfile, validate=False, xinclude=True)
        else:
            firstletter = re_firstchar(wikipage).group(0)
            basefile = u'%s/%s' % (firstletter,wikipage)
            kwmgr = Keyword.KeywordManager()
            kwmgr.Parse(basefile,wiki_keyword=True) # needed for new terms
            # raise ValueError(repr(basefile))
            kwmgr.Generate(basefile)

    def WikiUpdateSome(self,listfile):
        docids = codecs.open(listfile,encoding='iso-8859-1').read().split("\r\n")
        self._doManagerActionFor('WikiUpdate',docids)

    def _make_zipfiles(self):
        self._make_zipfile(os.path.sep.join([self.baseDir,u'dv','dv.zip']),
                           os.path.sep.join([self.baseDir,u'dv','parsed']),
                           ".xht2")

        self._make_zipfile(os.path.sep.join([self.baseDir,u'sfs','sfs.zip']),
                           os.path.sep.join([self.baseDir,u'sfs','parsed']),
                           ".xht2")
        
        

    def _make_zipfile(self, zipname, directory, extension=None):
        files = Util.listDirs(directory, extension)
        if Util.outfile_is_newer(files,zipname):
            log.info("Existing zip file %s is newer than all contained files" % zipname)
            return
        
        from zipfile import ZipFile, ZIP_DEFLATED
        log.info("Creating zip file %s" % zipname)
        z = ZipFile(zipname, 'w', ZIP_DEFLATED) # shrinks the file from ~130M to ~21M
        for f in Util.listDirs(directory, extension):
            zipf = f.replace(directory+os.path.sep, '')
            # it seems the write method can't handle unicode strings
            # -- convert to bytestrings using cp437, as that seems to
            # be the zip standard
            # print "adding %r" % zipf
            z.write(f, zipf.encode('cp437'))
        z.close()
        

    def DoFinal(self,module='all'):
        self.Indexpages(module)
        self.News(module)
        self.Publish()
    
    def DoAll(self,module='all'):
        start = time.time()
        self._doAction('DownloadNew',module)
        self._doAction('ParseAll',module)
        self._doAction('RelateAll',module)
        self._doAction('GenerateAll',module)
        self.News(module)
        self.Indexpages(module)
        # self.Publish()
        log.info(u'DoAll finished in %s' % time.strftime("%H:%M:%S",time.gmtime(time.time() - start)))

if __name__ == "__main__":
    import logging.config
    # print "loading logging config from %s" % __scriptdir__ + '/etc/log.conf'
    logging.config.fileConfig(__scriptdir__ + '/etc/log.conf')
    Manager.__bases__ += (DispatchMixin,)
    mgr = Manager()
    mgr.Dispatch(sys.argv)
