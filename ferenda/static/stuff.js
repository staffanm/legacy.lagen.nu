Editable = {
  origtexts: {},
  deferred: null,
  curEditor: null,
  curCommentid: null,
  edit: function(e) {
    log("Making editable");
    if (hasElementClass(e.src(),"editor")) {
      log("was already editable!");
      return;
    }
    commentid = e.src().id.substr(8); //trim off initial "comment-"
    log("edit: commentid is", commentid);
    //Editable.origtext = scrapeText(e.src());
    textarr = scrapeText(e.src(),true);
    textarr[0]="";
    Editable.origtexts[commentid] = textarr.join("");
    log("edit: origtext is", Editable.origtexts[commentid]);
    var action = "/save/" + document.body.id + "/" + commentid;
    var submit = INPUT({'type':'button','value':'Spara'});
    var cancel = INPUT({'type':'button','value':'Ångra'});
    var form = FORM({'method':'POST','action':action},
		   TEXTAREA({'name':'text','rows':'5','cols':'6'},Editable.origtexts[commentid]),
		   BR(),
		   submit,
		   cancel
		  );
    connect(submit,'onclick',Editable.save);
    connect(cancel,'onclick',Editable.cancel);
    replaceChildNodes(e.src(),form);
    addElementClass(e.src(),'editor');
  },
    
  cancel: function(e) {
    log("Canceling editor");
    editor = e.src().parentNode.parentNode;
    commentid = editor.id.substr(8);  // trim off initial "comment-"
    replaceChildNodes(editor,
		      SPAN({'class':'commentid'},commentid),Editable.origtexts[commentid]);
    removeElementClass(editor,"editor");
  },
  
  save: function(e) {
    log("Doing fancy XHR call");
    editor = e.src().parentNode.parentNode;
    commentid = editor.id.substr(8);
    Editable.curEditor = editor;
    Editable.curCommentid = commentid;
    text = editor.getElementsByTagName("textarea")[0].value;
    log("value",text);
    xhr = getXMLHttpRequest();
    actionUrl = "/savexhr/" + document.body.id + "/" + commentid;
    log("action", actionUrl);
    xhr.open("POST",actionUrl,true);
    replaceChildNodes(editor,
		      SPAN({'class':'commentid'},commentid),"...sparar...");
    Editable.deferred = sendXMLHttpRequest(xhr, queryString(['text'],[text]));
    Editable.deferred.addCallbacks(Editable.saved,Editable.saveFailed);
    removeElementClass(editor,"editor");    
    return false;
  },
  saved: function(xhr) {
    log("save succeeded");
    replaceChildNodes(Editable.curEditor,
		      SPAN({'class':'commentid'},Editable.curCommentid),xhr.responseText);
    Editable.deferred = null;
  },
  saveFailed: function(xhr) {
    log("save failed");
    // note that we have to use xhr.req.responseText here, as opposed to xhr.responseText -- some mochikit
    // magic that I have yet to understand.
    replaceChildNodes(Editable.curEditor,
		      SPAN({'class':'commentid'},Editable.curCommentid),SPAN({'class':'error'},xhr.req.responseText));
    Editable.deferred = null;
  }
}

/* addEvent(window,'load',MoveComments,false); */
/* addEvent(window,'load',PrepareEditFields,false); */
connect(window, 'onload', function(e) {
    var origtext;
    var elems = getElementsByTagAndClassName("div", "clicktoedit");
    log("connecting", elems.length, "elements");
    for (var i = 0; i < elems.length; i++) { 
      var elem = elems[i];
      connect(elem,'onclick',Editable.edit);
      elem.title = "Click to edit";
      //appendChildNodes(elem, "[foo]");
    }
  }
);
