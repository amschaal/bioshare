var BC = {}; //Bioinformatics Core namespace
BC.handle_ajax_errors = function(data,message_target){
	var errors = data.errors ? data.errors : [];
	if(data.error)
		errors.push(data.error);
	if(errors.length!=0){
//		if(message_target){
			$.bootstrapGrowl(errors.join(', '),{type:'error',delay: 10000});
//			BC.add_message(errors.join(', '),{'target':message_target,'classes':['alert-error']});
//		}else
//			alert(errors);
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
		});
}

BC.ajax=function(options){
	var callback = options.success ? options.success : false;
	options.success = function(data){
		BC.handle_ajax_errors(data);
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
BC.add_message = function(content, options){
	var classes = options.classes ? options.classes : ['alert-success'];
	var target = options.target ? options.target : '#messages';
	var alertbox = $('\
			<div class="alert '+classes.join(' ')+'">\
		    <button type="button" class="close" data-dismiss="alert">×</button>\
		    '+content+'\
		  </div>\
	').prependTo(target);
	if(options.timeout)
		window.setTimeout(function(){alertbox.alert('close')},options.timeout)
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