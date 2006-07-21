#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Hanterar domslut (detaljer och referat) från Domstolsverket, www.rattsinfosok.dom.se

Modulen hanterar omvandlande av domslutsdetaljer och -referat till XML
"""
# system libraries
import sys, os, re
#import unittest
import pprint
import types
import codecs
from cStringIO import StringIO

# 3rdparty libs
sys.path.append('3rdparty')
import BeautifulSoup
import elementtree.ElementTree as ET

# my libs
import LegalSource
from LegalRef import SFSRefParser,PreparatoryRefParser,ParseError
import Util
from DispatchMixin import DispatchMixin

# Django stuff
from DocComments import AnnotatedDoc
os.environ['DJANGO_SETTINGS_MODULE'] = 'ferenda.settings'
from ferenda.docview.models import Relation, LegalDocument

__version__ = (0,1)
__author__  = "Staffan Malmgren <staffan@tomtebo.org>"
__shortdesc__ = "Domslut (detaljer och referat)"
__moduledir__ = "dv"

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
    #def __init__(self,id,files,baseDir):
        #self.id = id
        #self.dir = baseDir + "/dv/parsed"
        #if not os.path.exists(self.dir):
            #Util.mkdir(self.dir)
        #self.files = files

    def Parse(self,id,files):
        import codecs
        self.id = id
        self.files = files
        soup = self.LoadDoc(self.files['detalj'][0])
        data = {}
        for row in soup.first('td', 'sokmenyBkgrMiddle').table:
            key = val = ""
            if len(row) > 3:
                key = row('td')[1].string.strip()
                if key == "":
                    key = lastkey
                if key[-1] == ":":
                    key = key[:-1]
                key = key.replace(" ", "-")
                val = self.ElementText(row('td')[2])

                #if val[:8] == "&#8226; ":
                #    val = val[8:]
                if val[:2] == u'\u2022 ':
                    val = val[2:]
                lastkey = key
                if val != '-':
                    # some keys are processed further
                    if key == u'Lagrum':
                        print u'parsing %r with lawparser' % val
                        parsed = SFSRefParser("<Lagrum>"+val+"</Lagrum>").parse()
                        val = ET.fromstring(parsed.encode('utf-8'))
                    elif key == u'Referat' and self.re_NJAref.match(val):
                        m = self.re_NJAref.match(val)
                        val = m.group(1)
                        data["Alt"+key] = m.group(2)

                    if key in data:
                        if type(data[key]) == types.ListType:
                            data[key].append(val)
                        else:
                            data[key] = [data[key],val]
                    else:
                        data[key] = val

        urn = self.__createUrn(data)

        referat = []
        if 'referat' in self.files and self.files['referat']:
            soup = self.LoadDoc(self.files['referat'][0])
            if soup.first('span', 'riDomstolsRubrik'):
                ref_domstol_node = soup.first('span', 'riDomstolsRubrik').findParent('td')
            elif soup.first('td', 'ritop1'):
                ref_domstol_node = soup.first('td', 'ritop1')
            else:
                raise LegalSource.ParseError("Kunde inte hitta domstolsnamnet i %s" % self.files['referat'])
            ref_domstol = self.ElementText(ref_domstol_node)
            ref_refid = self.ElementText(ref_domstol_node.findNextSibling('td'))
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
                referat.append(self.ElementText(p))

            ref_sokord = self.ElementText(soup.firstText(u'Sökord:').findParent('td').nextSibling.nextSibling)
            ref_sokord_arr = [self.NormalizeSpace(x) for x in self.re_delimSplit(ref_sokord)]
            ref_sokord_arr.sort()
            if not u'Sökord' in data:
                data_sokord_arr = []
            elif type(data[u'Sökord']) == types.ListType:
                data_sokord_arr = data[u'Sökord']
            else:
                data_sokord_arr = [data[u'Sökord']]

            data_sokord_arr.sort()
            if data_sokord_arr != ref_sokord_arr:
                print u"WARNING (Sokord): '%r' != '%r'" % (";".join(data_sokord_arr), ";".join(ref_sokord_arr))
                data[u'Sökord'] = Util.uniqueList(ref_sokord_arr, data_sokord_arr)
                
                print u" --- combining to '%r'" % ";".join(data[u'Sökord'])
            if soup.firstText(u'Litteratur:'):
                ref_litteratur = self.ElementText(soup.firstText(u'Litteratur:').findParent('td').nextSibling.nextSibling)
                data['Litteratur'] = [self.NormalizeSpace(x) for x in ref_litteratur.split(";")]

        root = ET.Element("Dom")
        root.attrib['urn'] = urn
        meta = ET.SubElement(root,"Metadata")
        for k in data.keys():
            if type(data[k]) == types.ListType:
                for i in data[k]:
                    node = ET.SubElement(meta,k)
                    if isinstance(i,ET._ElementInterface):
                        node.text = i.text
                        node[:] = i[:]
                    else:
                        node.text = i
            else:
                node = ET.SubElement(meta,k)
                if isinstance(data[k],ET._ElementInterface):
                    node.text = data[k].text
                    node[:] = data[k][:]
                else:
                    node.text = data[k]
        if referat:
            ref = ET.SubElement(root,"Referat")
            for p in referat:
                node = ET.SubElement(ref,"p")
                node.text = p
            
        tree = ET.ElementTree(root)
        buf = StringIO()
        
        #f = codecs.getwriter('iso-8859-1')(buf)
        # tree.write doesn't create initial '<?xml version=1.0 encoding='...'?>' so we add it ourselves to avoid problems with xmllint
        buf.write('<?xml version="1.0" encoding="utf-8"?>')        
        tree.write(buf,'utf-8')
        return buf.getvalue()

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
    __parserClass = DVParser
    
    def Parse(self,id):
        """'id' here is a single digit representing the filename on disc, not
        any sort of inherit case id or similarly"""
        files = {'detalj':self.__listfiles('detalj',id),
                 'referat':self.__listfiles('referat',id)}
        print("Files: %r" % files)
        p = self.__parserClass()
        parsed = p.Parse(id,files)
        filename = "%s/%s/parsed/%s.xml" % (self.baseDir, __moduledir__, id)
        Util.mkdir(os.path.dirname(filename))
        print "saving as %s" % filename
        out = file(filename, "w")
        out.write(parsed)
        out.close()
        Util.indentXmlFile(filename)
        
    def ParseAll(self):
        downloadDir = self.baseDir + "/dv/downloaded"
        for f in Util.listDirs(downloadDir,"detalj.html"):
            id = os.path.basename(f)[:-12]
            self.Parse(id)
    
    def Index(self,id):
        xmlFileName = self.__xmlFileName(id)
        root = ET.ElementTree(file=xmlFileName).getroot()
        title = root.findtext(u'Metadata/Rubrik')
        print "%d: %s" % (len(title.encode('utf-8')), id)
        return
        displayid = root.findtext(u'Metadata/Referat')
        if not displayid:
            displayid = root.findtext(u'Metadata/Målnummer')
        urn = root.get('urn')
        print "indexing %s (displayid: %s, id: %s)" % (urn,displayid,id)
        d = LegalDocument.objects.get_or_create(urn = urn.encode('utf-8'))
        d = LegalDocument.objects.get(urn = urn.encode('utf-8'))
        d.displayid = displayid.encode('utf-8')
        d.title = root.findtext(u'Metadata/Rubrik').encode('utf-8')
        d.htmlpath = self.__htmlFileName(id)
        d.xmlpath = xmlFileName
        d.save()
            
    def IndexAll(self):
        self.__doAllParsed(self.Index)

    def __doAllParsed(self,method):
        for f in Util.listDirs(self.baseDir+"/dv/parsed",'xml'):
            id = os.path.splitext(os.path.basename(f))[0]
            method(id)
    
    def __htmlFileName(self,id):
        return "%s/%s/generated/%s.html" % (self.baseDir, __moduledir__,id)

    def __xmlFileName(self,id):
        return "%s/%s/parsed/%s.xml" % (self.baseDir, __moduledir__,id)
        
    
    def __listfiles(self,suffix,id):
        filename = "%s/%s/downloaded/%s.%s.html" % (self.baseDir,__moduledir__,id,suffix)
        return [f for f in (filename,) if os.path.exists(f)]
        
    def Generate(self,id):
        infile = "%s/%s/parsed/%s.xml" % (self.baseDir, __moduledir__,id)
        outfile = "%s/%s/generated/%s.html" % (self.baseDir, __moduledir__,id)
        Util.mkdir(os.path.dirname(outfile))
        print "Transforming %s > %s" % (infile,outfile)
        Util.transform("xsl/dv.xsl",
                       infile,
                       outfile,
                       {},
                       validate=False)
        print "Generating index for %s" % outfile
        ad = AnnotatedDoc(outfile)
        ad.Prepare()
        print "Creating intrinsic relations for %s" % id
        self.__createRelations(infile)

    
    def __createRelations(self,xmlFileName):
        tree = ET.ElementTree(file=xmlFileName)
        urn = tree.getroot().get('urn')
        
        # delete all previous relations where this document is the object --
        # maybe that won't be needed if the typical GenerateAll scenario
        # begins with wiping the IntrinsicRelation table? It still is useful 
        # in the normal development scenario, though
        IntrinsicRelation.objects.filter(object__exact=urn.encode('utf-8')).delete()    
        for e in tree.getiterator():
            if e.tag == u'Referat':
                if e.text.strip():
                    self.createRelation(urn,u'kallas',e.text)
            if e.tag == u'Sökord':
                if e.text:
                    self.createRelation(urn,u'behandlar',e.text)
            if e.tag == u'Rättsfall':
                try:
                    self.createRelation(urn,u'refererar',self.findURN(e.text))
                except LegalSource.URNNotFound:
                    print "WARNING: no URN found for %r" % e.text
                    pass
            if e.tag == u'Lagrum':
                for link in e:
                    if link.tag == 'link' and link.attrib['law']:
                        self.createRelation(urn,u'åberopar',self.__createSFSUrn(link))
    
    def __createSFSUrn(self,el):
        res = u'urn:x-sfs:%s#' % el.attrib['law']
        if 'chapter' in el.attrib:
            res = res + "K" + el.attrib['chapter']
        if 'section' in el.attrib:
            res = res + "P" + el.attrib['section']
        if 'piece' in el.attrib:
            res = res + "S" + el.attrib['piece']
        if 'item' in el.attrib:
            res = res + "N" + el.attrib['item']
        if res.endswith("#"):
            res = res[:-1]
        return res
        
        
    

    def GenerateAll(self):
        self.__doAllParsed(self.Generate)
       

                
if __name__ == "__main__":
    if not '__file__' in dir():
        print "probably running from within emacs"
        sys.argv = ['DV.py','Parse', '42']
    
    DVManager.__bases__ += (DispatchMixin,)
    mgr = DVManager("testdata")
    # print "argv: %r" % sys.argv   
    mgr.Dispatch(sys.argv)
