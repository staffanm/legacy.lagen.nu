<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:import href="link.xsl"/>
  <!-- this stylesheet formats a verdict. The XML document contains a
       written report on the case, which we strip out in this
       stylesheets because of privacy concerns
  -->
  <xsl:output encoding="iso-8859-1"
	      method="xml"
	      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
	      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	      />

  <xsl:template match="/Dom">
    <xsl:variable name="id" select="@urn"/>
    <div class="content"> 
      <div class="outer">
	<div class="legaldoc">
	  <h1>[<xsl:value-of select="Metadata/Referat"/>]</h1>
	  <h2><xsl:value-of select="Metadata/Rubrik"/></h2>
	  
	  <dl class="preamble">
	    <dt>Domstol</dt>
	    <dd><xsl:value-of select="Metadata/Domstol"/></dd>
	    <dt>M�lnummer</dt>
	    <dd><xsl:value-of select="Metadata/M�lnummer"/></dd>
	    <dt>Avdelning</dt>
	    <dd><xsl:value-of select="Metadata/Avdelning"/></dd>
	    <dt>Avg�randedatum</dt>
	    <dd><xsl:value-of select="Metadata/Avg�randedatum"/></dd>
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
	</div>
	<xsl:comment>start:top</xsl:comment>
	<div class="commentplaceholder clicktoedit" id="comment-top"> 
	  <span class="commentid">top</span>klicka f�r att kommentera!
	</div>
	<xsl:comment>end:top</xsl:comment>
      </div>
      <xsl:if test="Referat">
	<div class="outer">
	  <div class="legaldoc">
	    <h2>Referat</h2>
	  </div>
	  <xsl:comment>start:referat</xsl:comment>
	  <div class="commentplaceholder clicktoedit">
	    <span class="commentid">referat</span>klicka f�r att kommentera!
	  </div>
          <xsl:comment>end:referat</xsl:comment>
	</div>
	<xsl:apply-templates select="Referat"/>
      </xsl:if>
    </div>
  </xsl:template>

  <xsl:template match="p">
    <div class="outer">
      <div class="legaldoc">
	<p><xsl:apply-templates/></p>
      </div>
      <xsl:comment>start:S<xsl:number/></xsl:comment>
      <div class="commentplaceholder clicktoedit">
	<span class="commentid">S<xsl:number/></span>klicka f�r att kommentera!
      </div>
      <xsl:comment>end:S<xsl:number/></xsl:comment>
    </div>
  </xsl:template>
</xsl:stylesheet>

