function search_share(query){
	$.get(search_url,{query:query},function(data){
		//console.log(data);
		$('#searchResults').html('');
		if (data.results.length==0)
			$('#searchResults').html('No results found');
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
	var files = selection.length > 1 ? '{'+selection.join(',')+'}' : selection.join('');
	var download_string = "rsync -vrt adam@phymaptest:"+path+files+" /to/my/local/directory";
	var upload_string = "rsync -vrt --no-p --no-g --chmod=ugo=rwX /path/to/my/files  adam@phymaptest:"+path;
	
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
	var files = selection.length > 1 ? '{'+selection.join(',')+'}' : selection.join('');
	var download_all_string = "rsync -vrt "+rsync_url+":"+path+" /to/my/local/directory";
	var download_string = "rsync -vrt "+rsync_url+":"+path+files+" /to/my/local/directory";
	
	$('#rsync-download-selected').text(download_string);
	$('#rsync-download-all').text(download_all_string);
	$('#rsync-download').modal('show');
}

function generate_rsync_upload(share,subpath){
	var re = new RegExp(' ', 'g');
	var path = subpath ? '/'+ share + '/' + subpath: '/'+share+'/';
	if (path.indexOf(' ') > -1)
		path = "'"+path.replace(re,'\\ ')+"'";
	var upload_string = "rsync -vrt --no-p --no-g --chmod=ugo=rwX /path/to/my/files "+rsync_url+":"+path;
	$('#rsync-upload-command').text(upload_string);
	$('#rsync-upload').modal('show');
}
function delete_paths(url,selection){
	BC.ajax(
		{
			'url':url,
			'data':{'selection':selection},
			'success':function(data){
				if(data.failed.length !=0){
					var message = "The following files were unable to be deleted: " + data.failed.join(', ');
					message += "<br>The filesystem may be read only.";
					$.bootstrapGrowl(message,{type:'error',delay: 10000});
				}
				if(data.deleted){
					$.each(data.deleted,function(index,item){
						$('#file-table [data-id="'+item+'"]').addClass('error').addClass('deleted');
					});
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
function generate_wget_download(share,subpath){
		//wget -r -nH -nc --cut-dirs=3 --no-parent --reject "index.html" http://127.0.0.1:8002/bioshare/wget/0000001234567890/wget_index.html
		var re = new RegExp(' ', 'g');
		var path = subpath ? '/'+ share + '/' + subpath: '/'+share+'/';
		if (path.indexOf(' ') > -1)
			path = path.replace(re,'\\ ');
		var command = '-r --level=10 -nH -nc --cut-dirs=3 --no-parent --reject "wget_index.html" --no-check-certificate --header "Cookie: sessionid='+session_cookie+';" https://'+ base_url + '/bioshare/wget'+path+'wget_index.html';
		$('#wget-linux').text('wget '+command);
		$('#wget-windows').text('"C:\\Program Files\\GnuWin32\\bin\\wget.exe" '+command);
		$('#wget-download').modal('show');
}
function archive_files(selection){
	if(selection.length  == 0){
		alert('Please select at least 1 file to be archived.');
	}
	else{
		$('#archive_selection').val(selection.join(','));
		$('#download_archive_form').submit();
		$.bootstrapGrowl('Download started',{type:'success'});
	}
	
//	if(selection.length  == 0)
//		alert('Please select at least 1 file to be archived.');
//	else
//		BC.ajax(
//			{
//				'url':url,
//				'data':{'json':JSON.stringify({'selection':selection})},
//				'success':function(data){
//					if(data.url){
//						var message = 'Archive ready for <a href="'+data.url+'">download</a>';
//						$.bootstrapGrowl(message,{delay: 100000000,type:'success'});
//					}
//				}
//			}
//		);
}
function archive_files_old(url,selection){
	if(selection.length  == 0)
		alert('Please select at least 1 file to be archived.');
	else
		BC.ajax(
			{
				'url':url,
				'data':{'json':JSON.stringify({'selection':selection})},
				'success':function(data){
					if(data.url){
						var message = 'Archive ready for <a href="'+data.url+'">download</a>';
						$.bootstrapGrowl(message,{delay: 100000000,type:'success'});
					}
				}
			}
		);
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
function preview_share_action(){
	var row = $(this).closest('tr');
	var path = subpath ? subpath + row.attr('data-id') : row.attr('data-id');
	preview_file(share,path);	
}
function calculate_md5(){
	var row = $(this).closest('tr');
	var path = subpath ? subpath + row.attr('data-id') : row.attr('data-id');
	var el = $('<span>Calculating...</span>').replaceAll(this);
	console.log('el',el);
	BC.ajax(
			{
				'url':'/bioshare/md5sum/'+share+'/'+path,
				'success':function(data){
						console.log('md5',data);
//						$.bootstrapGrowl("File: "+data.path+"<br>MD5: "+data.md5sum,{type:'success',delay: 10000});
						$(el).replaceWith('<span class="md5sum">'+data.md5sum+'</span>');
				}
			}
		);
}
function edit_metadata(){
	var id = $('#metadata-id').val();
	var url = metadata_url+id;
	
	BC.ajax_form_submit('#edit-metadata-form',
		{
			'ajax':{
				'type':'POST',
				'url':url,
				'data':{'tags':$('#edit-metadata-form [name=tags]').val(),'notes':$('#edit-metadata-form [name=notes]').val()}
			},
			'success':function(data){
				if(data.name){
					$('#edit-metadata').modal('hide');
					var row = $('#file-table [data-id="'+id+'"]');
					var tags_html = BC.run_template('tags-template',data.tags);
					var rowIndex = filetable.fnGetPosition(row[0]);
					filetable.fnUpdate(tags_html,rowIndex,3);//3 is for column index
//					row.find('.tags').html(tags_html);
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
function create_folder(){
		BC.ajax_form_submit('#new-folder-form',{
			'success':function(data){
				$.each(data.objects,function(index,obj){
					var html = BC.run_template('directory-template',obj);
					//var row = '<tr class="directory real-directory success" data-id="'+obj.name+'"><td><input class="action-check" type="checkbox"/></td><td><a href="'+obj.name+'"><i class="fam-folder"></i>'+obj.name+'</a></td><td></td><td></td></tr>';
                    var row = $(html).prependTo('#file-table');
                    filetable._fnAddTr(row[0]);
                    $.bootstrapGrowl('"'+obj.name+'" folder created',{type:'info',delay: 3000});
				});
				$('#new-folder').modal('hide');
				toggle_table_visibility();
			}
		});
		return false;
}

function create_link(){
	BC.ajax_form_submit('#new-link-form',{
		'success':function(data){
			$.each(data.objects,function(index,obj){
				if (obj.type == 'symlink') {
					if (obj.display) {
						var html = BC.run_template('link-template',obj);
						var row = $(html).prependTo('#file-table');
						filetable._fnAddTr(row[0]);
					}
					$.bootstrapGrowl('"'+obj.name+'" link created',{type:'info',delay: 3000});
				} else if (obj.type == 'directory') {
					if (obj.display) {
						var html = BC.run_template('directory-template',obj);
						//var row = '<tr class="directory real-directory success" data-id="'+obj.name+'"><td><input class="action-check" type="checkbox"/></td><td><a href="'+obj.name+'"><i class="fam-folder"></i>'+obj.name+'</a></td><td></td><td></td></tr>';
						var row = $(html).prependTo('#file-table');
						filetable._fnAddTr(row[0]);
					}
                    $.bootstrapGrowl('"'+obj.name+'" folder created',{type:'info',delay: 3000});
				}
			});
			$('#new-link').modal('hide');
			toggle_table_visibility();
		}
	});
	return false;
}

function unlink(){
	if (!confirm('Are you sure you want to unlink this directory?'))
		return;
	var row = $(this).closest('tr');
	var path = subpath ? subpath + row.attr('data-id') : row.attr('data-id');
	BC.ajax(
			{
				'url':'/bioshare/unlink/'+share+'/'+path,
				'success':function(data){
						console.log('unlink',data);
//						$.bootstrapGrowl("File: "+data.path+"<br>MD5: "+data.md5sum,{type:'success',delay: 10000});
						// $(el).replaceWith('<span class="md5sum">'+data.md5sum+'</span>');
						row.addClass('error').addClass('deleted');
						setTimeout(function(){
								$('#file-table tr.deleted').fadeOut({
									'duration':500,
									'complete':function(){filetable.fnDeleteRow($(this)[0]);toggle_table_visibility();}
										});
								}
							,500);
				},
				'error': BC.on_ajax_error
			}
		);
}

function open_rename_form(){
	var row = $(this).closest('tr');
//	$('#edit-metadata-form [name=notes]').val(row.attr('data-notes'));
	var from_name = row.attr('data-id');
	$('#rename-from-label').text(from_name);
	$('#modify-name-form [name=from_name]').val(from_name);
	$('#modify-name-form [name=to_name]').val(from_name);
	$('#modify-name').modal('show');
}

function modify_name(){
	BC.ajax_form_submit('#modify-name-form',{
		'success':function(data){
			$.each(data.objects,function(index,obj){
				//var html = BC.run_template('directory-template',obj);
				//var row = '<tr class="directory real-directory success" data-id="'+obj.name+'"><td><input class="action-check" type="checkbox"/></td><td><a href="'+obj.name+'"><i class="fam-folder"></i>'+obj.name+'</a></td><td></td><td></td></tr>';
                //var row = $(html).prependTo('#file-table');
                //filetable.fnAddTr(row[0]);
				var a = $('#file-table [data-id="'+obj.from_name+'"]').attr('data-id',obj.to_name).find('td.name a').text(obj.to_name);
                a.attr('href',a.attr('href').replace(obj.from_name,obj.to_name));
				$.bootstrapGrowl('"'+obj.from_name+'" renamed "'+obj.to_name+'"',{type:'info',delay: 3000});
			});
			$('#modify-name').modal('hide');
		}
	});
	return false;
}

function open_move_modal(){
	if (!BC.move_modal_initialized && share_perms.indexOf("write_to_share") > -1 && share_perms.indexOf("delete_share_files") > -1 )
    	init_dynatree();
	$("#tree").dynatree("getTree").reload();
	$('#move-to-modal').modal('show');
}

function move_files(url,selection){
	var selected = $("#tree").dynatree("getSelectedNodes")[0];
	var destination = selected ? $("#tree").dynatree("getSelectedNodes")[0].data.key : '';
	if(subpath==destination+'/'){
		alert('Why would you want to move things to the same directory?  That\'s just silly!');
		return;
	}
	BC.ajax(
			{
				'url':url,
				'data':{'json':{'selection':selection,'destination':destination}},
				'success':function(data){
					if(data.failed.length !=0){
						var message = "The following files were unable to be moved: " + data.failed.join(', ');
						message += "<br>The filesystem may be read only.";
						$.bootstrapGrowl(message,{type:'error',delay: 10000});
					}
					if(data.moved){
						$.each(data.moved,function(index,item){
							$('#file-table [data-id="'+item+'"]').addClass('error').addClass('moved');
						});
						var message = "The following files were moved to '"+destination+"': " + data.moved.join(', ');
						$.bootstrapGrowl(message,{type:'success',delay: 10000});
						setTimeout(function(){
								$('#file-table tr.moved').fadeOut({
									'duration':500,
									'complete':function(){filetable.fnDeleteRow($(this)[0]);toggle_table_visibility();}
										});
								}
							,500);
						$('#move-to-modal').modal('hide');
					}
				}
			}
		);

}

function init_dynatree(){
	 $("#tree").dynatree({
	      title: "Lazy loading sample",
	      fx: { height: "toggle", duration: 200 },
	      checkbox: true,
	      // Override class name for checkbox icon:
	      classNames: {checkbox: "dynatree-radio"},
	      selectMode: 1,
	      autoFocus: false, // Set focus to first child, when expanding or lazy-loading.
	      // In real life we would call a URL on the server like this:
//	          initAjax: {
//	              url: "/getTopLevelNodesAsJson",
//	              data: { mode: "funnyMode" }
//	              },
	      // .. but here we use a local file instead:
	      initAjax: {
	        url: get_directories_url
	        },

//	      onActivate: function(node) {
//	        $("#echoActive").text("" + node + " (" + node.getKeyPath()+ ")");
//	      },

	      onLazyRead: function(node){
	        // In real life we would call something like this:
	              node.appendAjax({
	                  url: get_directories_url,
	                data: {directory: node.data.key,
	                       mode: "funnyMode"
	                         }
	              });
	        // .. but here we use a local file instead:
//	        node.appendAjax({
//	          url: "sample-data2.json",
//	          // We don't want the next line in production code:
//	          debugLazyDelay: 750
//	        });
	      }
	    });
	 BC.move_modal_initialized = true;

}

$(function () {
	$(document).on('click','[data-action="edit-metadata"]',open_metadata_form);
	$(document).on('click','[data-action="preview"]',preview_share_action);
	$(document).on('click','[data-action="calculate-md5"]',calculate_md5);
	$(document).on('click','[data-action="modify-name"]',open_rename_form);
	$(document).on('click','[data-action="unlink"]',unlink);
	
	toggle_table_visibility();
	BC.load_templates()
    $('#fileupload').fileupload({
        url: upload_file_url,
        dataType: 'json',
		error: BC.on_ajax_error,
        done: function (e, data) {
            $.each(data.result.files, function (index, file) {
            	var old = $('#file-table tr[data-id="'+file.name+'"]');
            	if(old.length!=0){
            		old.addClass('warning');
            		$.bootstrapGrowl('Overwrote file: '+file.name,{type:'info',delay: 3000});
            	}
            	else{
            		file.download = share_perms.indexOf('download_share_files') > -1;
            		//var row = '<tr class="file success" data-id="'+file.name+'" data-bytes="'+file.bytes+'"><td><input class="action-check" type="checkbox"/></td><td><i class="fam-page-white"></i><a href="'+file.url+'">'+file.name+'</a></td><td>'+file.size+'</td><td>'+file.modified+'</td></tr>';
            		var row = BC.run_template('file-template',file);
            		if($('#file-table .directory').length==0)
                    	var row = $(row).prependTo('#file-table tbody');
                    else
                    	var row = $(row).insertAfter('#file-table .directory:last');
            		filetable._fnAddTr(row[0]);
            		$.bootstrapGrowl('Successfully uploaded '+file.name,{type:'success',delay: 3000});
            	}
            });
			$.each(data.result.errors, function (index, error) {
				$.bootstrapGrowl(error,{type:'error',delay: 10000});
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
    $('#create-folder').click(create_folder);
	$('#create-link').click(create_link);
    $('#rename-button').click(modify_name);
    $('#new-folder-form').submit(create_folder);
	$('#new-link-form').submit(create_link);
    $('#open-move-modal').click(open_move_modal);
    $('#move-button').click(function(){
    	if(confirm('Are you sure you want to move these files/folders?'))
    		move_files(move_paths_url,get_selected_names());
    });
    $('#toggle-checkbox').change(function(){
		$('.action-check').prop('checked',$(this).prop('checked'));
    });
    $('#download-zip').click(function(){
    	archive_files(get_selected_names());
    });
    $('#download-rsync').click(function(){
    	generate_rsync_download(share,subpath);
    });
    $('#download-wget').click(function(){
    	generate_wget_download(share,subpath);
    });
    $('.open-sftp').click(function(){
    	$('#sftp-dialog').modal('show');
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
    			archive_files(get_selected_names());
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
    $('#searchForm').submit(function(){search_share($('#searchBox').val()); return false;});
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
