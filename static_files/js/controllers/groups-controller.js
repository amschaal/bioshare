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

angular.module('bioshare').controller('GroupModalInstanceCtrl', function ($scope, $http,NgTableParams, Group, $uibModalInstance, group_id) {

  $scope.group_id = group_id;
  $scope.group = Group.get({id:group_id},function(group){
	  	$scope.users = new NgTableParams({}, { dataset: group.users});
	}
  )
  $scope.checkUsername = function (username){
	  console.log('username',username);
	  $http.get('/bioshare/api/get_user',{params:{query:username}}).then(function(response){
		  $scope.new_user = response.data.user;
		  $scope.new_user.permissions = [];
	  },function(response){
		  $scope.new_user = null;
		  console.log('invalid',response.data);
	  });
  }
  $scope.addUser = function(){
	  $scope.group.users.push($scope.new_user);
	  $scope.users.reload();
  }
  $scope.removeUser = function(index){
	  $scope.group.users.splice(index,1);
	  $scope.users.reload();
//	  $scope.group.$remove_user({user:user.id},function(data){console.log(data)});
  }
  $scope.ok = function () {
	$scope.group.$update_users(function(data){$uibModalInstance.close(data);})
  };

  $scope.cancel = function () {
    $uibModalInstance.dismiss('cancel');
  };
});