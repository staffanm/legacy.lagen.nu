<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- this is a standalone template for formatting links that use
       rinfo-standard URI:s (mapping those abstract uris to concrete
       uris used by lagen.nu -->
  <xsl:template name="uri">
    <xsl:choose>
      <xsl:when test="contains(@href,'/publ/sfs')">
	<xsl:variable name="uri">
	  <xsl:value-of select="substring-after(@href, '/publ/sfs')"/>
	</xsl:variable>
	<a href="{$uri}"><xsl:value-of select="."/></a>
      </xsl:when>
      <xsl:otherwise>
	<!-- more stuff (cases, propositions, celexdocs etc) to come -->
	<xsl:value-of select="."/>
      </xsl:otherwise>
    </xsl:choose>            
  </xsl:template>
</xsl:stylesheet>