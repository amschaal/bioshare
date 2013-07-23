function share_autocomplete(query,process){
	$.get(share_autocomplete_url,{query:query},function(data){
		if(data.errors)
			BC.handle_ajax_errors(data);
		else if(data.shares){
			var shares = $.map(data.shares,function(share,index){
				return '<span data-toggle="tooltip" title="'+share.notes+'" data-url="'+share.url+'">'+share.name+'</span>';
			});
			process(shares);
		}
	});
}
function share_autocomplete_match(obj){
	return true;
}
function share_autocomplete_select(obj) {
	var share = $(obj);
	window.location.href = share.attr('data-url');
	return share.text();
    //window.location.href = obj.url;
}
function preg_quote( str ) {
     return (str+'').replace(/([\\\.\+\*\?\[\^\]\$\(\)\{\}\=\!\<\>\|\:])/g, "\\$1");
}

function highlight( data, search )
{
    return data.replace( new RegExp( "(" + preg_quote( search ) + ")" , 'gi' ), "<b>$1</b>" );
}
function share_autocomplete_highlighter(item){
	console.log('highlight',this.query);
	var text = $(item).text();
	$.each(this.query.split(' '),function(index,term){
		if (term.length >1)
			text = highlight(text,term);
		//text = text.replace(term,'<b>'+term+'</b>');
	});
	return text;
	return $(item).text(text).clone().wrap('<div>').parent().html();
}
$(function () {
	$('#share_autocomplete').typeahead({highlighter:share_autocomplete_highlighter,source:share_autocomplete,updater:share_autocomplete_select,minLength:2,matcher:share_autocomplete_match})
});