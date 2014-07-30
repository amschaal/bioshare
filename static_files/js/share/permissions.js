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
	BC.ajax(
		{
			'url':set_permissions_url,
			'data':{'json':JSON.stringify(data)},
			'success':function(data){
					update_permissions(data);
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
//function add_user(query){
//	$.get(share_with_emails_url,{query:query},function(data){
//		if(data.errors)
//			BC.handle_ajax_errors(data,'#messages');
//		else{
//			$.each(data.exists,function(index,obj){
//				obj.permissions=[];
//				add_user_row(obj);
//			});
//			$.each(data.new_users,function(index,obj){
//				obj.permissions=[];
//				obj.new_user = true;
//				add_user_row(obj);
//			});
//			if(data.invalid.length != 0){
//				var emails = data.invalid.join(', ');
//				$.bootstrapGrowl('The following emails are invalid: '+emails,{type:'error',delay: 10000});
//			}
//			if(data.new_users.length != 0){
//				var emails = $.map(data.new_users,function(obj,ind){return obj.user.username;}).join(', ');
//				$.bootstrapGrowl('Accounts will automatically be made for the following new users: '+emails,{type:'info',delay: 10000});
//			}
//			
//		}
//		show_hide_permissions();
//	});
//}
//function add_group(query){
//	$.get(get_group_url,{query:query},function(data){
//		if(data.errors)
//			BC.handle_ajax_errors(data,'#messages');
//		else if(data.group){
//			data.permissions=[];
//			add_group_row(data);
////			BC.add_message(data.group.name);
//		}
//		show_hide_permissions();
//		console.log(data);
//	});
//}
//
//function add_user_row(obj){
//	var classes = obj.new_user ? 'new-user ' : '';
//	var warning = obj.new_user ? '<i class="fam-error-add" data-toggle="tooltip" title="An account will automatically be made for this email address"></i>' : '';
//	var row = $('<tr data-username="'+obj.user.username+'" class="'+classes+'"><td>'+warning+obj.user.username+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
//	$.each(obj.permissions,function(i,perm){
//		$('input[data-perm="'+perm+'"]',row).attr('checked',true);
//	});
//	$('#user_permissions tbody').append(row);
//}

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
//function add_group_row(obj){
//	var row = $('<tr data-group="'+obj.group.name+'"><td>'+obj.group.name+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
//	$.each(obj.permissions,function(i,perm){
//		$('input[data-perm="'+perm+'"]',row).attr('checked',true);
//	});
//	$('#group_permissions tbody').append(row);
//}
//function update_group_permissions(data){
//	console.log(data);
//	$('#group_permissions tbody').html('');
//	//view_share_files, download_share_files, write_to_share, delete_share_files
//	$.each(data.group_perms,function(index,obj){
//		add_group_row(obj);
//	});
//	show_hide_permissions();
//}

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
	
	//console.log($(this).attr('data-perm'));
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
//	if($('#group_permissions tbody tr').length == 0)
//		$('#group-permission-section').hide();
//	else
//		$('#group-permission-section').show();
}
$(function () {
	//console.log('Permissions');
	get_permissions();
	$(document.body).on('change','input[data-perm]',check_permissions_modified);
	$('#updateUserPermissions').click(function(){
		set_permissions({'users':get_user_permissions(),'groups':get_group_permissions(),'email':$('#email_users').prop('checked')});
	});
//	$('#updateGroupPermissions').click(function(){
//		set_permissions('groups',{'groups':get_group_permissions()});
//	});
	$('#addUserButton').click(function(){
		//add_user($('#addUser').val());
		share_with($('#addUser').val());
	});
//	$('#addGroupButton').click(function(){
//		add_group($('#addGroup').val());
//	});
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
	
});

function add_permission_row(obj){
	if (obj.user){
		if ($('.permissions tr[data-username="'+obj.user.username+'"]').length == 0){
			var classes = obj.new_user ? 'new-user ' : '';
			var warning = obj.new_user ? '<i class="fam-error-add" data-toggle="tooltip" title="An account will automatically be made for this email address"></i>' : '';
			var row = $('<tr data-username="'+obj.user.username+'" class="'+classes+'"><td>'+warning+'<i class="fam-user"></i>'+obj.user.username+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
		}
	}else if(obj.group){
		if ($('.permissions tr[data-group-id="'+obj.group.id+'"]').length == 0)
			var row = $('<tr data-group-id="'+obj.group.id+'" class="'+classes+'"><td><i class="fam-group"></i>'+obj.group.name+'</td><td><input data-perm="view_share_files" type="checkbox"></td><td><input data-perm="download_share_files" type="checkbox"></td><td><input data-perm="write_to_share" type="checkbox"></td><td><input data-perm="delete_share_files" type="checkbox"></td><td><input data-perm="admin" type="checkbox"></td></tr>').data('permissions',obj.permissions);
	}
	
	$.each(obj.permissions,function(i,perm){
		$('input[data-perm="'+perm+'"]',row).attr('checked',true);
	});
	$('#user_permissions tbody').append(row);
}

function share_with(query){
	$.get(share_with_url,{query:query},function(data){
		if(data.errors)
			BC.handle_ajax_errors(data,'#messages');
		else{
			$.each(data.exists,function(index,obj){
				obj.permissions=[];
				add_permission_row(obj,'user');
			});
			$.each(data.groups,function(index,obj){
				obj.permissions=[];
				add_permission_row(obj,'group');
			});
			$.each(data.new_users,function(index,obj){
				obj.permissions=[];
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
			
		}
		show_hide_permissions();
	});
}