angular.module("bioshare").requires.push('BioshareResources');
angular.module("bioshare")
.controller("GroupsController", ['$scope','$rootScope','Group','DRFNgTableParams','$uibModal', function($scope,$rootScope,Group,DRFNgTableParams,$uibModal) {
	$scope.init = function(params){
		console.log('params',params);
		$scope.user = params.user;
		$scope.tableSettings = {sorting: { name: "asc" },filter:{}};
		$scope.tableParams = DRFNgTableParams('/bioshare/api/groups/',$scope.tableSettings);
	}
 }]);

