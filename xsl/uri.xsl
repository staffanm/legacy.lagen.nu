<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:str="http://exslt.org/strings"
		extension-element-prefixes="str">


  <!-- this is a standalone template for formatting links that use
       rinfo-standard URI:s (mapping those abstract uris to concrete
       uris used by lagen.nu -->
  <xsl:template name="link">
    <xsl:variable name="uri" select="@href"/>
    <xsl:variable name="localurl">
      <xsl:call-template name="localurl">
	<xsl:with-param name="uri" select="$uri"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="contains($uri, '#L')">
	<span class="andringsnot"><xsl:apply-templates/></span>
      </xsl:when>
      <xsl:when test="$localurl = ''">
	<xsl:value-of select="."/>
      </xsl:when>
      <xsl:otherwise>
	<a href="{$localurl}"><xsl:apply-templates/></a>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- maps an idealized rinfo resource URI to an actual retrievable
       URI, either at lagen.nu or somewhere else -->
  <xsl:template name="localurl">
    <xsl:param name="uri"/>
    <xsl:choose>
      <xsl:when test="substring($uri, 0, 26) != 'http://rinfo.lagrummet.se'">
	<xsl:value-of select="$uri"/>
      </xsl:when>
      <xsl:when test="contains($uri,'/publ/sfs')">
	<xsl:value-of select="substring-after($uri, '/publ/sfs')"/>
      </xsl:when>
      <xsl:when test="contains($uri,'/publ/rattsfall')">
	/dom<xsl:value-of select="substring-after($uri, '/publ/rattsfall')"/>
      </xsl:when>
      <xsl:when test="contains($uri,'/ext/celex')">
	<!-- http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=CELEX:<xsl:value-of select="substring-after($uri, '/ext/celex/')"/>:SV:HTML-->http://eurlex.nu/doc/<xsl:value-of select="substring-after($uri, '/ext/celex/')"/>
      </xsl:when>
    </xsl:choose>            
  </xsl:template>
</xsl:stylesheet>