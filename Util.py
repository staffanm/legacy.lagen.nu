#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""General  library of small utility functions"""

import os, sys, subprocess, codecs, shutil, locale
from tempfile import mktemp
import filecmp
import BeautifulSoup


# Set up common namespaces and suitable prefixes for them
ns = {'dc':'http://purl.org/dc/elements/1.1/',
      'dct':'http://purl.org/dc/terms/',
      'rdfs':'http://www.w3.org/2000/01/rdf-schema#',
      'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
      'rinfo':'http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#',
      'rinfoex':'http://lagen.nu/terms#',
      'xsd':'http://www.w3.org/2001/XMLSchema#'}

class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class TransformError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ExternalCommandError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def mkdir(newdir):
    if not os.path.exists(newdir):
        os.makedirs(newdir)

def ensureDir(filename):
    d = os.path.dirname(filename)
    if d and not os.path.exists(d):
        mkdir(d)

def robustRename(old,new):
    """Rename old to new no matter what (if the file exists, it's
    removed, if the target dir doesn't exist, it's created)"""
    # print "robustRename: %s -> %s" % (old,new)
    ensureDir(new)
    if os.path.exists(new):
        #try:
        os.unlink(new)
        #except WindowsError:
        #    print "Caught WindowsError, sleeping"
        #    import time
        #    time.sleep(1)
        #    os.unlink(new)
    # os.rename may fail across file systems
    shutil.move(old, new)
   
def robust_remove(file):
    if os.path.exists(file):
        #try:
        os.unlink(file)
        #except WindowsError:
        #    print "Caught WindowsError, sleeping"
        #    import time
        #    time.sleep(1)
        #    os.unlink(file)

def numcmp(x,y):
    return cmp(split_numalpha(x),split_numalpha(y))

# '10 a §' => [10, ' a §']
def split_numalpha(s):
    res = []
    seg = ''
    digit = s[0].isdigit()
    for c in s:
        if (c.isdigit() and digit) or (not c.isdigit() and not digit):
            seg += c
        else:
            res.append(int(seg) if seg.isdigit() else seg)
            seg = c
            digit = not digit
    res.append(int(seg) if seg.isdigit() else seg)
    return res

def indentXmlFile(filename):
    """Neatifies an existing XML file in-place by running xmllint --format"""
    #tmpfile = "tmp.%s.xml" % os.getpid()
    #cmdline = "xmllint --format %s > %s" % (filename,tmpfile)
    #(ret,stdout,stderr) = runcmd(cmdline)
    #if (not ret):
    #    robustRename(tmpfile,filename)
    #else:
    #    raise ExternalCommandError("'%s' returned %d: %s" % (cmdline, ret, stderr))
    # The tidy invocation is for wrapping long lines for easier
    # readability (something that xmllint won't do for us) -- however,
    # it seems that Tidy, even though -raw is used, mangles tag names
    # with non-us-ascci characters when the file is utf-8-encoded
    # ('<Sökord>Lis pendens</Sökord>' comes out as '<Sàkord="">Lis
    # pendens</Sþ'). This is not a problem when using XHTML2, but it's
    # still a bug.
    #
    # Also, tidy will hang (due to excessive stderr messages?) for 1992:1226 -- we should
    # try to get runcmd handle this

    (ret,stdout,stderr) = runcmd("tidy -xml -utf8 -i -m -w 0 %s" % (filename))
    if (ret != 0):
        raise TransformError(stderr)
    # This fails occasionally - why?
    # os.remove(tmpfile)
    

def tidyHtmlFile(filename):    
    """Neatifies an existing XHTML file in-place by running tidy"""
    if os.sys.platform == "darwin":
        tidycmd = "/usr/local/bin/tidy"
    else:
        tidycmd = "tidy"
    (ret,stdout,stderr) = runcmd("%s -q -n -i -asxhtml -latin1 -w 120 --doctype strict %s > tmp.xml" % (tidycmd,filename))
    # tidy always exists with a non-0 return code if there were any
    # hrefs with spaces in them, so let's just silently ignore errors
    # for now
    #if (ret != 0):
    #    raise TidyError(stderr)
    
    # os.system("xmllint --format %s > tmp.xml" % filename)
    robustRename("tmp.xml", filename)

def transform(stylesheet,infile,outfile,parameters={},validate=True,xinclude=False):
    """Does a XSLT transform with the selected stylesheet. Afterwards, formats the resulting HTML tree and validates it"""

    parameters['infile'] = infile;
    parameters['outfile'] = outfile;
    
    param_str = ""
    for p in parameters.keys():
        # this double style quoting is needed for lawlist.xsl when
        # using the tagname parameter on macos. Maybe for other
        # reasons as well, I dunno
        param_str += "--param %s \"'%s'\" " % (p,parameters[p])

    if xinclude:
        tmpfile = mktemp()
        cmdline = "xmllint --xinclude --encode utf-8 %s > %s" % (infile, tmpfile)
        #print cmdline
        (ret,stdout,stderr) = runcmd(cmdline)
        #if (ret != 0):
        #    raise TransformError(stderr)
        infile = tmpfile

    tmpfile = mktemp()
    stylesheet = os.path.join(os.path.dirname(__file__),stylesheet)
    cmdline = "xsltproc %s %s %s > %s" % (param_str,stylesheet,infile,tmpfile)
    # print cmdline
    (ret,stdout,stderr) = runcmd(cmdline)
    if (ret != 0):
        raise TransformError(stderr)
    if stderr:
        print stderr

    # can't use tidy for HTML fragments -- it creates <head> and <body> sections and other stuff
    # tidyHtmlFile(outfile)
    # indentXmlFile(outfile)

    replace_if_different(tmpfile, outfile)
    if os.path.exists(tmpfile):
        os.unlink(tmpfile)
    if xinclude:
        os.unlink(infile)
    if validate:
        cmdline = "xmllint --noout --nonet --nowarning --dtdvalid %s/dtd/xhtml1-strict.dtd %s" % (basepath,outfile)
        (ret,stdout,stderr) = runcmd(cmdline)
        if (ret != 0):
            raise ValidationError(stderr)

