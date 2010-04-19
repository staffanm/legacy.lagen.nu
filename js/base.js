$(document).ready(function(){
    $("#toc ul").treeview({
	persist: "location",
        collapsed: true
	});

    /* Use the jQuery UI accordion CSS styles, but not the actual accordion JS code.
       Based on http://paste.pocoo.org/show/105888/

       This is slow on larger texts. Maybe we should set an
       onClick-handler in the pregenerated HTML text instead (even
       though that's not Best Practice<TM>).  */

    $(".ui-accordion")
	.find("h3")
		.click(function() {
			$(this).toggleClass("ui-accordion-header-active").toggleClass("ui-state-active")
				.toggleClass("ui-state-default").toggleClass("ui-corner-bottom")
			.find("> .ui-icon").toggleClass("ui-icon-triangle-1-e").toggleClass("ui-icon-triangle-1-s")
			.end().next().toggleClass("ui-accordion-content-active").toggleClass("ui-helper-hidden");
			//return false;
		})

    /*
    $("#q").autocomplete(docs, {
        matchContains: true,
        selectFirst: false,
        formatItem: function(item) {
            return item.t;
        }
        }).result(function(event, item) {
            location.href = item.l;
    });
    */
    /*
    var c = readCookie('style');
    if (c) switchStylestyle(c);
    */
});

jQuery.fn.setHeightLikeParent = function() {
  return this.each(function(){
      this_height = $(this).height();
      parent_height = $(this).parent().height();
      if (this_height > parent_height) {
	  $(this).height(parent_height);
      }
  });
};

function switchStylestyle(styleName)
{
	$('link[@rel*=style][@title]').each(function(i) 
	{
		this.disabled = true;
		if (this.getAttribute('title') == styleName) this.disabled = false;
	});
	createCookie('style', styleName, 365);
}
function switchBoxlayout(layout)
{
    if (layout == "none") {
	$(".kommentar").removeClass("leftbox").addClass("hiddenbox");
	$(".refs").removeClass("rightbox").addClass("hiddenbox");
    } else if (layout == "horizontal") {
	$(".kommentar").removeClass("hiddenbox").addClass("leftbox");
	$(".refs").removeClass("hiddenbox").addClass("rightbox");
        $(".kommentar").setHeightLikeParent();
        $(".refs").setHeightLikeParent();
    } else if (layout == "vertical") {
	// the default
	$(".kommentar").removeClass("leftbox").removeClass("hiddenbox");
	$(".refs").removeClass("rightbox").removeClass("hiddenbox");
        $(".kommentar").css("height","auto");
        $(".refs").css("height","auto");
         
    }
}

// cookie functions http://www.quirksmode.org/js/cookies.html
function createCookie(name,value,days)
{
	if (days)
	{
		var date = new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires = "; expires="+date.toGMTString();
	}
	else var expires = "";
	document.cookie = name+"="+value+expires+"; path=/";
}
function readCookie(name)
{
	var nameEQ = name + "=";
	var ca = document.cookie.split(';');
	for(var i=0;i < ca.length;i++)
	{
		var c = ca[i];
		while (c.charAt(0)==' ') c = c.substring(1,c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
	}
	return null;
}
function eraseCookie(name)
{
	createCookie(name,"",-1);
}
// /cookie functions