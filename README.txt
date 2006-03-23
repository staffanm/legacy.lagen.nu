This is the source code for lagen.nu 2.0 (or at least it will be)


tankar.txt
bDet globala formatet

* Formatet kommer bygga på ett antal olika namespaces.
* Det måste gå för en tredjepart att bygga valida dokument utan att
  nån sorts globalt "master-schema" ska ändras. Denna tredje part får
  bygga ett eget schema med de taggar han behöver, och referera till
  det genom lämpligt namespace.
* Den tänkta annoteringstillämpningen ska, åtminstone backendmässigt,
  gå att bygga på godtyckligt dokument vars ingående schemata följer
  några enkla grundläggande regler.
* Huvud-namespacet har mycket få taggar. Än så länge:
  * document
  * id (kanske ett "type"-attribut?)
  * baseurl ?
* Huvud-namespacet har två attribut ("structure" och "meaning"), som
  hängs på taggar från andras namespace, för att tala om ungefär
  vilken klass av data det är frågan om:

  <ec:preamble-note id="1" legal:structure="paragraph">
     I fördraget föreskrivs upprättandet...
  </ec:preamble-note>

  structure-attributet talar om vilken sorts typografisk/strukturell
  härad vi rör oss i, och meaning-attributet talar om vad noden har
  för juridisk betydelse (bestämmande, förklarande, metadata etc) --
  det här skulle göra det möjligt/enklare att implementera generell
  annotering.

  
Länk-schemat:
* Ett typ-attribut för att ange vilken "familj" av dokument man länkar
  till. "EC" för all EG-rätt (fördrag, direktiv, domslut), "SE" för
  allt inom svensk lagstiftning etc, "UN", "WIPO", "ILO" etc för
  internationella organisationers dokument.

Fotnötter:
* En tag (note) vars innehåll kan vara godtycklig PCDATA. Fotnottexten
  läggs inline i dokumentet. id-attribut
  
SFS-schemat:

* Det är OK med svenska tecken i taggarna
* Det är OK att plocka bort tecken som är rent strukturbärande. Exv i "2
  Kap. Inskräkningar i ..." så är det OK att plocka bort "2 Kap. ", så
  länge som siffran 2 bevaras i ett ID-attribut. Samma sak med själva
  "§"-tecknet. 

? Ska vi märka upp meningar (<sfs:mening>Såsom
  framställning...</sfs:mening>) -- referenser kan ju vara
  på formen "första stycket, tredje meningen"
? Är övergångsbestämmelser en del av den konsoliderade lagtexten,
  är det metainformation, är det ett eget namespace?
? Bilagor som är andra rättskällor (Europakonventionen etc), ska vi
  tvinga in dem i SFS-schemat (kan gå att göra automatiskt med lite
  slö heuristik) eller lägga in en rättskällespecifik version (kräver
  minst lite manuell handpåläggning)

SFS-meta-schemat:

* Tänkt för saker som finns i Rixlex och i lagtext, men som inte är
  betydelsebärande. Exempelvis "Ändring införd: t.o.m. SFS 2000:665" i
  preambeln, eller "Lag (1994:190)." i slutet av vissa paragrafer.

EG-rätt:

* Alla taggar är på engelska.
* xml:lang-attributet används, helst på toppnivå
* preamble-note: en för varje numrerat stycke, paragraph används för
  de onumrerade innan.
* punktlistor i direktiv kan nästlas; den första nivån är siffror, den
  andra bokstäver. Den första nivån avskils från resten av texten med
  punkt ("1. ") den andra med högerparantes ("2) "). Vi plockar bort
  det här separatortecknet.
  

? Preambeln: Ska numreringen "(12)" ligga i texten, eller ska numret
  läggas i ett id-attribut?
? De stycken i ett direktiv som traditionellt skrivs i versaler (exv
  kapitelrubriker), är det OK att lowercasa dem?
? vad ska vi kalla det som följer preambeln? body?
? Är det ok att göra om "KAPITEL II\n\nRÄTTIGHETER OCH UNDANTAG" till
  <ec:chapter id="2" title="RÄTTIGHETER OCH UNDANTAG">
? Följs artiklarna *alltid* av en rubrik? Är det ok att transformera
  "Artikel 4\n\nSpridningsrätt" till <ec:article id="4"
  title="Spridningsrätt">
? Är de numrerade punkter som förekommer under direktiven verkligen
  att beteckna som numrerade punktlistor, på samma sätt som de
  bokstavsnumrerade punktlistor som ibland kommer på lägre
  nivå. typografin i PDF'en antyder mer att det skulle vara
  styckeidentifierare (förutom att en del har flera faktiska stycken)
    
