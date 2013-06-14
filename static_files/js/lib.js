var BC = {}; //Bioinformatics Core namespace
BC.ajax_form_submit=function(form,options){
	var defaults={
			'ajax':
			{
				'type':'POST',
				'url':$(form).attr('action'),
				'data':$(form).serialize()
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
BC.ajax=function(options){
	var callback = options.success ? options.success : false;
	options.success = function(data){
		var errors = data.errors ? data.errors : [];
		if(data.error)
			errors.push(data.error);
		if(errors.length!=0)
			alert(errors);
		if(callback)
			callback(data);
	}
	var defaults={
			type:"POST"
	}
	var options = $.extend({},defaults,options);
	$.ajax(options);
}
BC.replace = function(str,dict){
	for(var key in dict){
		str = str.replace(key,dict[key]);
	}
	return str;
}