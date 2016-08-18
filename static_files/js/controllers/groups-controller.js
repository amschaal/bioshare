angular.module("bioshare").requires.push('BioshareResources');
angular.module("bioshare")
.controller("GroupsController", ['$scope','NgTableParams','$uibModal', function($scope,NgTableParams,$uibModal) {
	$scope.init = function(params){
		$scope.user = params.user;
		$scope.tableParams = new NgTableParams({}, { dataset: $scope.user.groups});
	}
	$scope.manageGroup = function (group) {

	    var modalInstance = $uibModal.open({
	      animation: $scope.animationsEnabled,
	      templateUrl: 'manageGroup.html',
	      controller: 'GroupModalInstanceCtrl',
	      size: 'lg',
	      resolve: {
	        group_id: function () {
	          return group.id;
	        }
	      }
	    });

	    modalInstance.result.then(function (selectedItem) {
	      $scope.selected = selectedItem;
	    }, function () {
	      $log.info('Modal dismissed at: ' + new Date());
	    });
	  };

 }]);

angular.module('bioshare').controller('GroupModalInstanceCtrl', function ($scope,NgTableParams, Group, $uibModalInstance, group_id) {

  $scope.group_id = group_id;
  $scope.group = Group.get({id:group_id},function(group){
	  	$scope.groupMembers = new NgTableParams({}, { dataset: group.users});
	  	$scope.groupAdmins = new NgTableParams({}, { dataset: group.permissions});
	}
  )
  
  
  $scope.ok = function () {
    $uibModalInstance.close("Stuff");
  };

  $scope.cancel = function () {
    $uibModalInstance.dismiss('cancel');
  };
});