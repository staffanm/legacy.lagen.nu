<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dct="http://dublincore.org/documents/dcmi-terms/">

  <xsl:include href="base.xsl"/>

  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    [Rättsfallsidentifierare] | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
      
  <xsl:template match="/">
    <div class="middle">
      <xsl:apply-templates/>
    </div>  
  </xsl:template>

  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:dl[@class='metadata']">
    <!-- plocka ut det gottaste från metadatat -->
    <h1><xsl:value-of select="xht2:dd[@property='http://dublincore.org/documents/dcmi-terms/identifier']"/></h1>
    <p><b><xsl:value-of select="xht2:dd[@property='http://dublincore.org/documents/dcmi-terms/description']"/></b></p>
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

  <!-- -->
  <xsl:template match="xht2:h" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:dl[@class='metadata']" mode="refs">
    <dl>
      <dt>Domstol</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://dublincore.org/documents/dcmi-terms/creator']"/></dd>
      <dt>Avgörandedatum</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#avgorandedatum']"/></dd>
      <dt>Målnummer</dt>
      <dd><xsl:value-of select="xht2:dd[@property='http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#malnummer']"/></dd>
    </dl>
    <p>Hänvisningar</p>
    <dl>
      <dt>Lagrum</dt>
      <dt>Rättsfall</dt>
      <xsl:for-each select=
      <dt>Litteratur</dt>
    </dl>
  </xsl:template>

  <xsl:template match="*|@*" mode="refs">
    <xsl:apply-templates mode="refs"/>
  </xsl:template>

  
</xsl:stylesheet>

