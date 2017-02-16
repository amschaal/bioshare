var ALL_PERMISSIONS = ['view_share_files', 'download_share_files', 'write_to_share', 'delete_share_files','admin'];
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
function set_permissions(data){
	$('#updateUserPermissions').prop('disabled',true).text('Updating...');
	BC.ajax(
		{
			'url':set_permissions_url,
			'data':{'json':JSON.stringify(data)},
			'success':function(data){
					update_permissions(data);
					$('#updateUserPermissions').prop('disabled',false).text('Update');
					$.bootstrapGrowl("Permissions have been updated",{type:'success',delay:2000});
			},
			'error':function(){
				$('#updateUserPermissions').prop('disabled',false).text('Update');
				$.bootstrapGrowl("There was an error updating permissions",{type:'error',delay:2000});
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
				$.bootstrapGrowl("Settings have been updated",{type:'info',delay:2000});
			}
		}
	);
}

function get_permissions(){
	$.get(get_permissions_url,function(data){
		update_permissions(data);
	});
}

function update_permissions(data){
	//console.log(data);
	$('#user_permissions tbody').html('');
	//view_share_files, download_share_files, write_to_share, delete_share_files
	$.each(data.user_perms,function(index,obj){
		add_permission_row(obj);
	});
	$.each(data.group_perms,function(index,obj){
		add_permission_row(obj);
	});
	show_hide_permissions();
}
function check_row_permissions_modified(row){
	var permissions = row.data('permissions');
	var modified = false;
	row.find('input[data-perm]').each(function(){
		if($(this).prop('checked') && permissions.indexOf($(this).attr('data-perm'))==-1)
			modified=true;
		else if(!$(this).prop('checked') && permissions.indexOf($(this).attr('data-perm'))!=-1)
			modified=true;
	});
	if (permissions.length == 0 && modified && $('#email_users').prop('checked')){
		if(row.find('.fam-email').length == 0)
			row.find('td').first().append('<i class="fam-email" style="margin-left:5px" ></i>');
	}else
		row.find('.fam-email').remove();
	if (permissions.length > 0 && row.find('input[data-perm]:checked').length == 0){
		if(row.find('.fam-cross').length == 0)
			row.find('td').first().append('<i class="fam-cross" style="margin-left:5px" data-toggle="tooltip" title="Remove access from this user"></i>');
	}else
		row.find('.fam-cross').remove();
	if(modified)
		row.addClass('modified');
	else
		row.removeClass('modified');
	
}
function check_permissions_modified(){
	var row = $(this).closest('tr');
	check_row_permissions_modified(row);
}
function refresh_permission_rows(){
	$('#user_permissions tbody tr').each(function(){
		check_row_permissions_modified($(this));
	});
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
	$('#user_permissions tr.modified[data-group-id]').each(function(){
		var group = $(this).attr('data-group-id');
		permissions[group]=[];
		$(this).find('input[data-perm]').each(function()
			{
				if($(this).prop('checked'))
					permissions[group].push( $(this).attr('data-perm'));
			});
	});
	return permissions;
}
function show_hide_permissions(){
	if($('#user_permissions tbody tr').length == 0)
		$('#user-permission-section').hide();
	else
		$('#user-permission-section').show();
}

