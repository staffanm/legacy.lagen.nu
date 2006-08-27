/* supporting code for the 3col layout */

function reloadPage(init) {  //Reloads the window if Netscape 4.x resized
  if (init==true) with (navigator) {if ((appName=="Netscape")&&(parseInt(appVersion)==4)) {
    document.pgW=innerWidth; document.pgH=innerHeight; onresize=reloadPage; }}
  else if (innerWidth!=document.pgW || innerHeight!=document.pgH) location.reload();
}
reloadPage(true);


/* this makes all box elements with a certain tag and classid move
around so as to fit in line with the legal document text they refer
to. Relies on MochiKit */


MovableBox = {
  resizeToCollapsed: function(element) {
    dim = getElementDimensions(element);
    element.style.zIndex=0;
    dim.w = element.origWidth;
    if (element.origHeight < element.scrollHeight) {
      log("resizeToCollapsed: content doesn't fit anymore -- we need to move some boxes!");
      dim.h = element.scrollHeight;
      setElementDimensions(element,dim);
      // this will only occur for comments, not references
      MovableBox.currentBoxMovingPolicy('comment'); 
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
      MovableBox.currentBoxMovingPolicy('comment'); // this will only occur for comments, not references
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
    MovableBox.resizeToOriginal(boxElement);
    disconnect(imgElement.clickSignal);
    //log("box has zindex: " + computedStyle(boxElement,'z-index'));
    imgElement.clickSignal = connect(e.src(),'onclick',MovableBox.collapseBox);
    imgElement.src = "/static/application_get.png";
    
  },
  
  collapseBox: function (e) {
    log("collapsing box");
    imgElement = e.src();
    boxElement = e.src().parentNode;
    boxElement.style.zIndex=0;
    MovableBox.resizeToCollapsed(boxElement);
    disconnect(imgElement.clickSignal);
    imgElement.clickSignal = connect(e.src(),'onclick',MovableBox.expandBox);
    imgElement.src = "/static/application_put-1.png";  
    e.stopPropagation();
  },
  
  /* there is a choice between two methods of placing the boxes: both try to
  move every box in-line with the legal document section it relates to, but if
  there's no room, moveAndCollapse collapses the boxes (and adds a maximize
  button), while moveToAvailableSlot places the box as close to the legal
  document section as possible without placing it over an existing box. Which
  one is in use is governed by MovableBox.currentBoxMovingPolicy */
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
	  imgelement = IMG({'src': '/static/application_put.png',
		 'class': 'expandicon',
		 'width': '16',
		 'heigth': '16',
		 'alt': 'Expandera den här rutan',
		 'title': 'Expandera den här rutan'});
	  imgelement.clickSignal = connect(imgelement, 'onclick',MovableBox.expandBox);
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
      if (pe) {
	if (pe.nodeName == 'A') {
	  pe = pe.nextSibling
	}
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
      } else {
        log("could not find element with id " + element.id.substr(classname.length + 1))
      }
      
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

    MovableBox.currentBoxMovingPolicy('comment');
    MovableBox.currentBoxMovingPolicy('references');
  }
}
MovableBox.currentBoxMovingPolicy = MovableBox.moveToAvailableSlot;

connect(window,'onload',MovableBox.moveBoxes);
// FIXME: on non-gecko browsers this event fires continously
// while the user resizes - lots of work. We should wait until
// no more resize events have been fired and then move boxes
connect(window,'resize',MovableBox.moveBoxes);