Domslut-schemat:

* Är skillnaden mellan HD och AD-domar för stora för att få plats i
  ett schema? Vilka gemensamma nämnare finns?
* Hur hanterar vi en NJA-publicerad dom med referat till HovR och
  TR-domarna?

arkitektur.txt

Arkitektur för lagen.nu 2.0

Systemet byggs upp kring en serie rättskällor, där de viktigaste är:

* Svensk lagtext (SFS)
** Ska vi göra skillnad på konsoliderad lagtext och
   ändringsförfattningar? Ska vi öht addressera det senare problemet?
* svenska förarbeten (Prop, SOU/DS och ev kommittédirektiv,
  utskottsbetänkanden och riksdagsskrivelser)
* Svenska rättsfall
* Europeiska direktiv
* Rättsfall från europadomstolen
* Enstaka one-off-dokument (genevekonventionen, FN's barnkonvention,
  Europeiska konventionen om de mänskliga rättigheterna, WIPOs
  romkonvention...)

För varje rättsfälla byggs fyra komponenter

* Ett RelaxNG-schema i ferenda-familjen som kan uttrycka de dokument
  som ingår i rättskällan. I detta arbete ingår också ett kanoniskt
  sätt att identifiera dokumenten, samt hur de lagras på lokal disk.
* En "grabber" -- denna ska kunna hämta namngivna dokument genom de ID
  som bestäms ovan, samt även göra operationen "hämta alla nytillkomna
  dokument". Dokumenten sparas i samma form som de ligger ute på nätet
  eller var de nu ligger nånstans, dvs HTML, word, PDF, whatever.
* En "parser" -- denna tar dokument som ligger på disk och gör
  ferenda-XML av dem. Det kan ibland betyda att göra ett måldokument
  av flera källdokument eller vice versa.
* Ett "site manager"-komponent -- denna är ansvarig för att ta
  ferenda-XML-dokument och göra HTML av dem, vilket så långt som
  möjligt kommer innefatta en XSLT-transformation. Den här komponenten
  kommer förmodligen arbeta tight ihop med "site manager"-komponenter
  för andra rättskällor.
  
Grabbers, parser och site managers ska vara löst kopplade och kan
implementeras i olika språk. grabbers och parsers kan tillochmed
ersättas av mankraft.

  
main.py
# Varje rättskälletyp hanteras av en separat modul
# Exempel på rättskällor: svenska författningar, svenska domslut (ska de delas
# upp i AD-domar, MD-domar, förvaltnings, vanliga etc)?, myndighetsyttranden
# (JO, ARN etc), förarbeten, doktrin (böcker, tidskrifter), EG-direktiv/fördrag,
# internationella konventioner, osv osv.

# En rättskällemodul ska kunna
# * Ladda ner de senaste versionerna av råmaterialet på ett bandbreddseffektivt sätt
# * Konvertera råmaterialet till XML
# * Tala om vilka rättskälledokument som finns (vad innebär detta för doktrin?)
#   * Inkl de 50 senaste/de nytillkomna eller uppdaterade den senaste veckan
# * (ev) konvertera rättskälledokument till XHTML och XSL-FO

# Rättskällehierarki (anpassad efter rättskällornas faktiska egenskaper som
# de publiceras på nätet - exv görs ingen skillnad på svenska lagar och
# svenska författningar)
# - författningar
# - domar
# -- HD / HovR / TR
# -- RegR / KamR / LR
# -- AD 
# - myndighetsbeslut
# -- JO
# -- ARN
# - förarbeten
# -- Direktiv
# -- Del/slutbetänkande (SOU/Ds)
# -- Proposition
# -- Utskottsbetänkande
# - doktrin
# -- monografier
# -- artiklar (i tidskrift eller samlingsvolym)
# - EG-rättsakter
# -- Fördrag
# -- Direktiv
# -- Förordning
# - Internationella konventioner

# En rättskälletyp kan vara: statisk (dom) eller updaterbar (författning)
#    en ändringsförfattning är statisk
# En rättskälla kan vara bibliografisk (bara metadata) eller 
# En rättskälla har: minst en unik identifierare (rättskällespecifik) inom ett visst
# namespace ("urn:sfs:1960:729" eller "urn:celex:C34000420240",
# "urn:doktrin:jt2004/05s123"). Det finns inte nödvändigtvis en 1:1 mappning
# mellan namespace och rättskälla. Ett 

# kontrollprogrammet ska kunna
# * hitta alla rättskällemoduler
# * be dem uppdatera råmaterialet
# * be dem konvetera till XML
# * 



