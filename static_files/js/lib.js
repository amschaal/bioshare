function ajax_form_submit(form,options){
	var defaults={
			'ajax':
			{
				'type':'POST',
				'url':$(form).attr('action')
			}
	}
	var options = $.extend({},defaults,options);
	$.ajax(options.ajax).success(function ( data ) {
			if(data.html)
				$(form).html(data.html);
			if(options.success)
				options.success(data);
		});
}