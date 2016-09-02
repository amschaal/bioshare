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
			if (data.unauthenticated)
				BC.login();
			
		}).error(function(data){
			if (options.error)
				options.error(data);
			if (data.responseJSON)
				BC.handle_ajax_errors(data.responseJSON);
			if (data.unauthenticated)
				BC.login();
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
$( document ).ajaxError(function(event, xhr, settings) {
	console.log('error',xhr.responseJSON,event,xhr,settings);
//	if(xhr.responseJSON.unauthenticated || xhr.status == 403 || xhr.status == 401)
//		BC.login();
});

angular.module("bioshare", ["ngTable","ngResource","ui.bootstrap","checklist-model"])
.run(function($rootScope) {
    $rootScope.getURL = django_js_utils.urls.resolve;
})
.config(function($resourceProvider) {
  $resourceProvider.defaults.stripTrailingSlashes = false;
})
.config(['$httpProvider', function($httpProvider) {
    $httpProvider.defaults.xsrfCookieName = 'csrftoken';
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
    $httpProvider.interceptors.push(function($q) {
    	  return {
    	   'response': function(response) {
    	      // do something on success
    	      return response || $q.when(response);
    	    },

    	   'responseError': function(rejection) {
    		   console.log('rejection',rejection);
//    		  if (rejection.status == 403 || rejection.status == 401)
//    			  BC.login();
    	      return $q.reject(rejection);
    	    }
    	  };
    	});
}])
.filter('bytes', function() {
	return function(bytes, precision) {
		if (bytes==0 ||isNaN(parseFloat(bytes)) || !isFinite(bytes)) return '-';
		if (typeof precision === 'undefined') precision = 1;
		var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
			number = Math.floor(Math.log(bytes) / Math.log(1024));
		return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
	}
});