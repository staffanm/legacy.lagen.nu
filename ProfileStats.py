#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import hotshot.stats
if __name__ == "__main__":
    stats = hotshot.stats.load(sys.argv[1])
    stats.strip_dirs()
    stats.sort_stats('time','calls')
    stats.print_stats(30)
