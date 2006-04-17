#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
"""High-level classes that coordinates various Downloaders, Parsers
and Renderers to create the static HTML files and other stuff"""


class ParseManager:
    """Given a directory prepared by a Downlader, iterates and calls
    the appropriate Parser for each downloaded LegalSource"""
    def __init__(self,dir,parserClass,baseDir):
        self.indexTree = ET.ElementTree(file=dir+"/index.xml")
        for node in self.indexTree.getroot():
            parser = parserClass(node.get("id"), dir + "/" + node.get("localFile"),baseDir)
            parser.parse()

