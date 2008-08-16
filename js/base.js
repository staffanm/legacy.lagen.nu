/* placerar varje refbox vid sidan om 'sin' paragraf -- funkar
   halvdant, långsamt och inte alls med utskrifter, så tills vidare
   får refboxarna vara under sin paragraf precis som förut */
/*
var bottom = 0;
$(document).ready(function() {
     $(".refbox").each(function() {
	 this.className = "positioned";
         this.style.top = ($("#"+this.id.substring(5)).offset().top-133)+"px";
         var ideal = $("#"+this.id.substring(5)).offset().top-133;
	 if (ideal > bottom + 20) {
             this.style.top = ideal+"px";
    	     bottom = ideal + $("#"+this.id).height();
	 } else {
            this.style.top = (bottom+10)+"px";
      	    bottom =  bottom + 20 + $("#"+this.id).height();
         }
     })
 });
*/
$(document).ready(function(){
    $("#toc").treeview({
	persist: "location",
        collapsed: true
	});
var data = [ {t:'Link A', l:'/page1'}, {t:'Link B', l: '/page2'} ];
$("#q").autocomplete(docs, {
  matchContains: true,
  selectFirst: false,
  formatItem: function(item) {
    return item.t;
  }
}).result(function(event, item) {
  location.href = item.l;
});
/*
    $("#q").autocomplete(docs, {
	minChars: 0,
        width: 310,
	formatItem: function(item) {
          return item.t;
        }
	matchContains: "word",
        autoFill: false,
    }).result(function(event, item) {
	location.href = item.l;
    });
*/
});
