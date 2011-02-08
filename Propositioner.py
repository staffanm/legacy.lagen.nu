#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import re

from Regeringen import Regeringen

class PropPolo(Regeringen):
    module_dir = "prop-polo"
    re_basefile_strict = re.compile(r'Prop. (\d{4}/\d{2,4}:\d+)')
    re_basefile_lax = re.compile(r'(?:Prop\.?|) ?(\d{4}/\d{2,4}:\d+)', re.IGNORECASE)
    
    def __init__(self,options):
        super(PropPolo,self).__init__(options) 
        self.document_type = self.PROPOSITION

    def generic_path(self,basefile,maindir,suffix):
        super(PropPolo,self).generic_path(basefile.replace("/","-"),maindir,suffix)
        
if __name__ == "__main__":
    PropPolo.run()
