This is the source code for lagen.nu 2.0 (or at least it will be)


tankar.txt
bDet globala formatet

* Formatet kommer bygga p� ett antal olika namespaces.
* Det m�ste g� f�r en tredjepart att bygga valida dokument utan att
  n�n sorts globalt "master-schema" ska �ndras. Denna tredje part f�r
  bygga ett eget schema med de taggar han beh�ver, och referera till
  det genom l�mpligt namespace.
* Den t�nkta annoteringstill�mpningen ska, �tminstone backendm�ssigt,
  g� att bygga p� godtyckligt dokument vars ing�ende schemata f�ljer
  n�gra enkla grundl�ggande regler.
* Huvud-namespacet har mycket f� taggar. �n s� l�nge:
  * document
  * id (kanske ett "type"-attribut?)
  * baseurl ?
* Huvud-namespacet har tv� attribut ("structure" och "meaning"), som
  h�ngs p� taggar fr�n andras namespace, f�r att tala om ungef�r
  vilken klass av data det �r fr�gan om:

  <ec:preamble-note id="1" legal:structure="paragraph">
     I f�rdraget f�reskrivs uppr�ttandet...
  </ec:preamble-note>

  structure-attributet talar om vilken sorts typografisk/strukturell
  h�rad vi r�r oss i, och meaning-attributet talar om vad noden har
  f�r juridisk betydelse (best�mmande, f�rklarande, metadata etc) --
  det h�r skulle g�ra det m�jligt/enklare att implementera generell
  annotering.

  
L�nk-schemat:
* Ett typ-attribut f�r att ange vilken "familj" av dokument man l�nkar
  till. "EC" f�r all EG-r�tt (f�rdrag, direktiv, domslut), "SE" f�r
  allt inom svensk lagstiftning etc, "UN", "WIPO", "ILO" etc f�r
  internationella organisationers dokument.

Fotn�tter:
* En tag (note) vars inneh�ll kan vara godtycklig PCDATA. Fotnottexten
  l�ggs inline i dokumentet. id-attribut
  
SFS-schemat:

* Det �r OK med svenska tecken i taggarna
* Det �r OK att plocka bort tecken som �r rent strukturb�rande. Exv i "2
  Kap. Inskr�kningar i ..." s� �r det OK att plocka bort "2 Kap. ", s�
  l�nge som siffran 2 bevaras i ett ID-attribut. Samma sak med sj�lva
  "�"-tecknet. 

? Ska vi m�rka upp meningar (<sfs:mening>S�som
  framst�llning...</sfs:mening>) -- referenser kan ju vara
  p� formen "f�rsta stycket, tredje meningen"
? �r �verg�ngsbest�mmelser en del av den konsoliderade lagtexten,
  �r det metainformation, �r det ett eget namespace?
? Bilagor som �r andra r�ttsk�llor (Europakonventionen etc), ska vi
  tvinga in dem i SFS-schemat (kan g� att g�ra automatiskt med lite
  sl� heuristik) eller l�gga in en r�ttsk�llespecifik version (kr�ver
  minst lite manuell handp�l�ggning)

SFS-meta-schemat:

* T�nkt f�r saker som finns i Rixlex och i lagtext, men som inte �r
  betydelseb�rande. Exempelvis "�ndring inf�rd: t.o.m. SFS 2000:665" i
  preambeln, eller "Lag (1994:190)." i slutet av vissa paragrafer.

EG-r�tt:

* Alla taggar �r p� engelska.
* xml:lang-attributet anv�nds, helst p� toppniv�
* preamble-note: en f�r varje numrerat stycke, paragraph anv�nds f�r
  de onumrerade innan.
* punktlistor i direktiv kan n�stlas; den f�rsta niv�n �r siffror, den
  andra bokst�ver. Den f�rsta niv�n avskils fr�n resten av texten med
  punkt ("1. ") den andra med h�gerparantes ("2) "). Vi plockar bort
  det h�r separatortecknet.
  

? Preambeln: Ska numreringen "(12)" ligga i texten, eller ska numret
  l�ggas i ett id-attribut?
? De stycken i ett direktiv som traditionellt skrivs i versaler (exv
  kapitelrubriker), �r det OK att lowercasa dem?
? vad ska vi kalla det som f�ljer preambeln? body?
? �r det ok att g�ra om "KAPITEL II\n\nR�TTIGHETER OCH UNDANTAG" till
  <ec:chapter id="2" title="R�TTIGHETER OCH UNDANTAG">
? F�ljs artiklarna *alltid* av en rubrik? �r det ok att transformera
  "Artikel 4\n\nSpridningsr�tt" till <ec:article id="4"
  title="Spridningsr�tt">
? �r de numrerade punkter som f�rekommer under direktiven verkligen
  att beteckna som numrerade punktlistor, p� samma s�tt som de
  bokstavsnumrerade punktlistor som ibland kommer p� l�gre
  niv�. typografin i PDF'en antyder mer att det skulle vara
  styckeidentifierare (f�rutom att en del har flera faktiska stycken)
    
