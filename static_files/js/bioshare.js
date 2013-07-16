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
function share_autocomplete_select(obj) {
	var share = $(obj);
	window.location.href = share.attr('data-url');
	return share.text();
    //window.location.href = obj.url;
}
$(function () {
	$('#share_autocomplete').typeahead({source:share_autocomplete,updater:share_autocomplete_select,minLength:2})
});