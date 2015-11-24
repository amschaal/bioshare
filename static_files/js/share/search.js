

$(function () {
	$('#search_users').textcomplete([
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
	
	$('#search_tags').textcomplete([
	 	                            { // mention strategy
//	 	                              match:  /@(\w{2,})$/,
	 	                              search: function (term, callback) {
	 	                            	  var searchTerm = term;
//	 	                            	  console.log('term',term);
	 	                                //callback(cache[term], true);
	 	                                $.getJSON('/bioshare/api/get_tags/', { tag: term })
	 	                                  .done(function (resp) {
//	 	                                	  console.log('term',searchTerm);
	 	                                	  callback($.map(resp.tags, function (tag) {
	 	                                		  					console.log(tag);
	 		  	                              		                return tag.toLowerCase().indexOf(term.toLowerCase()) === 0 ? tag: null;
	 		  	                            		            	}));
//	 	                                	  callback(resp.emails);   
	 	                                  })
	 	                                  .fail(function ()     { callback([]);   });
	 	                              },
//	 	                              replace: function (word) {
//	 	                                  return word + ', ';
//	 	                              },
	 	                              cache: true,
	 	                              template: function (value) {
	 	                            	  return value;
//	 	                            	  if (value.toLowerCase().indexOf('group:') === 0)
//	 	                            		  return '<i class="fam-group"></i>' + value;
//	 	                            	  else 
//	 	                            		  return '<i class="fam-user"></i>' + value;
	 	                              },
	 	                              match: /(^|\s)(\w*)$/,
	 	                            	  replace: function (value) { return '$1' + value + ', '; }
	 	                            }
	     ]);
	search_tags
});

