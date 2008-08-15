<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dct="http://dublincore.org/documents/dcmi-terms/">

  <xsl:import href="uri.xsl"/>
  <xsl:include href="base.xsl"/>
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/> | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
      
  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']">
    <!-- plocka ut det gottaste från metadatat -->
    <h1><xsl:value-of select="xht2:dd[@property='dct:identifier']"/></h1>
    <p><b><xsl:value-of select="xht2:dd[@property='dct:description']"/></b></p>
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

  <!-- refs mode -->
  <xsl:template match="xht2:h" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']" mode="refs">
    <dl>
      <dt>Domstol</dt>
      <dd><xsl:value-of select="xht2:dd[@rel='dct:creator']"/></dd>
      <dt>Avgörandedatum</dt>
      <dd><xsl:value-of select="xht2:dd[@property='rinfo:avgorandedatum']"/></dd>
      <dt>Målnummer</dt>
      <dd><xsl:value-of select="xht2:dd[@property='rinfo:malnummer']"/></dd>
      <!-- <xsl:if test="xht2:a[@rel='rinfo:lagrum']">  -->
	<dt>Lagrum</dt>
	<xsl:for-each select="xht2:dd[xht2:a[@rel='rinfo:lagrum']]">
	  <dd><xsl:apply-templates select="."/></dd>
	</xsl:for-each>
      <!-- </xsl:if> -->
      
      <!-- <xsl:if test="xht2:a[@rel='rinfo:rattsfallshanvisning']"> -->
	<dt>Rättsfall</dt>
	<xsl:for-each select="xht2:dd[xht2:a[@rel='rinfo:rattsfallshanvisning']]">
	  <dd><xsl:apply-templates select="."/></dd>
	</xsl:for-each>
      <!-- </xsl:if> -->

      <xsl:if test="xht2:dd[@property='dct:relation']">
	<dt>Litteratur</dt>
	<xsl:for-each select="xht2:dd[@property='dct:relation']">
	  <dd><xsl:value-of select="."/></dd>
	</xsl:for-each>
      </xsl:if>

      <xsl:if test="xht2:dd[@property='dct:subject']">
	<dt>Sökord</dt>
	<xsl:for-each select="xht2:dd[@property='dct:subject']">
	  <dd><xsl:value-of select="."/></dd>
	</xsl:for-each>
      </xsl:if>

      <dt>Källa</dt>
      <dd><a href="http://www.rattsinfosok.dom.se/lagrummet/index.jsp">Domstolsverket</a></dd>
    </dl>
  </xsl:template>

  <xsl:template match="*|@*" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <!-- kommentar mode -->
  <xsl:template match="*|@*" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>

  
</xsl:stylesheet>

