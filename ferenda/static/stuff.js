/* supporting code for the 3col layout */
var d = document;

function reloadPage(init) {  //Reloads the window if Netscape 4.x resized
  if (init==true) with (navigator) {if ((appName=="Netscape")&&(parseInt(appVersion)==4)) {
    document.pgW=innerWidth; document.pgH=innerHeight; onresize=reloadPage; }}
  else if (innerWidth!=document.pgW || innerHeight!=document.pgH) location.reload();
}
reloadPage(true);

function holdW(where){
  var mW = "";
  if((d.layers) || (d.getElementById('banner').style.minWidth == undefined)) { 
    var mW = ("<hr size=\"0\" color=\"white\" class=\"" + where + "\">");
  }
  return mW  
} 


Editable = {
  origtexts: {},
  deferred: null,
  curEditor: null,
  curCommentid: null,
  edit: function(e) {
    boxElement = e.src();
    log("Making editable");
    if (hasElementClass(boxElement,"editor")) {
      log("was already editable!");
      return;
    }
    commentid = boxElement.id.substr(8); //trim off initial "comment-"
    log("edit: commentid is", commentid);
    
    dim = getElementDimensions(boxElement);
    if (dim.h < 120) {
      dim.h = 120;
      dim.w = boxElement.parentNode.clientWidth;
      setElementDimensions(boxElement,dim);
      boxElement.style.zIndex=1;
    }
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
    Editable.resizeToCollapsed(editor);
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
    Editable.resizeToCollapsed(Editable.curEditor);
  },
  
  saveFailed: function(xhr) {
    log("save failed");
    // note that we have to use xhr.req.responseText here, as opposed to xhr.responseText -- some mochikit
    // magic that I have yet to understand.
    replaceChildNodes(Editable.curEditor,
		      SPAN({'class':'commentid'},Editable.curCommentid),SPAN({'class':'error'},xhr.req.responseText));
    Editable.deferred = null;
    Editable.resizeToCollapsed(Editable.curEditor);
  },


  resizeToCollapsed: function(element) {
    dim = getElementDimensions(element);
    element.style.zIndex=0;
    dim.w = element.origWidth;
    if (element.origHeight < element.scrollHeight) {
      log("resizeToCollapsed: content doesn't fit anymore -- we need to move some boxes!");
      dim.h = element.scrollHeight;
      setElementDimensions(element,dim);
      // this will only occur for comments, not references
      Editable.currentBoxMovingPolicy('comment'); 
    } else {
      dim.h = element.collapsedHeight;
    }    

    setElementDimensions(element,dim);
  },
  // practially identical to resizeToCollapsed now  
  resizeToOriginal: function(element) {
    dim = getElementDimensions(element);
    dim.w = element.origWidth;
    if (element.origHeight < element.scrollHeight) {
      log("resizeToCollapsed: content doesn't fit anymore -- we need to move some boxes!");
      dim.h = element.scrollHeight;
      setElementDimensions(element,dim);
      Editable.currentBoxMovingPolicy('comment'); // this will only occur for comments, not references
    } else {
      dim.h = element.origHeight;
      setElementDimensions(element,dim);
    }
  },
  
  expandBox: function(e) {
    log("expandingBox");
    imgElement = e.src();
    boxElement = e.src().parentNode;
    e.stopPropagation();        
    //log("box has zindex: " + computedStyle(boxElement,'z-index'));
    boxElement.style.zIndex=1;
    //log("box has zindex: " + computedStyle(boxElement,'z-index'));
    Editable.resizeToOriginal(boxElement);
    disconnect(imgElement.clickSignal);
    //log("box has zindex: " + computedStyle(boxElement,'z-index'));
    imgElement.clickSignal = connect(e.src(),'onclick',Editable.collapseBox);
    imgElement.src = "/static/application_get.png";
    
  },
  
  collapseBox: function (e) {
    log("collapsing box");
    imgElement = e.src();
    boxElement = e.src().parentNode;
    boxElement.style.zIndex=0;
    Editable.resizeToCollapsed(boxElement);
    disconnect(imgElement.clickSignal);
    imgElement.clickSignal = connect(e.src(),'onclick',Editable.expandBox);
    imgElement.src = "/static/application_put-1.png";  
    e.stopPropagation();
  },
  
  /* there is a choice between two methods of placing the boxes: both try to
  move every box in-line with the legal document section it relates to, but if
  there's no room, moveAndCollapse collapses the boxes (and adds a maximize
  button), while moveToAvailableSlot places the box as close to the legal
  document section as possible without placing it over an existing box. Which
  one is in use is governed by Editable.currentBoxMovingPolicy */
  moveAndCollapse: function (classname) {
    var elements = getElementsByTagAndClassName("p", classname);
    prevtop = 0;
    for (var i=elements.length-1; i >= 0; i--) {
      element = elements[i]
      pe = document.getElementById(element.id.substr(classname.length + 1));
      element.style.position = "absolute";
      element.style.top = pe.offsetTop + "px";
      pos = getElementPosition(element, element.parentNode);
      dim = getElementDimensions(element);
      element.origHeight = dim.h;
      element.origWidth = dim.w;	
      if (prevtop != 0) {
	// we might need to trim 
	if (pos.y + dim.h > prevtop) {
	  //log("trimming");
	  dim.h = prevtop - pos.y - 3;
	  element.collapsedHeight = dim.h;
	  setElementDimensions(element, dim);
	  element.style.overflow="hidden";
	  imgelement = IMG({'src': '/static/application_put-1.png',
		 'class': 'expandicon',
		 'width': '16',
		 'heigth': '16',
		 'alt': 'Expandera den här rutan',
		 'title': 'Expandera den här rutan'});
	  imgelement.clickSignal = connect(imgelement, 'onclick',Editable.expandBox);
	  appendChildNodes(element, imgelement);
	} else {
	  element.collapsedHeight = element.origHeight;
	}
      }
      element.style.left = "0"; // needed for IE
      element.style.right = "0"; 
  
      // remember the top pos for this one
      // pos = getElementPosition(element,element.parentNode);
      prevtop = pos.y;
      // log("settting prevtop to " + prevtop);
    }
  },
  /* see comment for moveAndCollapse */
  moveToAvailableSlot: function(classname) {
    starttime = new Date();
    intervaltime = new Date();
    var elements = getElementsByTagAndClassName("p", classname);
    log("Moving " + elements.length + " boxes");
    requiredTopPos = 0;
    for (var i=0; i < elements.length; i++) {
      element = elements[i];
      element.style.position = "absolute";
      element.style.display = "block";
      pe = document.getElementById(element.id.substr(classname.length + 1));
      //faster(?) way of moving elements
      //element.style.top = pe.offsetTop + "px";      
      pos = getElementPosition(element,element.parentNode);
      dim = getElementDimensions(element);
      
      corrPos = getElementPosition(pe,pe.parentNode);
      if (corrPos.y > requiredTopPos) {
	//alert("moving box #" + i + " inline: top: " + pos.y + ", corrTop:" + corrPos.y);
	pos.y = corrPos.y;
      } else {
	//alert("moving box #" + i + " to requiredTopPos: top: " + pos.y + ", corrTop:" + corrPos.y);
	pos.y = requiredTopPos;
      }
      setElementPosition(element, pos);
      dim.w = element.parentNode.clientWidth;      
      element.origHeight = dim.h;
      element.collapsedHeight = dim.h;	
      element.origWidth = dim.w;	

      setElementDimensions(element,dim);
      
      requiredTopPos = pos.y + dim.h + 2; // 3 = margin
      
      //if (i % 100 == 0) {
        //log("moved 100 boxes in " + (new Date() - intervaltime));
	//intervaltime = new Date()
      //}

    }
    endtime = new Date()
    log("elapsed:" + (endtime - starttime) + " (start " + starttime + ", end " + endtime + ")")
  },

  moveBoxes: function () {
    //log("Moving boxes");
    //Editable.moveToAvailableSlot('references');
    //Editable.moveToAvailableSlot('comment');
    Editable.currentBoxMovingPolicy('comment');
    Editable.currentBoxMovingPolicy('references');
  },
  
  connectBoxes: function() {
    var origtext;
    //log("connecting elements");
    var elems = getElementsByTagAndClassName("p", "editable");
    log("connecting", elems.length, "p's");
    for (var i = 0; i < elems.length; i++) { 
      var elem = elems[i];
      connect(elem,'onclick',Editable.edit);
      elem.title = "Click to edit";
      //appendChildNodes(elem, "[foo]");
    }
  },
  createLoggingPane: function() {
    createLoggingPane(true);
  }
}
Editable.currentBoxMovingPolicy = Editable.moveToAvailableSlot;
//connect(window,'onload', Editable.createLoggingPane);
connect(window,'onload',Editable.connectBoxes);
connect(window,'onload',Editable.moveBoxes);
// FIXME: on non-gecko browsers this event fires continously
// while the user resizes - lots of work. We should wait until
// no more resize events have been fired and then move boxes
connect(window,'resize',Editable.moveBoxes);

