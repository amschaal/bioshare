angular.module("bioshare")
.controller("GroupsController", ['$scope', function($scope) {
	$scope.init = function(params){
		$scope.user = params.user;
	}
 }]);