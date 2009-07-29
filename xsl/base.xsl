<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		exclude-result-prefixes="xht2">
  <xsl:param name="infile">unknown-infile</xsl:param>
  <xsl:param name="outfile">unknown-outfile</xsl:param>

  <xsl:output method="xml"
  	    doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
  	    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	    indent="yes"
	    />

  <!--
      we'd like to use the following doctype, since we're not valid
      w/o it, but IE brings up blank pages when using it (as do FF if
      we're not using application/xhtml+xml) - wonder how eurlex.nu
      does it? -->
  <!--
  <xsl:output method="xml"
	      doctype-public="-//W3C//DTD XHTML+RDFa 1.0//EN"
	      doctype-system="http://www.w3.org/MarkUp/DTD/xhtml-rdfa-1.dtd"
	      indent="yes"
	    />
  -->

  <!-- these minimal RDF files is only used to know wheter we have a
       specific case (and therefore should link it) or keyword, so
       that we can know when to link to it -->
  
  <xsl:variable name="rattsfall" select="document('../data/dv/parsed/rdf-mini.xml')/rdf:RDF"/>
  <xsl:variable name="terms" select="document('../data/keyword/parsed/rdf-mini.xml')/rdf:RDF"/>
  <xsl:variable name="lagkommentar" select="document('../data/sfs/parsed/rdf-mini.xml')/rdf:RDF"/>

  <xsl:param name="annotationfile"/>
  <xsl:variable name="annotations" select="document($annotationfile)/rdf:RDF"/>
  <!--<xsl:variable name="annotations"> <hello>world</hello>
       </xsl:variable>
  -->
  <xsl:template match="/">
    <!--<xsl:message>Root rule</xsl:message>-->
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="xht2:html">
    <!--<xsl:message>base/root</xsl:message>-->
    <html xml:lang="sv"><xsl:apply-templates/></html>
  </xsl:template>
    
  <xsl:template match="xht2:head">
    <!--<xsl:message>base/head</xsl:message>-->
    <head>
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
      <title><xsl:call-template name="headtitle"/></title>
      <xsl:call-template name="metarobots"/>
      <script type="text/javascript" src="/js/jquery-1.2.6.min.js"></script>
      <script type="text/javascript" src="/js/jquery-ui-personalized-1.6rc2.min.js"></script>
      <script type="text/javascript" src="/js/jquery.treeview.min.js"></script>
      <!--
      <script type="text/javascript" src="/js/jquery.autocomplete.min.js"></script>
      <script type="text/javascript" src="/js/localdata.js"></script>
      -->
      <script type="text/javascript" src="/js/base.js"></script>
      <link rel="shortcut icon" href="/img/favicon.ico" type="image/x-icon" />
      <link rel="stylesheet" href="/css/screen.css" title="Times" media="screen" type="text/css"/> 
      <link rel="alternate stylesheet" href="/css/alt-georgia.css" title="Georgia" media="screen" type="text/css"/> 
      <link rel="alternate stylesheet" href="/css/alt-verdana.css" title="Verdana" media="screen" type="text/css"/> 
      <link rel="alternate stylesheet" href="/css/alt-calibri.css" title="Calibri" media="" type="text/css"/> 
      <link rel="alternate stylesheet" href="/css/alt-cambria.css" title="Cambria" media="" type="text/css"/> 

      <link rel="stylesheet" href="/css/screen.css" media="screen" type="text/css"/> 
      <link rel="stylesheet" href="/css/print.css" media="print" type="text/css"/> 
      <xsl:call-template name="linkalternate"/>
      <xsl:call-template name="headmetadata"/>
    </head>
  </xsl:template>

  <xsl:template match="xht2:body">
    <!--<xsl:message>base/body</xsl:message>-->
    <body>
      <xsl:if test="//xht2:html/@about">
	<xsl:attribute name="about"><xsl:value-of select="//xht2:html/@about"/></xsl:attribute>
      </xsl:if>

      <xsl:attribute name="typeof"><xsl:value-of select="@typeof"/></xsl:attribute>

      
      <xsl:comment>[if lte IE 6]&gt;
	  &lt;style type="text/css"&gt;
	    #ie6msg{border:3px solid #090; margin:8px 0; background:#cfc; color:#000;}
	    #ie6msg h4{margin:8px; padding:0;}
	    #ie6msg p{margin:8px; padding:0; font-size: smaller;}
	    #ie6msg p a.getie7{font-weight:bold; color:#006;}
	    #ie6msg p a.ie6expl{font-weight:normal; color:#006;}
	  &lt;/style&gt;
	  &lt;div id="ie6msg"&gt;
	    &lt;h4&gt;Du har en gammal version av webbläsaren Internet Explorer.&lt;/h4&gt;
	    &lt;p&gt;
	      Det kan hända att sidan på grund av detta ser konstig ut, med överlappande text eller andra problem. 
              För att få en bättre och säkrare upplevelse på nätet
	      rekommenderar vi att du &lt;a class="getie7"
	      href="http://www.microsoft.com/sverige/windows/downloads/ie/getitnow.mspx"&gt;hämtar
	      en nyare version av Internet
	      Explorer&lt;/a&gt;. Uppgraderingen är kostnadsfri.  Sitter du
	      på jobb och inte har kontroll över din dator själv bör
	      du kontakta din IT-ansvarige.
	    &lt;/p&gt;
	    &lt;p&gt;
	      Vi kan också rekommendera dig att prova någon av följade
	      alternativa
	      webbläsare &lt;a href="http://mozilla.com"&gt;Firefox&lt;/a&gt;, 
              &lt;a href="http://www.google.com/chrome"&gt;Chrome&lt;/a&gt;, 
	      &lt;a href="http://www.apple.com/safari/download/"&gt;Safari&lt;/a&gt;
	      eller &lt;a href="http://www.opera.com"&gt;Opera&lt;/a&gt;.
	    &lt;/p&gt;
	    &lt;p&gt;
	      Den här uppmaningen har sitt ursprung i Norge och på en
	      av deras största sajter, finn.no, kan du läsa om
	      &lt;a class="ie6expl"
	      href="http://labs.finn.no/blog/finn-anbefaler-ie6-brukere-a-oppgradere-sin-nettleser"&gt;varför
              du bör uppgradera&lt;/a&gt;. Du kan även läsa
	      en &lt;a class="ie6expl" href="http://mindpark.se/2009/02/18/heja-norge/"&gt;bakgrund
	      till uppmaningen på svenska här&lt;/a&gt;.
	    &lt;/p&gt;
	  &lt;/div&gt;
	  &lt;![endif]</xsl:comment>

      <div id="vinjett">
	<img src="/img/blueprint.jpg" alt=""/>
	<h1><a href="/">lagen.nu</a></h1>
	<ul id="navigation">
	  <li><a href="/nyheter/">Nyheter</a></li>
	  <li><a href="/index/">Lagar</a></li>
	  <li><a href="/dom/index/">Domar</a></li>
	  <li><a href="/begrepp/index/">Begrepp</a></li>
	  <li><a href="/om/">Om</a></li>
	</ul>
	<form method="get" action="http://www.google.com/custom">
	  <p>
	    <span class="accelerator">S</span>ök:<input type="text" name="q" id="q" size="40" maxlength="255" value="" accesskey="S"/>
	    <input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;"/>
	    <input type="hidden" name="domains" value="lagen.nu"/>
	    <input type="hidden" name="sitesearch" value="lagen.nu" checked="checked"/>
	  </p>
	</form>
	<ul id="sss">
	  <li><a href="#" class="Times" title="Använd typsnitt: Times" onclick="switchStylestyle('Times'); return false;">Abc</a></li>
	  <li><a href="#" class="Verdana" title="Använd typsnitt: Verdana" onclick="switchStylestyle('Verdana'); return false;">Abc</a></li>
	</ul>

      </div>
      <div id="colmask" class="threecol">
	<div id="colmid">
	  <div id="colleft">
	    <div id="dokument">
	      <xsl:apply-templates/>
	    </div>
	    <div id="kommentarer">
	      <xsl:apply-templates mode="kommentarer"/>
	      <!--
	      <p class="bugreport-link">Ser sidan konstig ut? Hjälp
	      mig att göra tjänsten bättre genom en felanmälan!</p>
	      <form class="bugreport-form" action="http://trac.lagen.nu/newticket" method="get">
		<p>
		  <input type="hidden" name="summary" value="Felanmälan {$outfile}" />
		  Din epostadress (inte obligatoriskt, men bra om jag ska
		  kunna meddela dig att felet åtgärdats):<br/>
		  
		  <input type="text" id="author" name="author" value="" /><br/>
		  Beskrivning av problemet: <br/>
		  <textarea name="description" rows="8"></textarea><br/>
		  
		  Tips för en bra felanmälan: Beskriv <i>var</i> på sidan
		  problemet är, det <i>förväntade</i> utseendet, och
		  det <i>faktiska</i> utseendet.<br/>
		  
		  <input type="submit" name="submit" value="Felanmäl" />
		</p>
	      </form>
	      -->
	    </div>
	    <div id="referenser">
	      <xsl:apply-templates mode="refs"/>
	    </div>
	  </div>
	</div>
      </div>
      <div id="sidfot">
	<b>Lagen.nu</b> är en privat webbplats. Informationen här är
	inte officiell och kan vara felaktig | <a href="/om/ansvarsfriskrivning.html">Ansvarsfriskrivning</a> | <a href="/om/kontakt.html">Kontaktinformation</a>
      </div>
      <script type="text/javascript"><xsl:comment>
var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
      </xsl:comment></script>
      <script type="text/javascript"><xsl:comment>
var pageTracker = _gat._getTracker("UA-172287-1");
pageTracker._trackPageview();
      </xsl:comment></script>
    </body>
  </xsl:template>

  <!-- defaultimplementationer av de templates som anropas -->
  <!--
  <xsl:template name="headtitle">
    Lagen.nu - Alla Sveriges lagar på webben
  </xsl:template>
  <xsl:template name="linkrss"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="metarobots"/>
  <xsl:template name="headmetadata"/>
  -->
  
</xsl:stylesheet>
