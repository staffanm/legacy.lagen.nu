<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dc="http://purl.org/dc/elements/1.1/">
  <!-- FIXME: ändra dc till dct -->
  
  <xsl:include href="base.xsl"/>

  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    [lagnamn] ([alternativform]) | Lagen.nu
  </xsl:template>

  <!-- FIXME: anpassa till xht2-datat -->
  <xsl:template name="metarobots">
    <xsl:if test="preamble/revoked">
      <xsl:if test="number(translate($today,'-','')) > number(translate(/preamble/revoked,'-',''))">
	<meta name="robots" content="noindex,follow"/>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <!-- FIXME: anpassa till xht2-datat -->
  <xsl:template name="linkalternate">
    <link rel="alternate" type="text/plain" title="Plain text">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.txt</xsl:attribute>
    </link>
    <link rel="alternate" type="application/xml" title="XML">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.xml</xsl:attribute>
    </link>
  </xsl:template>

  <xsl:template name="headmetadata">
      <xsl:comment>all övrig metadata</xsl:comment>
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