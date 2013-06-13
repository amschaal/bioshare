function get_selected_names(){
	var selection = [];
	$('.action-check:checked').each(function(){
		selection.push($(this).closest('tr').attr('data-id'));
	});
	return selection;
}
$(function () {
    $('#fileupload').fileupload({
        url: upload_file_url,
        dataType: 'json',
        done: function (e, data) {
        	console.log('done',data);
            $.each(data.result.files, function (index, file) {
            	var row = '<tr class="file success" data-id="'+file.name+'"><td><input class="action-check" type="checkbox"/></td><td><i class="fam-page-white"></i>'+file.name+'</td><td>'+file.size+'</td></tr>';
                $(row).insertAfter('#file-table .directory:last');
            });
        },
        progressall: function (e, data) {
            var progress = parseInt(data.loaded / data.total * 100, 10);
            $('#progress .bar').css(
                'width',
                progress + '%'
            );
        }
    });
    $('#create-folder').click(function(){
    		ajax_form_submit('#new-folder-form',{
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
    			alert('download '+get_selected_names());
    			break;
    		case 'delete':
    			alert('delete '+get_selected_names());
    			break;
    	}
    })
    
});