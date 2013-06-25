function get_selected_names(){
	var selection = [];
	$('.action-check:checked').each(function(){
		selection.push($(this).closest('tr').attr('data-id'));
	});
	return selection;
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
function get_permissions(){
	$.get(get_permissions_url,function(data){
		update_user_permissions(data);
		update_group_permissions(data);
	});
}
function update_user_permissions(data){
	console.log(data);
	$('#user_permissions tbody').html();
	//view_share_files, download_share_files, write_to_share, delete_share_files
	$.each(data.user_perms,function(index,obj){
		var row = $('<tr data-username="'+obj.user.username+'"><td>'+obj.user.username+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td></tr>').data('permissions',obj.permissions);
		$.each(obj.permissions,function(i,perm){
			$('input[data-perm="'+perm+'"]',row).attr('checked',true);
		});
		$('#user_permissions tbody').append(row);
	});
}
function update_group_permissions(data){
	console.log(data);
	$('#group_permissions tbody').html();
	//view_share_files, download_share_files, write_to_share, delete_share_files
	$.each(data.group_perms,function(index,obj){
		var row = $('<tr data-group="'+obj.group+'"><td>'+obj.group+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td></tr>').data('permissions',obj.permissions);
		$.each(obj.permissions,function(i,perm){
			$('input[data-perm="'+perm+'"]',row).attr('checked',true);
		});
		$('#group_permissions tbody').append(row);
	});
}

function check_permissions_modified(){
	var row = $(this).closest('tr');
	var permissions = row.data('permissions');
	var modified = false;
	row.find('input[data-perm]').each(function(){
		if($(this).prop('checked') && permissions.indexOf($(this).attr('data-perm'))==-1)
			modified=true;
		else if(!$(this).prop('checked') && permissions.indexOf($(this).attr('data-perm'))!=-1)
			modified=true;
	});
	if(modified)
		row.addClass('modified');
	else
		row.removeClass('modified');
	
	console.log($(this).attr('data-perm'));
}

function get_user_permissions(){
	var permissions={};
	$('#user_permissions tr.modified[data-username]').each(function(){
		var username = $(this).attr('data-username');
		permissions[username]=[];
		$(this).find('input[data-perm]').each(function()
			{
				if($(this).prop('checked'))
					permissions[username].push( $(this).attr('data-perm'));
			});
	});
	return permissions;
}
function get_group_permissions(){
	var permissions={};
	$('#group_permissions tr.modified[data-group]').each(function(){
		var group = $(this).attr('data-group');
		permissions[group]=[];
		$(this).find('input[data-perm]').each(function()
			{
				if($(this).prop('checked'))
					permissions[group].push( $(this).attr('data-perm'));
			});
	});
	return permissions;
}

$(function () {
	console.log('Permissions');
	get_permissions();
	$(document.body).on('change','input[data-perm]',check_permissions_modified);
});