function search_share(query){
	$.get(search_url,{query:query},function(data){
		//console.log(data);
		$('#searchResults').html('');
		$.each(data.results,function(index,result){
			var split_at = result.lastIndexOf("/")+1;
			var directory = result.substring(0, split_at-1);
			var dir_link = '<a href="'+goto_url.replace(goto_url_replace,directory+'/')+'">'+directory+'</a> /';
			var file = result.substring(split_at);
			var file_link = file == '' ? '' : '<a href="'+goto_url.replace(goto_url_replace,result)+'">'+file+'</a>';
			$('#searchResults').append('<div>'+dir_link+' '+file_link+'</div>');
		});
	});
}

function get_selected_names(){
	var selection = [];
	$('.action-check:checked').each(function(){
		selection.push($(this).closest('tr').attr('data-id'));
	});
	return selection;
}
function generate_rsync_string(path){
	var selection = get_selected_names();
//	var path = subpath ? share + '/' + subpath : share;
	var string = 'rsync -vrz adam@phymaptest:'+path+'{'+selection.join(',')+'} /to/my/local/directory';
	$('#rsync-download-command').text(string);
	$('#rsync-download').modal('show');
}
function delete_paths(url,selection){
	BC.ajax(
		{
			'url':url,
			'data':{'json':JSON.stringify({'selection':selection})},
			'success':function(data){
				if(data.deleted){
					$.each(data.deleted,function(index,item){
						$('#file-table [data-id="'+item+'"]').addClass('error').addClass('deleted');
					})
					setTimeout(function(){
							$('#file-table tr.deleted').fadeOut({
								'duration':500,
								'complete':function(){$(this).remove();}
									});
							
							}
						,500);
				}
			}
		}
	);
}
function archive_files(url,selection){
	BC.ajax(
		{
			'url':url,
			'data':{'json':JSON.stringify({'selection':selection})},
			'success':function(data){
				var message = 'Archive ready for <a href="'+data.url+'">download</a>';
				add_message(message);
			}
		}
	);
}
function add_message(content,classes){
	var classes = classes ? classes : ['alert-success'];
	$('#messages').prepend('\
			<div class="alert '+classes.join(' ')+'">\
		    <button type="button" class="close" data-dismiss="alert">×</button>\
		    '+content+'\
		  </div>\
	');
	
}

$(function () {
    $('#fileupload').fileupload({
        url: upload_file_url,
        dataType: 'json',
        done: function (e, data) {
        	console.log('done',data);
            $.each(data.result.files, function (index, file) {
            	var old = $('#file-table tr[data-id="'+file.name+'"]');
            	if(old.length!=0)
            		old.addClass('warning');
            	else{
            		var row = '<tr class="file success" data-id="'+file.name+'"><td><input class="action-check" type="checkbox"/></td><td><i class="fam-page-white"></i><a href="'+file.url+'">'+file.name+'</a></td><td>'+file.size+'</td></tr>';
            		if($('#file-table .directory').length==0)
                    	$(row).prependTo('#file-table tbody');
                    else
                    	$(row).insertAfter('#file-table .directory:last');	
            	}
            });
            $('#progress').hide();
        },
        progressall: function (e, data) {
            var progress = parseInt(data.loaded / data.total * 100, 10);
            $('#progress .bar').css(
                'width',
                progress + '%'
            );
        },
        start: function(e){
        	$('#progress').show();
        }
    });
    $('#create-folder').click(function(){
    		BC.ajax_form_submit('#new-folder-form',{
    			'success':function(data){
    				console.log('',data);
    				$.each(data.objects,function(index,obj){
    					var row = '<tr class="directory real-directory success" data-id="'+obj.name+'"><td><input class="action-check" type="checkbox"/></td><td><a href="'+obj.name+'"><i class="fam-folder"></i>'+obj.name+'</a></td><td></td></tr>';
                        $(row).prependTo('#file-table');	
    				});
    				$('#new-folder').modal('hide');
    				
    			}
    		});
    	});
    $('#toggle-checkbox').change(function(){
		$('.action-check').prop('checked',$(this).prop('checked'));
    });
    $('#launch-action').click(function(){
    	switch($('#action').val()){
    		case 'download':
    			archive_files(archive_files_url,get_selected_names());
    			break;
    		case 'delete':
    			//alert('delete '+get_selected_names());
    			if(confirm('Are you sure you want to delete these files/folders?'))
    				delete_paths(delete_paths_url,get_selected_names());
    			break;
    		case 'rsync':
    			generate_rsync_string(path);
    	}
    });
    $('#searchButton').click(function(){search_share($('#searchBox').val())});
});