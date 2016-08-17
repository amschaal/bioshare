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
	        group: function () {
	          return group;
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

angular.module('bioshare').controller('GroupModalInstanceCtrl', function ($scope, $uibModalInstance, group) {

  $scope.group = group;

  $scope.ok = function () {
    $uibModalInstance.close("Stuff");
  };

  $scope.cancel = function () {
    $uibModalInstance.dismiss('cancel');
  };
});