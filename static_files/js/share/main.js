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
function generate_rsync_strings(share,subpath){
	var re = new RegExp(' ', 'g');
	var selection = get_selected_names();
	for(var i in selection){
		if (selection[i].indexOf(' ') > -1)
			selection[i] = "'"+selection[i].replace(re,'\\ ')+"'";
	}
	
	var path = subpath ? '/'+ share + '/' + subpath: '/'+share+'/';
	if (path.indexOf(' ') > -1)
		path = "'"+path.replace(re,'\\ ')+"'";
	var files = selection.length > 0 ? '{'+selection.join(',')+'}' : '';
	var download_string = "rsync -vrz adam@phymaptest:"+path+files+" /to/my/local/directory";
	var upload_string = "rsync -vrz /path/to/my/files  adam@phymaptest:"+path;
	
	$('#rsync-download-command').text(download_string);
	$('#rsync-upload-command').text(upload_string);
	$('#rsync-download').modal('show');
}
function generate_rsync_download(share,subpath){
	var re = new RegExp(' ', 'g');
	var selection = get_selected_names();
	for(var i in selection){
		if (selection[i].indexOf(' ') > -1)
			selection[i] = "'"+selection[i].replace(re,'\\ ')+"'";
	}
	
	var path = subpath ? '/'+ share + '/' + subpath: '/'+share+'/';
	if (path.indexOf(' ') > -1)
		path = "'"+path.replace(re,'\\ ')+"'";
	var files = selection.length > 0 ? '{'+selection.join(',')+'}' : '';
	var download_all_string = "rsync -vrz "+rsync_url+":"+path+" /to/my/local/directory";
	var download_string = "rsync -vrz "+rsync_url+":"+path+files+" /to/my/local/directory";
	
	$('#rsync-download-selected').text(download_string);
	$('#rsync-download-all').text(download_all_string);
	$('#rsync-download').modal('show');
}
function generate_rsync_upload(share,subpath){
	var re = new RegExp(' ', 'g');
	var path = subpath ? '/'+ share + '/' + subpath: '/'+share+'/';
	if (path.indexOf(' ') > -1)
		path = "'"+path.replace(re,'\\ ')+"'";
	var upload_string = "rsync -vrz /path/to/my/files "+rsync_url+":"+path;
	$('#rsync-upload-command').text(upload_string);
	$('#rsync-upload').modal('show');
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
								'complete':function(){filetable.fnDeleteRow($(this)[0]);toggle_table_visibility();}
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
				if(data.url){
					var message = 'Archive ready for <a href="'+data.url+'">download</a>';
					add_message(message);
				}
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
function toggle_table_visibility(){
	if($('#file-table tbody tr').length == 1){
		$('#add-files-message').removeClass('hidden');
	}else{
		$('#add-files-message').addClass('hidden');
	}
}
function open_metadata_form(){
	var row = $(this).closest('tr');
	$('#edit-metadata-form').html($('#edit-meta-data-form-clean').html());
	$('#edit-metadata-form [name=notes]').val(row.attr('data-notes'));
	$('#edit-metadata-form [name=tags]').val(row.attr('data-tags'));
	$('#metadata-label').text(row.attr('data-id'));
	$('#metadata-id').val(row.attr('data-id'));
	$('#edit-metadata').modal('show');
	
}
function edit_metadata(){
	var id = $('#metadata-id').val();
	var url = metadata_url+id;
	
	BC.ajax_form_submit('#edit-metadata-form',
		{
			'ajax':{
				'url':url,
				'data':{'tags':$('#edit-metadata-form [name=tags]').val(),'notes':$('#edit-metadata-form [name=notes]').val()}
			},
			'success':function(data){
				if(data.name){
					$('#edit-metadata').modal('hide');
					var row = $('#file-table [data-id="'+id+'"]');
					var tags_html = BC.run_template('tags-template',data.tags);
					row.find('.tags').html(tags_html);
					row.attr('data-notes',data.notes);
					row.attr('data-tags',data.tags);
					var name_col = row.find('.name');
					name_col.attr('data-toggle','tooltip');
					name_col.attr('title',data.notes);
				}
			}
		}			
	);
//	BC.ajax(
//			{
//				'url':url,
//				'data':{'tags':$('#edit-metadata-form [name=tags]').val(),'notes':$('#edit-metadata-form [name=notes]').val()},
//				'success':function(data){
//					if(data.name){
//						$('#edit-metadata').modal('hide');
//						var row = $('#file-table [data-id="'+id+'"]');
//						var tags_html = BC.run_template('tags-template',data.tags);
//						row.find('.tags').html(tags_html);
//						row.attr('data-notes',data.notes);
//						row.attr('data-tags',data.tags);
//						var name_col = row.find('.name');
//						name_col.attr('data-toggle','tooltip');
//						name_col.attr('title',data.notes);
//					}
//				}
//			}
//		);
}
$(function () {
	$(document).on('click','[data-action="edit-metadata"]',open_metadata_form);
	
	toggle_table_visibility();
	BC.load_templates()
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
            		file.download = share_perms.indexOf('download_share_files') > -1;
            		//var row = '<tr class="file success" data-id="'+file.name+'" data-bytes="'+file.bytes+'"><td><input class="action-check" type="checkbox"/></td><td><i class="fam-page-white"></i><a href="'+file.url+'">'+file.name+'</a></td><td>'+file.size+'</td><td>'+file.modified+'</td></tr>';
            		var row = BC.run_template('file-template',file);
            		if($('#file-table .directory').length==0)
                    	var row = $(row).prependTo('#file-table tbody');
                    else
                    	var row = $(row).insertAfter('#file-table .directory:last');
            		filetable.fnAddTr(row[0]);
            	}
            });
            $('#progress').hide();
            toggle_table_visibility();
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
    					var html = BC.run_template('directory-template',obj);
    					//var row = '<tr class="directory real-directory success" data-id="'+obj.name+'"><td><input class="action-check" type="checkbox"/></td><td><a href="'+obj.name+'"><i class="fam-folder"></i>'+obj.name+'</a></td><td></td><td></td></tr>';
                        var row = $(html).prependTo('#file-table');
                        filetable.fnAddTr(row[0]);
    				});
    				$('#new-folder').modal('hide');
    				toggle_table_visibility();
    			}
    		});
    	});
    $('#toggle-checkbox').change(function(){
		$('.action-check').prop('checked',$(this).prop('checked'));
    });
    $('#download-zip').click(function(){
    	archive_files(archive_files_url,get_selected_names());
    });
    $('#download-rsync').click(function(){
    	generate_rsync_download(share,subpath);
    });
    $('#upload-rsync').click(function(){
    	generate_rsync_upload(share,subpath);
    });
    $('#delete-button').click(function(){
    	if(confirm('Are you sure you want to delete these files/folders?'))
			delete_paths(delete_paths_url,get_selected_names());
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
    			generate_rsync_strings(share,subpath);
    	}
    });
    $('#searchButton').click(function(){search_share($('#searchBox').val())});
    $('#save-metadata').click(edit_metadata);
    $('#file-table').on('click','span.tag',function(){hide_other_tags($(this).text())});
    filtered_tags = [];
    $('#reset-tag-button').click(reset_tags);
});
function hide_other_tags(tag){
	if(filtered_tags.indexOf(tag) >= 0)
		return;
	filtered_tags.push(tag);
	$('tr.file,tr.directory','#file-table').each(function(index,row){
		if($(row).attr('data-tags')=='')
			$(row).addClass('hide-me');
		var tags=$(row).attr('data-tags').split(',');
		if(tags.indexOf(tag) < 0)
			$(row).addClass('hide-me');
	});
	$('#file-table tr.hide-me').hide();
	$('#filtered-tags').text(filtered_tags.join(', '));
	$('#reset-tags').show();
//	setTimeout(function(){
//		$('#file-table tr.hide-me').hide();
//			$('#file-table tr.hide-me').fadeOut({
//				'duration':200//,
////				'complete':function(){$(this).remove();}
//			});
//		}
//	,500);
}
function reset_tags(){
	$('#file-table tr.hide-me').show().removeClass('hide-me');
	$('#reset-tags').hide();
	filtered_tags = [];
}