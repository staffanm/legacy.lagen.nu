#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# 1. l�s alla triples i dv/parsed/rdf.nt, f�r varje unik URI:
#     * hitta rinfo:rattsfallspublikation
#     * hitta alla rinfo:lagrum (felk�lla: h�nvisning till EG-r�tt,
#       myndighetsf�rfattningssamlingar etc kommer inte med). I parsesteget
#       kanske varje lagrumsrad som inte ger n�gon URI b�r resultera i en
#       str�ngliteraltriple ist�llet?
#     * hitta alla rinfo:rattsfallshanvisning
#     * hitta alla dct:relation och dela upp i f�rarbeten resp doktrin (och
#       ibland tydligen �ven r�ttsfall, se R� 2008 ref 10)
#
# 2. F�r alla fall inom en rinfo:rattsfallspublikation
#    * R�kna: antal lagrum, antal lagar, antal r�ttsfallsh�nvisningar, antal
#      f�rarbeten, antal doktrin.
#    * Sammanst�ll: Hur m�nga r�ttsfall hade en lagrumsh�nvisning? Tv�? Tre? osv
#
# Vy 1: F�rdelning av antal lagrum: en stapel med antal r�ttsfall som
# har noll lagrumsh�nvisningar, en stapel med antal r�ttsfall som har
# en lagrumsh�nvisning, osv. Samma f�r antal lagar, antal r�ttsfall,
# antal f�rarbetsh�nv. samt doktrinh�nv. KAnske en kumulativ?
#
# Vy 2: J�mf�rande mellan r�ttsk�llor �ver tid: Vad var snittantalet
# lagrumsh�nvisningar 1980? Vad var snittantalet
# r�ttsfallsh�nvisningar 1980? 1981? osv
#
# Vy 3: �lder: Hur m�nga h�nvisningar (inom en hel publ) �r 1 �r
# gamla? 2 �r? 3 �r?  Uppdelat p� h�nvisningstyp och kumulativt. F�r
# r�ttsfall, f�rarb. och kanske doktrin.
#
# Vy 4: F�rarbetstyper: Vilka h�nvisas till mest? Ds, Sou, prop, NJA II? �ver tid?
#
# Vy 5: F�rfattningstyper: Vilka f�rtfattningstyper, ut�ver SFS?
#
# Vy 6: Doktrintyper: B�cker, tidskrifter?
#
# Topplistor: Popul�st lagrum, lag, r�ttsfall, f�rarbete, bok, f�rfattare, tidskrift
