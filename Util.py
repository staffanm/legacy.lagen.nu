#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""General library of small utility functions"""

# On what to add here:
# * only functions that are generally useful in any part of the source code
# * code only useful for Parsers/Downloaders should go in the LegalSource.* classes

import os, subprocess, codecs
import BeautifulSoup

# other peoples code

# From http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/82465
# author: Trent Mick
# license: PSL
def mkdir(newdir):
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
            mkdir(head)
            #print "mkdir %s" % repr(newdir)
        if tail:
            os.mkdir(newdir)

def ensureDir(filename):
    d = os.path.dirname(filename)
    if not os.path.exists(d):
        mkdir(d)

def robustRename(old,new):
    """Rename old to new no matter what (if the file exists, it's
    removed, if the target dir doesn't exist, it's created"""
    ensureDir(new)
    if os.path.exists(new):
        os.unlink(new)
    os.rename(old, new)
    
# # from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/135435
# # author: Chui Tey
# # license: PSL
# def numsort(alist):
#     """
#     Sorts a list in numeric order. For example:
#         ['aaa35', 'aaa6', 'aaa261'] 
#     is sorted into:
#         ['aaa6', 'aaa35', 'aaa261']
#     """
# 
#     def _generate_index(str):
#         """
#         Splits a string into alpha and numeric elements, which
#         is used as an index for sorting
#         """
#         #
#         # the index is built progressively
#         # using the _append function
#         #
#         index = []
#         def _append(fragment, alist=index):
#             if fragment.isdigit(): fragment = int(fragment)
#             alist.append(fragment)
#     
#         # initialize loop
#         prev_isdigit = str[0].isdigit()
#         current_fragment = ''
#         # group a string into digit and non-digit parts
#         for char in str:
#             curr_isdigit = char.isdigit()
#             if curr_isdigit == prev_isdigit:
#                 current_fragment += char
#             else:
#                 _append(current_fragment)
#                 current_fragment = char
#                 prev_isdigit = curr_isdigit
#         _append(current_fragment)
#         return tuple(index)
#     indices = map(_generate_index, alist)
#     decorated = zip(indices, alist)
#     decorated.sort()
#     return [ item for index, item in decorated ]
# 


# the rest of the code is my fault

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

# FIXME: phase code out to use odict instead
class OrderedDict:
    """A combination of a list and a dictionary. There probably exists
    a much-better built-in version somewhere"""
    
    def __init__(self):
        self.list = []
        self.dict = {}

    def append(self,key,value):
        self.list.append([key,value])
        self.dict[key] = self.list[-1]

    def append_to_value(self,key,value):
        #print "append_to_value: initial value: '%s'" % self.dict[key][1]
        #print "append_to_value: value to append: '%s'" % value
        l = self.dict[key]
        l[1] += value
        #print "append_to_value: final value: '%s'" % self.dict[key][1]
        
    def item(self,key):
        return self.dict[key][1]

    def has_key(self,key):
        return self.dict.has_key(key)

    def extend(self,dict2):
        for item in dict2.list:
            self.list.append(item)



def indentXmlFile(filename):
    """Neatifies an existing XML file in-place by running xmllint --format"""
    tmpfile = "tmp.%s.xml" % os.getpid()
    cmdline = "xmllint --format %s > %s" % (filename,tmpfile)
    (ret,stdout,stderr) = runcmd(cmdline)
    if (not ret):
        os.remove(filename)
        os.rename(tmpfile,filename)
    else:
        raise ExternalCommandError("'%s' returned %d: %s" % (cmdline, ret, stderr))
    # The tidy invocation is for wrapping long lines for easier readability
    # (something that xmllint won't do for us) -- however, it seems that Tidy,
    # even though -raw is used, mangles tag names with non-us-ascci characters
    # when the file is utf-8-encoded ('<Sökord>Lis pendens</Sökord>' comes
    # out as '<Sàkord="">Lis pendens</Sþ'). Therefore it's disabled until I find
    # a better XML formatting tool.
    #
    # Also, tidy will hang (due to excessive stderr messages?) for 1992:1226 -- we should
    # try to get runcmd handle this
    # (ret,stdout,stderr) = runcmd("tidy -xml -raw -i %s > %s" % (tmpfile,filename))
    # if (ret != 0):
    #    raise TransformError(stderr)
    # os.remove(tmpfile)
    # 

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
    os.remove(filename)
    os.rename("tmp.xml",filename)

def transform(stylesheet,infile,outfile,parameters={},validate=True):
    """Does a XSLT transform with the selected stylesheet. Afterwards, tidies the resulting HTML tree and validates it"""
    param_str = ""
    for p in parameters.keys():
        # this double style quoting is needed for lawlist.xsl when
        # using the tagname parameter on macos. Maybe for other
        # reasons as well, I dunno
        param_str += "--param %s \"'%s'\" " % (p,parameters[p])
    
    cmdline = "xsltproc %s %s %s > %s" % (param_str,stylesheet,infile,outfile)
    # print cmdline
    (ret,stdout,stderr) = runcmd(cmdline)
    if (ret != 0):
        raise TransformError(stderr)

    # can't use tidy for HTML fragments -- it creates <head> and <body> sections and other stuff
    # tidyHtmlFile(outfile)
    indentXmlFile(outfile)

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
    # print "runcmd: %s" % cmdline
    p = subprocess.Popen(cmdline,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout = p.stdout.read()
    stderr = p.stderr.read()
    ret = p.wait()
    return (ret,stdout,stderr)

def normalizeSpace(string):
    return " ".join(string.split())

def listDirs(dir,suffix=None):
    """A generator that works much like os.listdir, only recursively (and only returns files, not directories)"""
    # inspired by http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/161542
    directories = [dir]
    while directories:
        dir = directories.pop()
        for f in os.listdir(dir):
            
            f = "%s/%s" % (dir,f)
            if os.path.isdir(f):
                directories.append(f)
            elif os.path.isfile:
                if suffix and not f.endswith(suffix):
                    continue
                else:
                    yield f

def loadSoup(filename,encoding='iso-8859-1'):
    return BeautifulSoup.BeautifulSoup(
        codecs.open(filename,encoding=encoding,errors='replace').read(),
        convertEntities='html')


def elementText(element):
    """finds the plaintext contained in a BeautifulSoup element"""
    return normalizeSpace(
        ''.join(
        [e for e in element.recursiveChildGenerator() 
         if (isinstance(e,unicode) and 
             not isinstance(e,BeautifulSoup.Comment))]))
