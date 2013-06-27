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
function set_permissions(type,data){
	BC.ajax(
		{
			'url':set_permissions_url,
			'data':{'json':JSON.stringify(data)},
			'success':function(data){
				console.log(data);
				if(type == 'users')
					update_user_permissions(data);
				else if (type=='groups')
					update_group_permissions(data);
			}
		}
	);
}
function update_share(data){
	BC.ajax(
		{
			'url':update_share_url,
			'data':{'json':JSON.stringify(data)},
			'success':function(data){
				console.log(data);
				BC.add_message("Settings have been updated",{timeout:2000});
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
function add_user(query){
	$.get(get_user_url,{query:query},function(data){
		if(data.errors)
			BC.handle_ajax_errors(data,'#messages');
		else if(data.user){
			data.permissions=[];
			add_user_row(data);
			BC.add_message(data.user.username);
		}
		console.log(data);
	});
}
function add_group(query){
	$.get(get_group_url,{query:query},function(data){
		if(data.errors)
			BC.handle_ajax_errors(data,'#messages');
		else if(data.group){
			data.permissions=[];
			add_group_row(data);
			BC.add_message(data.group.name);
		}
		console.log(data);
	});
}

function add_user_row(obj){
	var row = $('<tr data-username="'+obj.user.username+'"><td>'+obj.user.username+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
	$.each(obj.permissions,function(i,perm){
		$('input[data-perm="'+perm+'"]',row).attr('checked',true);
	});
	$('#user_permissions tbody').append(row);
}

function update_user_permissions(data){
	console.log(data);
	$('#user_permissions tbody').html('');
	//view_share_files, download_share_files, write_to_share, delete_share_files
	$.each(data.user_perms,function(index,obj){
		add_user_row(obj);
	});
}
function add_group_row(obj){
	var row = $('<tr data-group="'+obj.group.name+'"><td>'+obj.group.name+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
	$.each(obj.permissions,function(i,perm){
		$('input[data-perm="'+perm+'"]',row).attr('checked',true);
	});
	$('#group_permissions tbody').append(row);
}
function update_group_permissions(data){
	console.log(data);
	$('#group_permissions tbody').html('');
	//view_share_files, download_share_files, write_to_share, delete_share_files
	$.each(data.group_perms,function(index,obj){
		add_group_row(obj);
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
	$('#updateUserPermissions').click(function(){
		set_permissions('users',{'users':get_user_permissions()});
	});
	$('#updateGroupPermissions').click(function(){
		set_permissions('groups',{'groups':get_group_permissions()});
	});
	$('#addUserButton').click(function(){
		add_user($('#addUser').val());
	});
	$('#addGroupButton').click(function(){
		add_group($('#addGroup').val());
	});
	$('#updateGeneralSettings').click(function(){
		update_share({'secure':$('#secure').prop('checked')});
	});
});