def uniqueList(*lists):
    slots = {}
    for l in lists:
        for i in l:
            slots[i] = 1
    return slots.keys();

def runcmd(cmdline):
    # print "runcmd: %r" % cmdline
    if isinstance(cmdline,unicode):
        # FIXME: How do we detect the proper encoding? Using
        # sys.stdout.encoding gives 'cp850' on windows, which is not
        # what xsltproc expects
        cmdline = cmdline.encode('iso-8859-1')

    p = subprocess.Popen(cmdline,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    ret = p.returncode
    # print "runcmd '%s...': %s, '%s...', '%s...'" % (cmdline[:15], ret, stdout[:15], stderr[:15])
    if sys.stdout.encoding:
        enc = sys.stdout.encoding
    else:
        enc = locale.getpreferredencoding()
        
    if isinstance(stdout, str):
        stdout = stdout.decode(enc)
    if isinstance(stderr, str):
        stderr = stderr.decode(enc)
    return (p.returncode,stdout,stderr)

def normalizeSpace(string):
    return u' '.join(string.split())

def listDirs(d,suffix=None,reverse=False):
    """A generator that works much like os.listdir, only recursively (and only returns files, not directories)"""
    # inspired by http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/161542
        
    if isinstance(d,str):
        print "WARNING: listDirs was called with str. Use unicode instead, plz"
    directories = [d]
    while directories:
        d = directories.pop()
        for f in sorted(os.listdir(d),cmp=numcmp,reverse=reverse):
            #print "f is %s" % f
            f = "%s%s%s" % (d,os.path.sep,f)
            if os.path.isdir(f):
                directories.insert(0,f)
            elif os.path.isfile:
                if suffix and not f.endswith(suffix):
                    continue
                else:
                    #print "yielding %s" % f
                    yield f

def loadSoup(filename,encoding='iso-8859-1'):
    return BeautifulSoup.BeautifulSoup(
        codecs.open(filename,encoding=encoding,errors='replace').read(),
        convertEntities='html')


def elementText(element):
    """finds the plaintext contained in a BeautifulSoup element"""
    return normalizeSpace(
        u''.join(
        [e for e in element.recursiveChildGenerator() 
         if (isinstance(e,unicode) and 
             not isinstance(e,BeautifulSoup.Comment))]))

def word_to_html(indoc,outhtml):
    indoc = os.path.join(os.getcwd(),indoc.replace("/",os.path.sep))
    outhtml = os.path.join(os.getcwd(),outhtml.replace("/",os.path.sep))
    display_indoc = indoc[len(os.getcwd()):].replace(os.path.sep,"/")
    display_outhtml = outhtml[len(os.getcwd()):].replace(os.path.sep,"/")
    # print "Ensuring dir for %r" % outhtml
    ensureDir(outhtml)
    if not os.path.exists(indoc):
        print "indoc %s does not exists (seriously)" % indoc
    if os.path.exists(outhtml):
        # if self.verbose: print "local file %s exists, not doing Word->HTML conversion" % display_outhtml
        return
    #if os.path.exists(outhtml + ".err.log"):
    #    print "Word->HTML conversion for local file %s has failed, not re-trying"% display_outhtml
    #    return
    from win32com.client import Dispatch
    import pywintypes
    wordapp = Dispatch("Word.Application")
    if wordapp == None:
        print "Couldn't start word"
        return
    # print "word_to_html: %s to %s" % (indoc,outhtml)
    try:
        wordapp.Documents.Open(indoc)
        wordapp.Visible = False
        doc = wordapp.ActiveDocument
        doc.SaveAs(outhtml, 10) # 10 = filtered HTML output
        doc.Close()
        doc = None
        wordapp.Quit
    except pywintypes.com_error, e:
        print "Warning: could not convert %s" % indoc
        print e[2][2]
        errlog = open(outhtml+".err.log","w")
        errlog.write("%s:\n%s" % (indoc,e))

def indent_et(elem, level=0):
    i = "\r\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent_node(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def indent_node(elem, level=0):
    i = "\r\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent_node(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def replace_if_different(newfile,oldfile):
    assert os.path.exists(newfile)
    if not os.path.exists(oldfile):
        robustRename(newfile,oldfile)
    elif not filecmp.cmp(newfile,oldfile):
        robustRename(newfile,oldfile)
    else:
        os.unlink(newfile)

def copy_if_different(src,dest):
    if not os.path.exists(dest):
        ensureDir(dest)
        shutil.copy2(src,dest)
    elif not filecmp.cmp(src,dest):
        os.unlink(dest)
        shutil.copy2(src,dest)
    else:
        pass

def outfile_is_newer(infiles,outfile):
    """check to see if the outfile is newer than all ingoing files
    (which means there's no need to regenerate outfile)"""
    if not os.path.exists(outfile): return False
    outfile_mtime = os.stat(outfile).st_mtime
    for f in infiles:
        # print "Testing whether %s is newer than %s" % (f, outfile)
        if os.path.exists(f) and os.stat(f).st_mtime > outfile_mtime:
            # print "%s was newer than %s" % (f, outfile)
            return False
    # print "%s is newer than %r" % (outfile, infiles)
    return True

