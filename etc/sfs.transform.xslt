<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- this stylesheet formats a law. it's the stylesheet from hell. -->
  <xsl:import href="base.xslt"/>
  <xsl:output method="xml"
	      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
	      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	      />
    <!-- the following basically transfers control to the base
       stylesheet so that it can provide the basic template with
       navigation, css etc -->
  <xsl:template match="/">
    <xsl:apply-imports/>
  </xsl:template>

  <xsl:template match="/html/body">
    <something>
      <xsl:apply-imports/>
    </something>
  </xsl:template>

  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  
</xsl:stylesheet>
