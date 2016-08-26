angular.module("bioshare").requires.push('BioshareResources');
angular.module("bioshare")
.controller("GroupsController", ['$scope','Group','NgTableParams','$uibModal', function($scope,Group,NgTableParams,$uibModal) {
	$scope.init = function(params){
		$scope.user = params.user;
		$scope.tableParams = new NgTableParams({}, { dataset: $scope.user.groups});
	}
	$scope.createGroup = function(name){
		var group = new Group({name:name});
		group.$create(function(group){
				$scope.user.groups.push(group);
				$scope.tableParams.reload();
				$scope.manageGroup(group);
			},function(response){
				console.log('error',response);
				$.bootstrapGrowl('Error creating group',{type:'error',delay: 3000});
			}
		);
	}
	$scope.deleteGroup = function(group){
		if (!confirm('Are you sure you want to delete the group "'+group.name+'"?'))
			return;
		group = new Group(group);
		group.$delete(function(){
				$scope.user.groups.splice($scope.user.groups.indexOf(group),1);
				$scope.tableParams.reload();
				$.bootstrapGrowl('Group "'+group.name+'" deleted',{type:'success',delay: 3000});
			},function(){
				$.bootstrapGrowl('Error deleting group "'+group.name+'"',{type:'error',delay: 3000});
			});
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
//	      $log.info('Modal dismissed at: ' + new Date());
	    });
	  };

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
	$scope.group.$update_users(function(data){$uibModalInstance.close(data);})
  };
  $scope.cancel = function () {
    $uibModalInstance.dismiss('cancel');
  };
});