Domslut-schemat:

* �r skillnaden mellan HD och AD-domar f�r stora f�r att f� plats i
  ett schema? Vilka gemensamma n�mnare finns?
* Hur hanterar vi en NJA-publicerad dom med referat till HovR och
  TR-domarna?

arkitektur.txt

Arkitektur f�r lagen.nu 2.0

Systemet byggs upp kring en serie r�ttsk�llor, d�r de viktigaste �r:

* Svensk lagtext (SFS)
** Ska vi g�ra skillnad p� konsoliderad lagtext och
   �ndringsf�rfattningar? Ska vi �ht addressera det senare problemet?
* svenska f�rarbeten (Prop, SOU/DS och ev kommitt�direktiv,
  utskottsbet�nkanden och riksdagsskrivelser)
* Svenska r�ttsfall
* Europeiska direktiv
* R�ttsfall fr�n europadomstolen
* Enstaka one-off-dokument (genevekonventionen, FN's barnkonvention,
  Europeiska konventionen om de m�nskliga r�ttigheterna, WIPOs
  romkonvention...)

F�r varje r�ttsf�lla byggs fyra komponenter

* Ett RelaxNG-schema i ferenda-familjen som kan uttrycka de dokument
  som ing�r i r�ttsk�llan. I detta arbete ing�r ocks� ett kanoniskt
  s�tt att identifiera dokumenten, samt hur de lagras p� lokal disk.
* En "grabber" -- denna ska kunna h�mta namngivna dokument genom de ID
  som best�ms ovan, samt �ven g�ra operationen "h�mta alla nytillkomna
  dokument". Dokumenten sparas i samma form som de ligger ute p� n�tet
  eller var de nu ligger n�nstans, dvs HTML, word, PDF, whatever.
* En "parser" -- denna tar dokument som ligger p� disk och g�r
  ferenda-XML av dem. Det kan ibland betyda att g�ra ett m�ldokument
  av flera k�lldokument eller vice versa.
* Ett "site manager"-komponent -- denna �r ansvarig f�r att ta
  ferenda-XML-dokument och g�ra HTML av dem, vilket s� l�ngt som
  m�jligt kommer innefatta en XSLT-transformation. Den h�r komponenten
  kommer f�rmodligen arbeta tight ihop med "site manager"-komponenter
  f�r andra r�ttsk�llor.
  
Grabbers, parser och site managers ska vara l�st kopplade och kan
implementeras i olika spr�k. grabbers och parsers kan tillochmed
ers�ttas av mankraft.

  
main.py
# Varje r�ttsk�lletyp hanteras av en separat modul
# Exempel p� r�ttsk�llor: svenska f�rfattningar, svenska domslut (ska de delas
# upp i AD-domar, MD-domar, f�rvaltnings, vanliga etc)?, myndighetsyttranden
# (JO, ARN etc), f�rarbeten, doktrin (b�cker, tidskrifter), EG-direktiv/f�rdrag,
# internationella konventioner, osv osv.

# En r�ttsk�llemodul ska kunna
# * Ladda ner de senaste versionerna av r�materialet p� ett bandbreddseffektivt s�tt
# * Konvertera r�materialet till XML
# * Tala om vilka r�ttsk�lledokument som finns (vad inneb�r detta f�r doktrin?)
#   * Inkl de 50 senaste/de nytillkomna eller uppdaterade den senaste veckan
# * (ev) konvertera r�ttsk�lledokument till XHTML och XSL-FO

# R�ttsk�llehierarki (anpassad efter r�ttsk�llornas faktiska egenskaper som
# de publiceras p� n�tet - exv g�rs ingen skillnad p� svenska lagar och
# svenska f�rfattningar)
# - f�rfattningar
# - domar
# -- HD / HovR / TR
# -- RegR / KamR / LR
# -- AD 
# - myndighetsbeslut
# -- JO
# -- ARN
# - f�rarbeten
# -- Direktiv
# -- Del/slutbet�nkande (SOU/Ds)
# -- Proposition
# -- Utskottsbet�nkande
# - doktrin
# -- monografier
# -- artiklar (i tidskrift eller samlingsvolym)
# - EG-r�ttsakter
# -- F�rdrag
# -- Direktiv
# -- F�rordning
# - Internationella konventioner

# En r�ttsk�lletyp kan vara: statisk (dom) eller updaterbar (f�rfattning)
#    en �ndringsf�rfattning �r statisk
# En r�ttsk�lla kan vara bibliografisk (bara metadata) eller 
# En r�ttsk�lla har: minst en unik identifierare (r�ttsk�llespecifik) inom ett visst
# namespace ("urn:sfs:1960:729" eller "urn:celex:C34000420240",
# "urn:doktrin:jt2004/05s123"). Det finns inte n�dv�ndigtvis en 1:1 mappning
# mellan namespace och r�ttsk�lla. Ett 

# kontrollprogrammet ska kunna
# * hitta alla r�ttsk�llemoduler
# * be dem uppdatera r�materialet
# * be dem konvetera till XML
# * 



