<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- this stylesheet formats a law. it's the stylesheet from hell. -->
  <xsl:import href="link.xsl"/>
  <xsl:output encoding="iso-8859-1"
	      method="xml"
	      />

  <!-- the following basically transfers control to the base
       stylesheet so that it can provide the basic template with
       navigation, css etc -->
  <xsl:template match="/">
    <div class="content">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <!-- we should be able to find this out from /law/preamble/sfsid, but it stopped working... -->
  <xsl:param name="lawid"/>
  <!-- today's date -->
  <xsl:param name="today"/>
  
  <xsl:variable name="relevantVerdicts"
		select="document('../generated/verdict-xml/cache.xml')//law[@id=$lawid]"/>
  <xsl:variable name="relevantTags"
		select="document('../static/tags.xml')//law[@id=$lawid]/tag"/>
  <xsl:variable name="sectionOneCount" select="count(//section[@id='1'])"/>
  <xsl:variable name="hasChapters" select="/law/chapter"/>
  
  <!-- this "overrides" the base stylesheet rule for formatting the
       title tag in the html header. If we don't provide this
       template, the resulting page will just get a generic page title
       -->
  <xsl:template name="headtitle">
    <xsl:value-of select="/law/preamble/sfsid"/> - <xsl:value-of select="/law/preamble/title"/> - lagen.nu
  </xsl:template>

  <!-- same for the "robots" meta tag -->
  <xsl:template name="metarobots">
    <xsl:if test="preamble/revoked">
      <xsl:if test="number(translate($today,'-','')) > number(translate(/preamble/revoked,'-',''))">
	<meta name="robots" content="noindex,follow"/>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <xsl:template name="linkalternate">
    <link rel="alternate" type="text/plain" title="Plain text">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.txt</xsl:attribute>
    </link>
    <link rel="alternate" type="application/xml" title="XML">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.xml</xsl:attribute>
    </link>
  </xsl:template>

<xsl:template match="/law">
  <table class="outer" id="top">
    <tr>
      <td>
        <h1 class="legaldoc"><xsl:value-of select="preamble/title"/></h1>
        <dl class="preamble legaldoc">
        <xsl:apply-templates mode="header" select="preamble"/>
        </dl>
      </td>
      <td>
        <xsl:comment>start:top</xsl:comment>
	<p class="commentplaceholder clicktoedit" id ="comment-top"><span class="commentid">top</span>klicka för att kommentera</p>
	<xsl:comment>end:top</xsl:comment>
       </td>
     </tr>
 </table>
  <!--<xsl:apply-templates select="preamble" mode="header"/>-->
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
  <!-- the actual meat of the law -->
  <xsl:apply-templates/>
</xsl:template>


<!-- =============================== -->
<!-- STUFF APPLICABLE TO HEADER MODE -->
<!-- =============================== -->

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
  <xsl:variable name="xid" select="@id"/>
    <table class="changelog" summary="Ändringar och övergångsbestämmelser">
    <tr><td colspan="2"><h1>Ändringar och övergångsbestämmelser</h1></td></tr>
    <xsl:for-each select="change">
        <tr>
	    <td colspan="2" style="border-top: 1px solid black">
	      <!-- what is the id attribute used for? it causes validation errors... -->
	      <a name="L{translate(@id,' ','_')}">
	      </a>
	      <b>Ändring:</b>
	    </td>
	</tr>
	<xsl:for-each select="link">
	  <tr>
	    <td colspan="2">
	      <xsl:call-template name="link"/>
	    </td>
	  </tr>
	</xsl:for-each>
	<xsl:for-each select="prop">
	    <tr>
	        <td class="topright"><xsl:value-of select="@key"/></td>
	        <td>
		    <xsl:apply-templates/>
		</td>
	    </tr>
	</xsl:for-each>
    </xsl:for-each>
    </table>
</xsl:template>

<xsl:template match="chapter">
  <a name="K{@id}"/>
  <xsl:apply-templates/>
</xsl:template>

<xsl:template match="headline">
  <table class="outer">
    <tr>
      <td>
  <xsl:if test="@level = '1'">
    <h1 class="legaldoc">
      <a name="R{@id}"></a>
      <xsl:value-of select="."/>
    </h1>
  </xsl:if>
  <xsl:if test="@level = '2'">
    <h2 class="legaldoc">
      <a name="R{@id}"></a>
      <xsl:value-of select="."/>
    </h2>
  </xsl:if>
      </td>
      <td>
  <xsl:comment>start:R<xsl:value-of select="@id"/></xsl:comment>
  <p class="commentplaceholder clicktoedit" id="comment-R{@id}"><span class="commentid">R<xsl:value-of select="@id"/></span>Klicka för att kommentera</p>
  <xsl:comment>end:R<xsl:value-of select="@id"/></xsl:comment>
      </td>
    </tr>
  </table>
</xsl:template>


<xsl:template match="introduction">
  INTRODUCTION:<br/>
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
  <table class="outer">
    <tr>
      <td>
  <p class="legaldoc">
    <xsl:if test="(ancestor::section) and (position()=2)"><!-- why 2? I have no idea... -->
      <a>
	<xsl:attribute name="name">
	  <xsl:if test="$hasChapters and $sectionOneCount > 1">K<xsl:value-of select="../../@id"/></xsl:if>P<xsl:value-of select="../@id"/>
	</xsl:attribute>
      </a>
      <span class="sectionid"><xsl:value-of select="../@id"/> §</span>
    </xsl:if>
    <xsl:if test="$id">
      <a name="{$id}"/>
      <xsl:apply-templates/>
    </xsl:if>
  </p>
      </td>
      <xsl:if test="$id != ''">
      <td>
	<xsl:comment>start:<xsl:value-of select="$id"/></xsl:comment>
	<p class="commentplaceholder clicktoedit" id="comment-{$id}"><span class="commentid"><xsl:value-of select="$id"/></span>Klicka för att kommentera</p>
	<xsl:comment>end:<xsl:value-of select="$id"/></xsl:comment>
      </td>
      </xsl:if>
    </tr>
  </table>
</xsl:template>

<xsl:template match="ol">
<xsl:apply-templates/>
</xsl:template>

<xsl:template match="li">
  <xsl:variable name="id">
    <xsl:if test="$hasChapters and $sectionOneCount > 1">K<xsl:value-of select="../../../@id"/></xsl:if>P<xsl:value-of select="../../@id"/>S<xsl:value-of select="count(../preceding-sibling::p)"/>N<xsl:number/>
  </xsl:variable>
  <table class="outer">
    <tr>
      <td>
	<p class="legaldoc li">
	  <a name="{$id}"/>
	  <xsl:apply-templates/>
	</p>
      </td>
      <td>
	<xsl:comment>start:<xsl:value-of select="$id"/></xsl:comment>
	<p class="commentplaceholder clicktoedit" id ="comment-{$id}"><span class="commentid"><xsl:value-of select="$id"/></span>klicka för att kommentera</p>
	<xsl:comment>end:<xsl:value-of select="$id"/></xsl:comment>
      </td>
    </tr>
  </table>
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