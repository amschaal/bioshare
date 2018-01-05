angular.module("bioshare").requires.push('BioshareResources');
angular.module("bioshare")
.controller("GroupsController", ['$scope','$rootScope','Group','DRFNgTableParams','$uibModal', function($scope,$rootScope,Group,DRFNgTableParams,$uibModal) {
	$scope.init = function(params){
		console.log('params',params);
		$scope.user = params.user;
		$scope.tableSettings = {sorting: { name: "asc" },filter:{}};
		$scope.tableParams = DRFNgTableParams('/bioshare/api/groups/',$scope.tableSettings);
//		$scope.tableParams = new NgTableParams({}, { dataset: $scope.user.groups});
	}
	$scope.createGroup = function(name){
		var group = new Group({name:name});
		group.$create(function(group){
				window.location = $rootScope.getURL('group',{'group_id':group.id})
//				$scope.user.groups.push(group);
//				$scope.tableParams.reload();
//				$scope.manageGroup(group);
			},function(response){
				console.log('error',response);
				$.bootstrapGrowl('Error creating group',{type:'error',delay: 3000});
			}
		);
	}
	
 }]);

