#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) från Domstolsverket, www.rattsinfosok.dom.se

Modulen hanterar omvandlande av domslutsdetaljer och -referat till XML
"""
import sys
import os
import re
import shutil
import unittest
import pprint
import types
import LegalSource
import Util

sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Domslut (detaljer och referat)"

class DVMigrate:
    """Engångsflyttkod"""

    def Migrate():
        import sha
        from difflib import Differ
        basedir = "legacy/verdict"
        newdir = "testdata/dv/downloaded"
        moves = {}
        checksums = {}
        for d in os.listdir(basedir):
            if d.isdigit():
                for f in os.listdir("%s/%s" % (basedir,d)):
                    oldfile = "%s/%s/%s" % (basedir,d,f)
                    if f.startswith("report-"):
                        id = f[7:-5]
                        filename = "%s/%s.referat.html" % (newdir, id)
                    elif f.startswith("summary-"):
                        id = f[8:-5]
                        filename = "%s/%s.detalj.html" % (newdir, id)
                    else:
                        filename = None
                        continue
                    
                    # print "%s -> %s" % (oldfile,filename)
                    c = sha.new()
                    c.update(file(oldfile).read())
                    if filename in moves:
                        print "WARNING: %s previously exists as %s" % (oldfile, moves[filename])
                        if c.hexdigest() == checksums[filename]:
                            print "But %s == %s, so no matter" % (c.hexdigest(), checksums[filename])
                        else:
                            print "Checksums differ (%s vs %s), can't be good. Checking diff:" % (c.hexdigest(), checksums[filename])
                            (ret,stdout,stderr) = runcmd("diff %s %s" % (moves[filename], oldfile))
                            print ret
                            print stdout
                            print stderr
                    
                    moves[filename] = oldfile
                    checksums[filename] = c.hexdigest()
                    print "%s (%s) A-OK" % (moves[filename], checksums[filename])
                    
                    # assert(not os.path.exists(filename))
                    shutil.copy2(oldfile,filename)

    def runcmd(cmdline):
        import subprocess
        print "runcmd: %s" % cmdline
        p = subprocess.Popen(cmdline,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stdout = p.stdout.read()
        stderr = p.stderr.read()
        ret = p.wait()
        return (ret,stdout,stderr)
 

class DVParser(LegalSource.Parser):
    re_NJAref = re.compile(r'(NJA \d{4} s\. \d+) \(alt. (NJA \d{4}:\d+)\)')
    re_delimSplit = re.compile("[:;,] ?").split
    def __init__(self,id,files,baseDir):
        self.id = id
        self.dir = baseDir + "/dv/parsed"
        if not os.path.exists(self.dir):
            Util.mkdir(self.dir)
        self.files = files

    def Parse(self):
        import codecs
        soup = self.loadDoc(self.files['detalj'])
        data = {}
        for row in soup.first('td', 'sokmenyBkgrMiddle').table:
            key = val = ""
            if len(row) > 3:
                key = row('td')[1].string.strip()
                if key == "":
                    key = lastkey
                if key[-1] == ":":
                    key = key[:-1]
                val = self.elementText(row('td')[2])

                if val[:8] == "&#8226; ":
                    val = val[8:]
                lastkey = key
                if val != '-':
                    if key in data:
                        if type(data[key]) == types.ListType:
                            data[key].append(val)
                        else:
                            data[key] = [data[key],val]
                    else:
                        m = self.re_NJAref.match(val)
                        if m:
                            val = m.group(1)
                            data["Alt"+key] = m.group(2)
                        data[key] = val

        urn = self.__createUrn(data)

        referat = []
        if 'referat' in self.files:
            soup = self.loadDoc(self.files['referat'])
            if soup.first('span', 'riDomstolsRubrik'):
                ref_domstol_node = soup.first('span', 'riDomstolsRubrik').findParent('td')
            elif soup.first('td', 'ritop1'):
                ref_domstol_node = soup.first('td', 'ritop1')
            else:
                raise LegalSource.ParseError("Kunde inte hitta domstolsnamnet i %s" % self.files['referat'])
            ref_domstol = self.elementText(ref_domstol_node)
            ref_refid = self.elementText(ref_domstol_node.findNextSibling('td'))
            if not ref_refid:
                raise LegalSource.ParseError("Kunde inte hitta referatnumret i %s" % self.files['referat'])
            m = self.re_NJAref.match(val)
            if m:
                ref_refid = m.group(1)

            if ref_domstol.lower() != data['Domstol'].lower():
                print u"WARNING (Domstol): '%s' != '%s'" % (ref_domstol, data['Domstol'])
            if ref_refid != data['Referat']:
                print u"WARNING (Referat): '%s' != '%s'" % (ref_refid, data['Referat'])
            for p in soup.firstText(u'REFERAT').findParent('tr').findNextSibling('tr').fetch('p'):
                referat.append(self.elementText(p))

            ref_sokord = self.elementText(soup.firstText(u'Sökord:').findParent('td').nextSibling.nextSibling)
            ref_sokord_arr = [self.normalizeSpace(x) for x in self.re_delimSplit(ref_sokord)]
            ref_sokord_arr.sort()
            if not u'Sökord' in data:
                data_sokord_arr = []
            elif type(data[u'Sökord']) == types.ListType:
                data_sokord_arr = data[u'Sökord']
            else:
                data_sokord_arr = [data[u'Sökord']]

            data_sokord_arr.sort()
            if data_sokord_arr != ref_sokord_arr:
                print u"WARNING (Sokord): '%s' != '%s'" % (";".join(data_sokord_arr), ";".join(ref_sokord_arr))
                data[u'Sökord'] = Util.uniqueList(ref_sokord_arr, data_sokord_arr)
                
                print u" --- combining to '%s'" % ";".join(data[u'Sökord'])
            if soup.firstText(u'Litteratur:'):
                ref_litteratur = self.elementText(soup.firstText(u'Litteratur:').findParent('td').nextSibling.nextSibling)
                data['Litteratur'] = [self.normalizeSpace(x) for x in ref_litteratur.split(";")]

        root = ET.Element("Dom")
        root.attrib['urn'] = urn
        meta = ET.SubElement(root,"Metadata")
        for k in data.keys():
            if type(data[k]) == types.ListType:
                for i in data[k]:
                    node = ET.SubElement(meta,k)
                    node.text = i
            else:
                node = ET.SubElement(meta,k)
                node.text = data[k]
        if referat:
            ref = ET.SubElement(root,"Referat")
            for p in referat:
                node = ET.SubElement(ref,"p")
                node.text = p
            
        tree = ET.ElementTree(root)
        tree.write(self.dir + "/" + self.id + ".xml", encoding="iso-8859-1")
        Util.indentXmlFile(self.dir+"/"+self.id+".xml")

        return tree

    def __createUrn(self,data):
        domstolar = {
            u'Marknadsdomstolen':                 u'md',
            u'Hovrätten för Övre Norrland':       u'hovr:övrenorrland',
            u'Hovrätten för Nedre Norrland':      u'hovr:nedrenorrland',
            u'Hovrätten över Skåne och Blekinge': u'hovr:skåne',
            u'Svea hovrätt':                      u'hovr:svea',
            u'Hovrätten för Västra Sverige':      u'hovr:västra',
            u'G\xf6ta hovr\xe4tt':                u'hovr:göta',
            u'Kammarr\xe4tten i G\xf6teborg':     u'kamr:göteborg',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'kamr:jönkoping',
            u'Kammarr\xe4tten i Stockholm':       u'kamr:stockholm',
            u'Kammarr\xe4tten i Sundsvall':       u'kamr:sundsvall',
            u'Arbetsdomstolen':                   u'ad',
            u'Högsta domstolen':                  u'hd',
            u'Regeringsrätten':                   u'regr',
            u'Patentbesvärsrätten':               u'pbr',
            u'Rättshjälpsnämnden':                u'rhn',
            u'Miljööverdomstolen':                u'möd',
             }
        idfield = {
            u'Marknadsdomstolen':                 u'Domsnummer',
            u'Hovrätten för Övre Norrland':       u'Målnummer',
            u'Hovrätten för Nedre Norrland':      u'Målnummer',
            u'Hovrätten över Skåne och Blekinge': u'Målnummer',
            u'Svea hovrätt':                      u'Målnummer',
            u'Hovrätten för Västra Sverige':      u'Målnummer',
            u'G\xf6ta hovr\xe4tt':                u'Målnummer',
            u'Kammarr\xe4tten i G\xf6teborg':     u'Målnummer',
            u'Kammarr\xe4tten i J\xf6nk\xf6ping': u'Målnummer',
            u'Kammarr\xe4tten i Stockholm':       u'Målnummer',
            u'Kammarr\xe4tten i Sundsvall':       u'Målnummer',
            u'Arbetsdomstolen':                   u'Domsnummer',
            u'Högsta domstolen':                  u'Målnummer',
            u'Regeringsrätten':                   u'Målnummer',
            u'Patentbesvärsrätten':               u'Målnummer',
            u'Rättshjälpsnämnden':                u'Diarienummer',
            u'Miljööverdomstolen':                u'Målnummer',
            }
        domstol = data['Domstol']
        urn = "urn:x-dom:%s:%s" % (domstolar[domstol], data[idfield[domstol]])
        return urn

class DVManager(LegalSource.Manager):
    def __init__(self,baseDir):
        self.baseDir = baseDir
        
    def parseAll(self):
        downloadDir = self.baseDir + "/dv/downloaded"
        for f in Util.numsort(os.listdir(downloadDir)):
            if f.endswith("detalj.html"):
                id = f[:-12]
                filePair = {"detalj":downloadDir + "/" + f}
                if os.path.exists(downloadDir + "/" + id + ".referat.html"):
                    filePair['referat'] = downloadDir + "/" + id + ".referat.html"
                p = DVParser(id, filePair, self.baseDir)
                t = p.parse()
                print "id:%s\turn: %s" % (p.id, t.getroot().attrib['urn'])
        
class TestDVCollection(unittest.TestCase):
    baseDir = "testdata"
    def testParse(self):
        #dc = DVCollection("testdata")
        #dc.parseAll()
        dp = DVParser("282", {'detalj':'testdata/dv/downloaded/282.detalj.html',
                              'referat':'testdata/dv/downloaded/282.referat.html'},
        'testdata')
        dp.parse()
        

                
if __name__ == "__main__":
    unittest.main()
