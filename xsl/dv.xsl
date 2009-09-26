<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		exclude-result-prefixes="xht2 rdf">

  <xsl:import href="uri.xsl"/>
  <xsl:import href="accordion.xsl"/>
  <xsl:include href="base.xsl"/>

  <xsl:variable name="dokumenturi" select="/xht2:html/@xml:base"/>

  <xsl:variable name="docmetadata">
    <dl id="refs-dokument">
      <dt>Domstol</dt>
      <dd rel="dct:creator" resource="{//xht2:dd[@rel='dct:creator']/@href}"><xsl:value-of select="//xht2:dd[@rel='dct:creator']"/></dd>
      <dt>Avgörandedatum</dt>
      <dd property="rinfo:avgorandedatum"><xsl:value-of select="//xht2:dd[@property='rinfo:avgorandedatum']"/></dd>
      <dt>Målnummer</dt>
      <dd property="rinfo:malnummer"><xsl:value-of select="//xht2:dd[@property='rinfo:malnummer']"/></dd>
      <xsl:if test="//xht2:a[@rel='rinfo:lagrum']">
	<dt >Lagrum</dt>
	<xsl:for-each select="//xht2:dd[xht2:a[@rel='rinfo:lagrum']]">
	  <dd><xsl:apply-templates select="."/></dd>
	</xsl:for-each>
      </xsl:if>
      
      <xsl:if test="//xht2:a[@rel='rinfo:rattsfallshanvisning']">
	<dt>Rättsfall</dt>
	<xsl:for-each select="//xht2:dd[xht2:a[@rel='rinfo:rattsfallshanvisning']]">
	  <dd><xsl:apply-templates select="."/></dd>
	</xsl:for-each>
      </xsl:if>
      
      <xsl:if test="//xht2:dd[@property='dct:relation']">
	<dt>Litteratur</dt>
	<xsl:for-each select="//xht2:dd[@property='dct:relation']">
	  <dd property="dct:relation"><xsl:value-of select="."/></dd>
	</xsl:for-each>
      </xsl:if>
      
      <xsl:if test="//xht2:dd[@property='dct:subject']">
	<dt>Sökord</dt>
	<xsl:for-each select="//xht2:dd[@property='dct:subject']">
	  <dd property="dct:subject"><a href="/begrepp/{.}"><xsl:value-of select="."/></a></dd>
	</xsl:for-each>
      </xsl:if>
      
      <dt>Källa</dt>
      <dd rel="dct:publisher" resource="http://lagen.nu/org/2008/domstolsverket" content="Domstolsverket"><a href="http://www.rattsinfosok.dom.se/lagrummet/index.jsp">Domstolsverket</a></dd>
    </dl>
  </xsl:variable>

  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/> | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate">
    <link rel="alternate" type="application/xml" title="XHTML2">
      <xsl:attribute name="href">/dom/<xsl:value-of select="substring-after(//xht2:html/@about,'publ/rattsfall/')"/>.xht2</xsl:attribute>
    </link>
  </xsl:template>
  <xsl:template name="headmetadata"/>

  <xsl:template match="xht2:dl[@role='contentinfo']"/>

  <xsl:template match="xht2:section[@role='main']">
    <!-- select $kommentarer and $inbound -->
    <table>
      <tr>
	<td width="66%">
	  <xsl:if test="//xht2:dd[@property='rinfoex:patchdescription']">
	    <p class="patchdescription">Texten har ändrats jämfört med ursprungsmaterialet: <xsl:value-of select="//xht2:dd[@property='rinfoex:patchdescription']"/></p>
	  </xsl:if>
	  <h1 property="dct:identifier"><xsl:value-of select="//xht2:dd[@property='dct:identifier']"/></h1>
	  <p property="dct:description" class="rattsfallsrubrik"><xsl:value-of select="//xht2:dd[@property='dct:description']"/></p>
	  <xsl:apply-templates/>
	</td>
	<td class="aux">
	  <div class="ui-accordion">
	    <xsl:call-template name="accordionbox">
	      <xsl:with-param name="heading">Metadata</xsl:with-param>
	      <xsl:with-param name="contents"><xsl:copy-of select="$docmetadata"/></xsl:with-param>
	    </xsl:call-template>

	    <xsl:call-template name="accordionbox">
	      <xsl:with-param name="heading">Rättsfallshänvisningar hit</xsl:with-param>
	      <xsl:with-param name="contents">...kommer snart</xsl:with-param>
	    </xsl:call-template>
	  </div>
	</td>
      </tr>
    </table>
  </xsl:template>
  
  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>


  <!-- defaultregel: kopierar alla element från xht2 till
       default-namespacet -->
  <xsl:template match="*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <xsl:template match="xht2:section[@role='main']" mode="toc">
    <h2>Innehållsförteckning</h2>
    <ul id="toc">
	<li>Om vi kan hitta</li>
	<li>strukturen i alla rättsfall</li>
	<li>Framförallt:
	<ul>
	  <li>De olika instanserna</li>
	  <li>men också rubriker inom ett domskäl</li>
	</ul>
	<li>Rent tekniskt ganska knepigt, men...</li>
	</li>
      </ul>
  </xsl:template>

  <xsl:template match="*" mode="toc"/>
  
</xsl:stylesheet>

