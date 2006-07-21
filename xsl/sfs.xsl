<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- this stylesheet formats a law. it's the stylesheet from hell. -->
  <xsl:import href="link.xsl"/>
  <xsl:output encoding="iso-8859-1"
	      method="xml"
	      />


  <xsl:template match="/">
    
      <xsl:apply-templates/>
    
  </xsl:template>

  <!-- we should be able to find this out from /law/preamble/sfsid, but it stopped working... -->
  <xsl:param name="lawid"/>
  <!-- today's date -->
  <xsl:param name="today"/>
  <xsl:variable name="sectionOneCount" select="count(//section[@id='1'])"/>
  <xsl:variable name="hasChapters" select="/law/chapter"/>
  
  <xsl:template match="/law">
    <h1 class="legaldoc" id="top"><xsl:value-of select="preamble/title"/></h1>
    <xsl:comment>start:top</xsl:comment>
    <xsl:comment>end:top</xsl:comment>
    <dl class="preamble legaldoc">
      <xsl:apply-templates mode="header" select="preamble"/>
    </dl>
    <!--
    <div class="metadata">
      <xsl:apply-templates select="meta" mode="header"/>
      <xsl:variable name="bigtoc" select="chapter[(headline or section)]"/>
      <xsl:if test="$bigtoc">
	<form>
	  <input id="toggletoc" type="button" value="Visa innehållsförteckning"/>
	</form>
	<div id="toc">
	  <xsl:apply-templates select="chapter[(headline or section)]" mode="toc"/>
	</div>
      </xsl:if>
    </div>
    -->
    <!-- the actual meat of the law -->
    <xsl:apply-templates/>
  </xsl:template>


  <!-- =============================== -->
  <!-- STUFF APPLICABLE TO HEADER MODE -->
  <!-- =============================== -->

  <!-- in dv.xsl, a similar problem (how to handle all metadata properties) is
       solved the other way round (the main template does a lot of xsl:value-of
       inserts) - it results in tighter, although maybe a litte less XSLT-ish, code
  -->

  <xsl:template match="preamble" mode="header">
    <xsl:apply-templates mode="header"/>
  </xsl:template>

  <xsl:template match="meta" mode="header">
    <dl>
      <dt>Källa</dt>
      <dd><a href="http://62.95.69.15/cgi-bin/thw?%24%7BHTML%7D=sfst_lst&amp;%24%7BOOHTML%7D=sfst_dok&amp;%24%7BSNHTML%7D=sfst_err&amp;%24%7BBASE%7D=SFST&amp;%24%7BTRIPSHOW%7D=format%3DTHW&amp;BET={$lawid}%24">Regeringskansliets rättsdatabaser</a></dd>
      <xsl:apply-templates mode="header"/>
    </dl>
  </xsl:template>

  <xsl:template match="preamble/sfsid" mode="header">
    <dt>SFS-nummer</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/dept" mode="header">
    <dt>Departement/myndighet</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/issued" mode="header">
    <dt>Utfärdad</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/containedchanges" mode="header">
    <dt>Ändring införd</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/revoked" mode="header">
    <dt>Upphävd</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/revokedby" mode="header">
    <dt>Upphävd genom</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/other" mode="header">
    <dt>Övrigt</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/reprint" mode="header">
    <dt>Omtryck</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="preamble/timelimited" mode="header">
    <dt>Tidsbegränsad</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>

  <xsl:template match="meta/fetched" mode="header">
    <dt>Senast hämtad</dt>
    <dd><xsl:value-of select="."/></dd>
  </xsl:template>


  <xsl:template match="preamble/title" mode="header"/>

  <!-- =============================== -->
  <!-- STUFF APPLICABLE TO TOC MODE    -->
  <!-- =============================== -->

  <!-- fixme: it would be great if we could have a old-school nested   unorderedlist instead of this divmess -->

  <xsl:template match="headline" mode="toc">
    <xsl:if test="@level = '1'">
      <div class="l1">
	<a>
	  <xsl:attribute name="href">
	    <xsl:choose>
	      <xsl:when test="substring(.,1,5) = 'AVD. '">#R<xsl:value-of select="@id"/></xsl:when>
	      <xsl:when test="../../chapter">#K<xsl:value-of select="../@id"/></xsl:when>
	      <xsl:otherwise>#R<xsl:value-of select="@id"/></xsl:otherwise>
	    </xsl:choose>
	  </xsl:attribute>
	  <xsl:value-of select="."/>
	</a>
      </div>
    </xsl:if>
    <xsl:if test="@level = '2'">
      <div class="l2">
	<a href="#R{@id}"><xsl:value-of select="."/></a>
      </div>
    </xsl:if>
  </xsl:template>

  <xsl:template match="section" mode="toc"/>
  <xsl:template match="changes" mode="toc"/>
  <xsl:template match="appendix" mode="toc"/>
  <xsl:template match="preamble" mode="toc"/>
  <xsl:template match="meta" mode="toc"/>

  <!-- =============================== -->
  <!-- STUFF APPLICABLE TO NORMAL MODE -->
  <!-- =============================== -->

  <xsl:template match="preamble"/>
  <xsl:template match="meta"/>

  <xsl:template match="changes">
    <h1>Ändringar och övergångsbestämmelser</h1>
    <dl>
    <xsl:for-each select="change">
      <dt id="L{translate(@id,' ','_')}">Ändring:</dt>
      <xsl:for-each select="link">
	<dd><xsl:call-template name="link"/></dd>
      </xsl:for-each>
      <xsl:for-each select="prop">
	<dt><xsl:value-of select="@key"/></dt>
	<dd><xsl:apply-templates/></dd>
      </xsl:for-each>
    </xsl:for-each>
    </dl>
  </xsl:template>

  <xsl:template match="introduction">
    INTRODUCTION:<br/>
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="chapter">
    <a name="K{@id}"/>
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="headline">
    <xsl:variable name="id">R<xsl:value-of select="@id"/></xsl:variable>
    <xsl:if test="@level = '1'">
      <h1 id="{$id}" class="legaldoc"><xsl:value-of select="."/></h1>
    </xsl:if>
    <xsl:if test="@level = '2'">
      <h2 id="{$id}" class="legaldoc"><xsl:value-of select="."/></h2>
    </xsl:if>
    <xsl:comment>start:R<xsl:value-of select="@id"/></xsl:comment>
    <xsl:comment>end:R<xsl:value-of select="@id"/></xsl:comment>
  </xsl:template>

  <xsl:template match="section">
    <xsl:variable name="id">
      <xsl:if test="$hasChapters and $sectionOneCount > 1">K<xsl:value-of select="../../@id"/></xsl:if>P<xsl:value-of select="../@id"/>
    </xsl:variable>
    <a name="{$id}"></a>
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="p">
    <!-- depending on wheter this is is a paragraph inside of a
	 section, the appendix, or the introduction, we must use
	 different anchor name prefixes -->
    <xsl:variable name="id">
      <xsl:if test="ancestor::section">
	<xsl:if test="$hasChapters and $sectionOneCount > 1">K<xsl:value-of select="../../@id"/></xsl:if>P<xsl:value-of select="../@id"/>S<xsl:number/>
      </xsl:if>
      <xsl:if test="ancestor::introduction">S<xsl:number/></xsl:if>
      <xsl:if test="ancestor::appendix">B<xsl:number/></xsl:if>
    </xsl:variable>
    <!-- <a name="{$id}"/> -->
    <p id="{$id}" class="legaldoc">
    <!-- if this is the first p in a section, bring in the 
	 section id as a span element -->
    <xsl:if test="(ancestor::section) and (position()=2)">
      <!-- why 2? I have no idea... -->
      <span class="sectionid"><xsl:value-of select="../@id"/> § </span>
    </xsl:if>
    <xsl:apply-templates/>
    </p>
    <xsl:comment>start:<xsl:value-of select="$id"/></xsl:comment>
    <xsl:comment>end:<xsl:value-of select="$id"/></xsl:comment>
  </xsl:template>

  <xsl:template match="ol">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="li">
    <xsl:variable name="id">
      <xsl:if test="$hasChapters and $sectionOneCount > 1">K<xsl:value-of select="../../../@id"/></xsl:if>P<xsl:value-of select="../../@id"/>S<xsl:value-of select="count(../preceding-sibling::p)"/>N<xsl:number/>
    </xsl:variable>
    <p id="{$id}" class="legaldoc faux-li">
    <xsl:apply-templates/>
    </p>
    <xsl:comment>start:<xsl:value-of select="$id"/></xsl:comment>
    <xsl:comment>end:<xsl:value-of select="$id"/></xsl:comment>
  </xsl:template>

  <xsl:template match="br">
    <br/>
  </xsl:template>

  <xsl:template match="table">
    <table>
      <xsl:apply-templates/>
    </table>
  </xsl:template>

  <xsl:template match="th">
    <th>
      <xsl:apply-templates/>
    </th>
  </xsl:template>

  <xsl:template match="tr">
    <tr>
      <xsl:apply-templates/>
    </tr>
  </xsl:template>

  <xsl:template match="td">
    <td>
      <xsl:apply-templates/>
    </td>
  </xsl:template>

  <xsl:template match="pre">
    <pre>
      <xsl:apply-templates/>
    </pre>
  </xsl:template>


  <xsl:template match="appendix">
    <div class="appendix">
      <xsl:apply-templates/>
    </div>
  </xsl:template>


  <xsl:template name="docref">
    <xsl:variable name="url">
      <xsl:choose>
	<xsl:when test="@doctype='celex'">
