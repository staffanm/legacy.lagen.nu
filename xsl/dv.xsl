<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:import href="link.xsl"/>
  <!-- this stylesheet formats a verdict. It is 60 % less evil than sfs.xsl  -->
  <xsl:output encoding="iso-8859-1"
	      method="xml"
	      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
	      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	      />

  <!-- we need to declare this variable in order to use the link.xsl
       template -->
  <xsl:variable name="hasChapters"/>

  <xsl:template match="/">
    <div class="middle">
      <xsl:apply-templates/>
    </div>  
  </xsl:template>

  <xsl:template match="/Dom">
    <h1 class="legaldoc">
    <!-- basically the same algorithm as in _findDisplayId in DVManager, with less fancy string handling -->
      <xsl:choose>
	<xsl:when test="(Metadata/Referat != 'Referat �nnu ej publicerat') and (Metadata/Referat != 'Referat finns ej')"><xsl:value-of select="Metadata/Referat"/></xsl:when>
	<xsl:when test="Metadata/M�lnummer"><xsl:value-of select="Metadata/M�lnummer"/></xsl:when>
	<xsl:when test="Metadata/Diarienummer"><xsl:value-of select="Metadata/Diarienummer"/></xsl:when>
	<xsl:when test="Metadata/Domsnummer"><xsl:value-of select="Metadata/Domsnummer"/></xsl:when>
      </xsl:choose>
    </h1>
    <h2><xsl:value-of select="Metadata/Rubrik"/></h2>
    <dl class="preamble legaldoc">
      <dt>Domstol</dt>
      <dd><xsl:value-of select="Metadata/Domstol"/></dd>
      <dt>M�lnummer</dt>
      <dd><xsl:value-of select="Metadata/M�lnummer"/></dd>
      <dt>Avdelning</dt>
      <dd><xsl:value-of select="Metadata/Avdelning"/></dd>
      <dt>Avg�randedatum</dt>
      <dd><xsl:value-of select="Metadata/Avg�randedatum"/></dd>
      <!-- consider adding diarienummer/domsnummer --> 
      <dt>Lagrum</dt>
      <xsl:for-each select="Metadata/Lagrum">
	<dd><xsl:apply-templates/></dd>
      </xsl:for-each>
      <dt>R�ttsfall</dt>
      <xsl:for-each select="Metadata/R�ttsfall">
	<dd><xsl:apply-templates/></dd>
      </xsl:for-each>
      <dt>S�kord</dt>
      <xsl:for-each select="Metadata/S�kord">
	<dd><xsl:apply-templates/></dd>
      </xsl:for-each>
    </dl>
    <xsl:comment>start:top</xsl:comment>
    <xsl:comment>end:top</xsl:comment>
    <xsl:if test="Referat">
    <h2 class="legaldoc">Referat</h2>
    <xsl:comment>start:referat</xsl:comment>
    <xsl:comment>end:referat</xsl:comment>
    <xsl:apply-templates select="Referat"/>
    </xsl:if>
  </xsl:template>

  <xsl:template match="p">
    <p class="legaldoc"><xsl:apply-templates/></p>
    <xsl:comment>start:S<xsl:number/></xsl:comment>
    <xsl:comment>end:S<xsl:number/></xsl:comment>
  </xsl:template>
</xsl:stylesheet>

