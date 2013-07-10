function delete_key(id){
	if(confirm('Are you sure you want to delete this SSH key?'))
		$.post(delete_key_url,{id:id},function(data){
			console.log(data);
			if(data.deleted){
				$('#ssh-key-table [data-id='+data.deleted+']').addClass('error').addClass('deleted');
				setTimeout(function(){
						$('#ssh-key-table tr.deleted').fadeOut({
							'duration':500,
							'complete':function(){$(this).remove();}
								});
						}
					,500);
			}
		});
}

$(function () {
	$('[data-action="delete-key"]').click(function(){
		delete_key($(this).closest('[data-id]').attr('data-id'));
	});
});