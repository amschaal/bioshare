var transformDjangoRestResponse = function(data, headers){
	try {
        var jsonObject = angular.fromJson(data); // verify that json is valid
        return jsonObject.results;
    }
    catch (e) {
        console.log("did not receive valid Json: " + e)
    }
    return {};
}
var setErrors = function(data, headers){
	console.log(data);
	return data;
//	try {
//        var jsonObject = JSON.parse(data); // verify that json is valid
//        return jsonObject.results;
//    }
//    catch (e) {
//        console.log("did not receive a valid Json: " + e)
//    }
//    return {};
}
angular.module('BioshareResources', ['ngResource'])
.factory('Group', ['$resource', function ($resource) {
  return $resource('/bioshare/api/groups/:id/', {id:'@id'}, {
    query: { method: 'GET', isArray:true, transformResponse:transformDjangoRestResponse }, //, transformResponse:transformDjangoRestResponse
    save : { method : 'PUT'},
    create : { method : 'POST'},
    remove : { method : 'DELETE' },
    update_users: {method : 'POST', url: '/bioshare/api/groups/:id/update_users/' },
    remove_user: {method : 'POST', url: '/bioshare/api/groups/:id/remove_user/' }
  });
}])
.factory('Message', ['$resource', function ($resource) {
  return $resource('/bioshare/api/messages/:id/', {id:'@id'}, {
    query: { method: 'GET', isArray:true, transformResponse:transformDjangoRestResponse }, //, transformResponse:transformDjangoRestResponse
    dismiss: {method : 'POST', url: '/bioshare/api/messages/:id/dismiss/' }
  });
}]);
