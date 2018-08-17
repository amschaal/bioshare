angular.module("bioshare").requires.push('BioshareResources');
angular.module("bioshare")
.controller("GroupController", ['$scope','$rootScope','Group','$uibModal', function($scope,$rootScope,Group,$uibModal) {
	$scope.init = function(params){
		console.log('params',params);
		$scope.group = Group.get({id:params.group_id});
	}
	$scope.manageGroup = function () {

	    var modalInstance = $uibModal.open({
	      animation: $scope.animationsEnabled,
	      templateUrl: 'manageGroup.html',
	      controller: 'GroupModalInstanceCtrl',
	      size: 'lg',
	      resolve: {
	        group_id: function () {
	          return $scope.group.id;
	        }
	      }
	    });
	    
	    modalInstance.result.then(function (data) {
	    	$scope.group = Group.get({id:$scope.group.id});
//	      $scope.selected = selectedItem;
	      
	    }, function () {
//	      $log.info('Modal dismissed at: ' + new Date());
	    });
	  };
	$scope.groupSharesURL = function (group){
		return '/bioshare/groups/'+group.id+'/shares/';
	}
 }]);

angular.module('bioshare').controller('GroupModalInstanceCtrl', function ($scope, $http,NgTableParams, Group, $uibModalInstance, group_id) {
  $scope.group_id = group_id;
  $scope.disable_save=true;
  $scope.group = Group.get({id:group_id},function(group){
	  	$scope.users = new NgTableParams({}, { dataset: group.users});
	}
  )
  $scope.$watch('group.users', function(newUsers, oldUsers) {
	  	  if (!oldUsers) return;
	  	  console.log('foo',$scope.group.users);
	  	  $scope.disable_save=false;
	  	},true);
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
  $scope.removeUser = function(user){
	  $scope.group.users.splice($scope.group.users.indexOf(user),1);
	  $scope.users.reload();
//	  $scope.group.$remove_user({user:user.id},function(data){console.log(data)});
  }
  $scope.save = function () {
	$scope.group.$update_users(function(data){$uibModalInstance.close($scope.group);})
  };
  $scope.cancel = function () {
    $uibModalInstance.dismiss('cancel');
  };
});