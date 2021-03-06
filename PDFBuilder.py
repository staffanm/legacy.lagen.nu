#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# load a list of wanted texts
# - syntax for expressing just part of a text needed (http://www.lagen.nu/1962:700#K20 ? )
# 
# create one big xht2 file with all lawtext and other stuff
# - load in each file (optionally filtering out the needed part(s)
# - transform each file including metadata (particularly title) into a body-level section
# - maybe create a toc as well ?
#
# run prince on the result
#
# folkets jubel!
import sys,os
from SFS import SFSManager
from Util import mkdir as mkdirp
import xml.etree.cElementTree as ET

import re
from collections import defaultdict
from pprint import pprint
from genshi.template import TemplateLoader

def parseList(s):
    return [l.strip().split("#") for l in s.split("\n")]

def parseAccessExport(s):
    res = defaultdict(list)
    for l in s.split("\n"):
        flds = [re.sub('(^"|"$)', '', x) for x in l.split("\t")]
        if len(flds) == 6:
            (id, name, year, sfsnr, kursfordan, area) = flds
            if year == 0: continue
            res[area].append({'sfsnr': "%s:%s" % (year, sfsnr),
                              'rubrik': name})
    return res
        
def parseSimpleList(s,title):
    res = []
    for l in s.split("\n"):
        if l:
            (sfsnr, rubrik,indelning) = l.split("\t")
            res.append({'sfsnr':sfsnr,'rubrik':rubrik,'indelning':indelning})
    return {title:res}

def download_config(configpage):
    import Wiki
    wd = Wiki.WikiDownloader()
    wd._downloadSingle(configpage)

def main(listfile,title=u"Lagtextsamling"):
    res = parseSimpleList(open(listfile).read().decode('iso-8859-1'),title)
    for area in sorted(res.keys()):
        for f in res[area]:
            pass
        areastruct = {area:res[area]}
        loader = TemplateLoader(['.'])
        tmpl = loader.load("etc/samling.template.xht2")
        stream = tmpl.generate(data=areastruct, ns={'xmlns:xi':'http://www.w3.org/2001/XInclude'})
        out = open("tmp.xht2", "w")
        out.write(stream.render())
        out.close()
        # note that prince.exe has internal xinclude support, so this step isn't really needed
        # (is useful for debugging though)
        cmd = "xmllint --xinclude --format tmp.xht2 > out.xht2" 
        os.system(cmd)
        cmd = '"C:\\Program Files (x86)\\Prince\\Engine\\bin\\prince.exe" -s css\\xht2-print.css out.xht2 -o %s.pdf' % area.encode('iso-8859-1').replace(" ", "")
        print cmd
        os.system(cmd)
    

if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    main(sys.argv[1])

    

