<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dc="http://purl.org/dc/elements/1.1/">
		<!-- fixme: change dc to dct -->
  <xsl:template match="xht2:html">
    <html><xsl:apply-templates/></html>
  </xsl:template>  

  <xsl:template match="xht2:head">
    <head>
      <title>[lagnamn] ([alternativform]) | Lagen.nu</title>
      <link rel="shortcut icon" href="http://lagen.nu/favicon.ico" type="image/x-icon" />
      <link rel="stylesheet" type="text/css" href="file://C|/Users/staffan/wds/ferenda.lagen.nu/css/default.css" />
      <xsl:comment>all övrig metadata</xsl:comment>
    </head>
  </xsl:template>

  <xsl:template match="xht2:body">
    <body>
      <div id="vinjett">
	<b>Vinjett text:</b> Lorem ipsum dolor sit amet, consectetuer
	adipiscing elit. Morbi ipsum nulla, tincidunt eu, varius in,
	sodales at, ipsum. Donec scelerisque. Integer congue
	adipiscing nisi. Suspendisse ligula magna, venenatis eu,
	condimentum et, viverra sed, est. Praesent nibh risus, euismod
	ut, ullamcorper ut, porta at, urna.
      </div>
      <div id="wrapper_extra">
	<div id="wrapper">
	  <div id="lagtext">
	    <xsl:apply-templates/>
	  </div>
	  <div id="kommentarer">
	    <div class="sidoruta">
	      &#160;
	    </div>
	  </div>
	  <div id="referenser">
	    <div class="sidoruta">
	      <p>Om dokumentet</p>
	      <xsl:apply-templates mode="refs"/>
	    </div>
	  </div>
	</div>
	<div id="sidfot">
	  <b>Lagen.nu:</b> Mauris non risus a nisi posuere
	  gravida. Morbi ut lacus. Nulla faucibus pulvinar ligula. Proin
	  mattis. Maecenas sagittis venenatis lorem. Praesent facilisis
	  posuere pede.
	</div>
      </div>
    </body>
  </xsl:template>
  
  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:dl[@class='metadata']">
    <!-- emit nothing -->
  </xsl:template>

  
  <xsl:template match="*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <xsl:template match="xht2:dl[@class='metadata']" mode="refs">
    <!-- Den stora metadata-definitionslistan innehåller en massa som
         inte är intressant att visa för slutanvändaren. Filtrera ut
         de intressanta bitarna -->
    <dl>
      <dt>Departement</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://dublincore.org/documents/dcmi-terms/creator']"/></dd>
      <dt>Utfärdad</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#utfardandedatum']"/></dd>
      <dt>Ändring införd t.o.m.</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#konsolideringsunderlag']"/></dd>
      <dt>Källa</dt>
      <dd><a href="">Regeringskansliets rättsdatabaser</a></dd>
      <dt>Senast hämtad</dt>
      <dd>...måste in i xht2-datan</dd>
    </dl>
  </xsl:template>

  <xsl:template match="*|@*" mode="refs">
    <!-- emit nothing -->
  </xsl:template>
</xsl:stylesheet>