http://europa.eu.int/smartapi/cgi/sga_doc?smartapi!celexplus!prod!CELEXnumdoc&amp;lg=sv&amp;numdoc=<xsl:value-of select="@docid"/>
	</xsl:when>
	<xsl:when test="@doctype='prop'">
	  <!-- 1993 onwards -->
	  <xsl:if test="number(substring(@docid,1,4)) > 1992">
	    <xsl:variable name="base">
	      PROPARKIV<xsl:call-template name="shortyears">
	      <xsl:with-param name="id" select="@docid"/>
	    </xsl:call-template>
	    </xsl:variable>
	    <xsl:variable name="pnr" select="substring-after(@docid,':')"/>
	    http://rixlex.riksdagen.se/htbin/thw?${HTML}=PROP_LST&amp;${OOHTML}=PROP_DOK&amp;${SNHTML}=PROP_ERR&amp;${MAXPAGE}=26&amp;${CCL}=define+reverse&amp;${TRIPSHOW}=format=THW&amp;${BASE}=<xsl:value-of select="normalize-space($base)"/>&amp;${FREETEXT}=&amp;PRUB=&amp;DOK=&amp;PNR=<xsl:value-of select="$pnr"/>&amp;ORG=
	  </xsl:if>
	</xsl:when>
	<xsl:when test="@doctype='consid'">
	  <!-- 1990 onwards -->
	  <xsl:if test="number(substring(@docid,1,4)) > 1989">
	    <xsl:variable name="base">
	      BETARKIV<xsl:call-template name="shortyears">
	      <xsl:with-param name="id" select="@docid"/>
	    </xsl:call-template>
	    </xsl:variable>
	    <xsl:variable name="bnr" select="substring-after(@docid,':')"/>
	    http://rixlex.riksdagen.se/htbin/thw?${HTML}=BET_LST&amp;${OOHTML}=BET_DOK&amp;${SNHTML}=BET_ERR&amp;${MAXPAGE}=26&amp;${TRIPSHOW}=format=THW&amp;${CCL}=define+reverse&amp;${BASE}=<xsl:value-of select="normalize-space($base)"/>&amp;${FREETEXT}=&amp;BRUB=&amp;BNR=<xsl:value-of select="$bnr"/>
	  </xsl:if>
	</xsl:when>
	<xsl:when test="@doctype='skrivelse'">
	  <!-- 1999 onwards -->
	  <xsl:if test="number(substring(@docid,1,4)) > 1998">
	    http://www.riksdagen.se/debatt/rskr/rskr<xsl:call-template name="shortyears"><xsl:with-param name="id" select="@docid"/></xsl:call-template>.asp
	  </xsl:if>
	</xsl:when>
      </xsl:choose>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="normalize-space($url)!=''">
	<a href="{normalize-space($url)}" title="Länk till det externa dokumentet {normalize-space(.)}"><xsl:value-of select="."/></a>
      </xsl:when>
      <xsl:otherwise>
	<a title="Dokument {normalize-space(.)} är inte tillgängligt" style="border-bottom: 1px dashed black;"><xsl:value-of select="."/></a>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="shortyears">
    <xsl:param name="id"/>
    <xsl:value-of select="substring($id,3,2)"/>
    <xsl:value-of select="substring(substring-before($id,':'),string-length(substring-before($id,':'))-1,2)"/>
  </xsl:template>
</xsl:stylesheet>