function add_permission_row(obj){
	if (!obj.permissions)
		obj.permissions = [];
	var write_permissions = read_only ? '' : '<td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td>';
	var check_uncheck_controls = '<td><i class="fam-accept check_all" title="Check all permissions"></i> <i class="fam-delete uncheck_all" title="Uncheck all permissions"></i></td>';
	if (obj.user){
		if ($('.permissions tr[data-username="'+obj.user.username+'"]').length == 0){
			var classes = obj.new_user ? 'new-user ' : '';
			var warning = obj.new_user ? ' <i class="fam-error-add" data-toggle="tooltip" title="An account will automatically be made for this email address"></i>' : '';
			var row = $('<tr data-username="'+obj.user.username+'" class="'+classes+'"><td><i class="fam-user"></i>'+obj.user.username + warning+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td>'+write_permissions+'<td><input data-perm="admin" type="checkbox"></td>'+check_uncheck_controls+'</tr>').data('permissions',obj.permissions);
		}
	}else if(obj.group){
		if ($('.permissions tr[data-group-id="'+obj.group.id+'"]').length == 0)
			var row = $('<tr data-group-id="'+obj.group.id+'" class="'+classes+'"><td><i class="fam-group"></i>'+obj.group.name+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td>'+write_permissions+'<td><input data-perm="admin" type="checkbox"></td>'+check_uncheck_controls+'</tr>').data('permissions',obj.permissions);
	}
	
	$.each(obj.permissions.length ? obj.permissions : ['view_share_files','download_share_files'],function(i,perm){
		$('input[data-perm="'+perm+'"]',row).prop('checked',true);
	});
	$('#user_permissions tbody').append(row);
	if (row)
		check_row_permissions_modified(row);
}

function update_row_permissions(row,permissions){
	$('input[data-perm]',row).prop('checked',false);
	$.each(permissions ,function(i,perm){
		$('input[data-perm="'+perm+'"]',row).prop('checked',true);
	});
	check_row_permissions_modified(row);
}

function share_with(query){
	$.get(share_with_url,{query:query},function(data){
		if(data.errors)
			BC.handle_ajax_errors(data,'#messages');
		else{
			$.each(data.exists,function(index,obj){
//				obj.permissions=[];
				add_permission_row(obj,'user');
			});
			$.each(data.groups,function(index,obj){
//				obj.permissions=[];
				add_permission_row(obj,'group');
			});
			$.each(data.new_users,function(index,obj){
//				obj.permissions=[];
				obj.new_user = true;
				add_permission_row(obj,'user');
			});
			if(data.invalid.length != 0){
				var emails = data.invalid.join(', ');
				$.bootstrapGrowl('The following emails are invalid: '+emails,{type:'error',delay: 10000});
			}
			if(data.new_users.length != 0){
				var emails = $.map(data.new_users,function(obj,ind){return obj.user.username;}).join(', ');
				$.bootstrapGrowl('Accounts will automatically be made for the following new users: '+emails,{type:'info',delay: 10000});
			}
			$('#addUser').val('');
		}
		show_hide_permissions();
	});
}
function check_all(){
	update_row_permissions($(this).closest('tr'),ALL_PERMISSIONS)
}
function uncheck_all(){
	console.log('uncheck',this)
	update_row_permissions($(this).closest('tr'),[])
}
$(function () {
	get_permissions();
	$(document.body).on('change','input[data-perm]',check_permissions_modified);
	$('#updateUserPermissions').click(function(){
		set_permissions({'users':get_user_permissions(),'groups':get_group_permissions(),'email':$('#email_users').prop('checked')});
	});
	$('#email_users').click(refresh_permission_rows);
	$('#addUserButton').click(function(){
		share_with($('#addUser').val());
	});
	$('#updateGeneralSettings').click(function(){
		update_share({'secure':$('#secure').prop('checked')});
	});
	$('#addUser').textcomplete([
	                            { // mention strategy
//	                              match:  /@(\w{2,})$/,
	                              search: function (term, callback) {
	                            	  var searchTerm = term;
//	                            	  console.log('term',term);
	                                //callback(cache[term], true);
	                                $.getJSON('/bioshare/api/get_addresses/', { q: term })
	                                  .done(function (resp) {
//	                                	  console.log('term',searchTerm);
	                                	  callback($.map(resp.emails, function (email) {
		  	                              		                return email.toLowerCase().indexOf(term.toLowerCase()) === 0 ? email : null;
		  	                            		            	}),true); 
	                                	  callback($.map(resp.groups, function (group) {
		  	                              		                return group.toLowerCase().indexOf(term.toLowerCase()) === 0 ? 'Group:'+ group : null;
		  	                            		            	}));
//	                                	  callback(resp.emails);   
	                                  })
	                                  .fail(function ()     { callback([]);   });
	                              },
//	                              replace: function (word) {
//	                                  return word + ', ';
//	                              },
	                              cache: true,
	                              template: function (value) {
	                            	  if (value.toLowerCase().indexOf('group:') === 0)
	                            		  return '<i class="fam-group"></i>' + value;
	                            	  else 
	                            		  return '<i class="fam-user"></i>' + value;
	                              },
	                              match: /(^|\s)(\w*)$/,
	                            	  replace: function (value) { return '$1' + value + ', '; }
	                            }
    ]);
	$('#user_permissions').on('click','.check_all',check_all);
	$('#user_permissions').on('click','.uncheck_all',uncheck_all);
});

