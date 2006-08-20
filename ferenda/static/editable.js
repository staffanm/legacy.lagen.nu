/* -*- coding: utf-8 -*-

This makes all boxes with a certain classid editable. Relies on
some functions from MovableBox (base.js) and Mochikit
*/

EditableBox = {
  origtexts: {},
  deferred: null,
  curEditor: null,
  curCommentid: null,
  globalClickHandler: function(e) {
    boxElement = e.target();
    log("clicked: ", boxElement.id);
    if (boxElement.id.substring(0,4) == 'edit') {
      fragmentId = boxElement.id.substr(5);    
      log("clickhandler: ", fragmentId);
      // try to find comment box
      boxElement = getElement("comment-" + fragmentId);
      if (!boxElement) {
	log("Code for creating an comment box and attaching it");
	boxElement = P({'class':'comment editable',
			'id':'comment-'+fragmentId},'Kommentar...');
	boxElement.style.position = "absolute";
	boxElement.style.display = "block";			
	appendChildNodes('right',boxElement);
	MovableBox.currentBoxMovingPolicy('comment');
      }	
      EditableBox.makeEditable(boxElement);
    } else if (boxElement.id.substring(0,7) == 'comment') {
      EditableBox.makeEditable(boxElement);      
    }
  },
  boxClickHandler: function(e) {
    EditableBox.makeEditable(e.src());
  },
  makeEditable: function(boxElement) {
    commentid = boxElement.id.substr(8); //trim off initial "comment-"
    log("edit: commentid is", commentid);
    
    dim = getElementDimensions(boxElement);
    if (dim.h < 120) {
      dim.h = 120;
      dim.w = boxElement.parentNode.clientWidth;
      setElementDimensions(boxElement,dim);
      boxElement.style.zIndex=1;
    }
    //EditableBox.origtext = scrapeText(e.src());
    textarr = scrapeText(boxElement,true);
    textarr[0]="";
    EditableBox.origtexts[commentid] = textarr.join("");
    log("edit: origtext is", EditableBox.origtexts[commentid]);
    var action = "/save/" + document.body.id + "/" + commentid;
    var submit = INPUT({'type':'button','value':'Spara'});
    var cancel = INPUT({'type':'button','value':'Ångra'});
    var form = FORM({'method':'POST','action':action},
		   TEXTAREA({'name':'text','rows':'5','cols':'6'},EditableBox.origtexts[commentid]),
		   BR(),
		   submit,
		   cancel
		  );
    connect(submit,'onclick',EditableBox.save);
    connect(cancel,'onclick',EditableBox.cancel);
    replaceChildNodes(boxElement,form);
    addElementClass(boxElement,'editor');
  },
    
  cancel: function(e) {
    log("Canceling editor");
    editor = e.src().parentNode.parentNode;
    commentid = editor.id.substr(8);  // trim off initial "comment-"
    replaceChildNodes(editor,
		      SPAN({'class':'commentid'},commentid),EditableBox.origtexts[commentid]);
    removeElementClass(editor,"editor");
    MovableBox.resizeToCollapsed(editor);
  },
  
  save: function(e) {
    log("Doing fancy XHR call");
    editor = e.src().parentNode.parentNode;
    commentid = editor.id.substr(8);
    EditableBox.curEditor = editor;
    EditableBox.curCommentid = commentid;
    text = editor.getElementsByTagName("textarea")[0].value;
    log("value",text);
    xhr = getXMLHttpRequest();
    docid = document.body.id;
    if (docid.substring(0,1) == 'L') { 
      docid = docid.substr(1);
    }
    actionUrl = "/savexhr/" + docid + "/" + commentid;
    log("action", actionUrl);
    xhr.open("POST",actionUrl,true);
    replaceChildNodes(editor,
		      SPAN({'class':'commentid'},commentid),"...sparar...");
    EditableBox.deferred = sendXMLHttpRequest(xhr, queryString(['text'],[text]));
    EditableBox.deferred.addCallbacks(EditableBox.saved,EditableBox.saveFailed);
    removeElementClass(editor,"editor");    
    return false;
  },

  saved: function(xhr) {
    log("save succeeded");
    replaceChildNodes(EditableBox.curEditor,
		      SPAN({'class':'commentid'},EditableBox.curCommentid),xhr.responseText);
    EditableBox.deferred = null;
    MovableBox.resizeToCollapsed(EditableBox.curEditor);
  },
  
  saveFailed: function(xhr) {
    log("save failed");
    // note that we have to use xhr.req.responseText here, as opposed to xhr.responseText -- some mochikit
    // magic that I have yet to understand.
    replaceChildNodes(EditableBox.curEditor,
		      SPAN({'class':'commentid'},EditableBox.curCommentid),SPAN({'class':'error'},xhr.req.responseText));
    EditableBox.deferred = null;
    MovableBox.resizeToCollapsed(EditableBox.curEditor);
  },
  /* not used */
  createNextEditIcon: function() {
    starttime = new Date();
    quantity = 50;
    startIdx = EditableBox.boxesToConnectIdx;
    endIdx = Math.min(startIdx + quantity,
                      EditableBox.boxesToConnect.length);

    log("doing box #" + startIdx + " to #" + endIdx);
    for (var i=startIdx; i<endIdx; i++) {
      var elem = EditableBox.boxesToConnect[i];
      imgElement = IMG({'src': '/static/comment_add.png',
		      'class': 'editicon',
		      'width': '16',
		      'heigth': '16',
		      'alt': 'Kommentera denna sektion',
		      'title': 'Kommentera denna sektion'});
      // imgelement.clickSignal = connect(imgelement, 'onclick',MovableBox.expandBox);
      parentElement = elem.parentNode;
      parentElement.insertBefore(imgElement,elem);
    } 
    EditableBox.boxesToConnectIdx = endIdx + 1;
    endtime = new Date();
    log("elapsed:" + (endtime - starttime));
    if (endIdx < EditableBox.boxesToConnect.length) {
      window.setTimeout(EditableBox.createNextEditIcon,200);
    } else {
      log("No more boxes to connect!")
    } 
  },
  
  /* not used */
  createEditIcons: function() {
    var origtext;
    //log("connecting elements");
    EditableBox.boxesToConnect = getElementsByTagAndClassName("*", "legaldoc");
    EditableBox.boxesToConnectIdx = 0;
    log("connecting", EditableBox.boxesToConnect.length, "p's");
    window.setTimeout(EditableBox.connectNextBox,200);
  },
  
  connectBoxes: function() {
    var elems = getElementsByTagAndClassName("p", "editable");
    log("connecting", elems.length, "p's");
    for (var i = 0; i < elems.length; i++) {
      var elem = elems[i];
      connect(elem,'onclick',Editable.boxClickHandler);
      elem.title = "Click to edit";
    }
  }
}

// connect(window,'onload',EditableBox.connectBoxes);
connect(document,'onclick',EditableBox.globalClickHandler);