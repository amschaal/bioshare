angular.module("bioshare", ["ngTable","ngResource"]);

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

/* Start file preview code */
var  preview_stats={};
//function disable_more_button(){
//	$('#preview-more').prop('disabled', true);
//	$('#preview-more').unbind();
//}
//function enable_more_button(share_id,subpath,from,lines){
//	
//	$('#preview-more').prop('disabled', false);
//	$('#preview-more').unbind();
//	$('#preview-more').click(function(){
//		preview_file(share_id,subpath,from,lines);
//	});
//}
function disable_scroll_load(){
	$('#preview-file-area').unbind('scroll');
}
function enable_scroll_load(share_id,subpath,from,lines){
	
	$('#preview-file-area').bind('scroll', function(){
          if($(this).scrollTop() + $(this).innerHeight()>=$(this)[0].scrollHeight)
          {
        	  disable_scroll_load();
        	  preview_file(share_id,subpath,from,lines);
          }
    })
}
function reset_file_preview(){
	disable_scroll_load();
	$('#preview-file-area').text('');
	$('#lines-loaded').text('');
	preview_stats={};
}
function close_file_preview(){
	reset_file_preview();
	$('#preview-file').modal('hide');
}
function preview_file(share_id,subpath,from,lines){
	var data = {};
	if(!from || ! lines){//first call
		reset_file_preview();
		var from = 1;
		var lines = 100;
		$('#preview-file').modal('show');
		$('#preview-share-id').text(share_id);
		$('#preview-subpath').text(subpath);
//		disable_more_button();
		data['get_total']=true;
	}
	data['from']= from;
	data['for']= lines;
	
	var url = preview_file_url.replace('000000000000000',share_id)+subpath;
//	return url;
	disable_scroll_load();
	$.get(url,data,function(data){
		if(data.errors){
			BC.handle_ajax_errors(data);
			return;
		}
		if(data.total){
			preview_stats.total = data.total;
		}
		preview_stats.current_last_line = preview_stats.total < data.next['from'] ? preview_stats.total : data.next['from'] - 1;
		preview_stats.percentage = Math.floor(preview_stats.current_last_line * 100 / preview_stats.total);
		$('#lines-loaded').text('Showing '+preview_stats.current_last_line+' of '+preview_stats.total+' lines ('+preview_stats.percentage+'%)');
		if(data.content){
//			data.content.replace(/<|>/ig,function(m){
//			    return '&'+(m=='>'?'g':'l')+'t;';
//			})
			$('#preview-file-area').append(
					data.content.replace(/<|>/ig,function(m){
					    return '&'+(m=='>'?'g':'l')+'t;';
					})
			);
//			$('#preview-file-area').html($('#preview-file-area').html()+data.content);
//			enable_more_button(share_id,subpath,data.next['from'],data.next['for']);
			
		}else{
//			disable_scroll_load();
//			disable_more_button();
		}
		if(preview_stats.current_last_line < preview_stats.total)
			enable_scroll_load(share_id,subpath,data.next['from'],data.next['for']);
			
	});
}
$(function () {
	$('#preview-file').on('hide', reset_file_preview);
});
/* End file preview code */