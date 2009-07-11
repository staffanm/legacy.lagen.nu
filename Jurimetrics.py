#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# 1. läs alla triples i dv/parsed/rdf.nt, för varje unik URI:
#     * hitta rinfo:rattsfallspublikation
#     * hitta alla rinfo:lagrum (felkälla: hänvisning till EG-rätt,
#       myndighetsförfattningssamlingar etc kommer inte med). I parsesteget
#       kanske varje lagrumsrad som inte ger någon URI bör resultera i en
#       strängliteraltriple istället?
#     * hitta alla rinfo:rattsfallshanvisning
#     * hitta alla dct:relation och dela upp i förarbeten resp doktrin (och
#       ibland tydligen även rättsfall, se RÅ 2008 ref 10)
#
# 2. För alla fall inom en rinfo:rattsfallspublikation
#    * Räkna: antal lagrum, antal lagar, antal rättsfallshänvisningar, antal
#      förarbeten, antal doktrin.
#    * Sammanställ: Hur många rättsfall hade en lagrumshänvisning? Två? Tre? osv
#
# Vy 1: Fördelning av antal lagrum: en stapel med antal rättsfall som
# har noll lagrumshänvisningar, en stapel med antal rättsfall som har
# en lagrumshänvisning, osv. Samma för antal lagar, antal rättsfall,
# antal förarbetshänv. samt doktrinhänv. KAnske en kumulativ?
#
# Vy 2: Jämförande mellan rättskällor över tid: Vad var snittantalet
# lagrumshänvisningar 1980? Vad var snittantalet
# rättsfallshänvisningar 1980? 1981? osv
#
# Vy 3: Ålder: Hur många hänvisningar (inom en hel publ) är 1 år
# gamla? 2 år? 3 år?  Uppdelat på hänvisningstyp och kumulativt. För
# rättsfall, förarb. och kanske doktrin.
#
# Vy 4: Förarbetstyper: Vilka hänvisas till mest? Ds, Sou, prop, NJA II? Över tid?
#
# Vy 5: Författningstyper: Vilka förtfattningstyper, utöver SFS?
#
# Vy 6: Doktrintyper: Böcker, tidskrifter?
#
# Topplistor: Populäst lagrum, lag, rättsfall, förarbete, bok, författare, tidskrift
