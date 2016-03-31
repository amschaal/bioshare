var BC = {}; //Bioinformatics Core namespace
BC.handle_ajax_errors = function(data,message_target){
	console.log(data);
	var errors = data.errors ? data.errors : [];
	if(data.error)
		errors.push(data.error);
	if(errors.length!=0){
//		if(message_target){
			$.bootstrapGrowl(errors.join(', '),{type:'error',delay: 10000});
//		}else
//			alert(errors);
	}
	if(data.messages){
		for(var i in data.messages)
			$.bootstrapGrowl(data.messages[i].content,{type:data.messages[i].type,delay: 10000});//type:(null, 'info', 'error', 'success')
	}
		
}
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
//			BC.handle_ajax_errors(data,options.message_target);
			if(data.html)
				$(form).html(data.html);
			if(options.success)
				options.success(data);
			
		}).error(function(data){
			if (options.error)
				options.error(data);
			if (data.responseJSON)
				BC.handle_ajax_errors(data.responseJSON);
		});
}
BC.login=function(){
	console.log('login')
	window.location = '/accounts/login';
}
BC.ajax=function(options){
	var callback = options.success ? options.success : false;
	options.success = function(data){
		BC.handle_ajax_errors(data);
		if (data.unauthenticated)
			BC.login();
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

BC.templates = {};
BC.load_templates = function(){
	$('script[type="text/x-handlebars-template"]').each(function(index,template){
		BC.templates[$(template).prop('id')] = Handlebars.compile($(template).html());
	});
}
BC.run_template = function(id,context){
	if (!BC.templates[id])
		throw "Template id: '"+id+"' hasn't been compiled";
	else
		return BC.templates[id](context);
}