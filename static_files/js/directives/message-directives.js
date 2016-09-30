angular.module("messages", ["messages.tpls","messages.directives"]);
angular.module("messages.tpls", ["template/messages/messages.html","template/messages/message.html"]);

angular.module('messages.directives', ['BioshareResources'])
.directive('messageList', function(Message,$uibModal) {//Subscription,Notification
	  return {
	    restrict: 'AE',
	    templateUrl: 'template/messages/messages.html',
	    scope: {
	    },
	    controller: function($scope, $http, $element){
	    	this.$scope = $scope;
	    	$scope.messages = Message.query();
	    	$scope.open = function (message,index) {

	    	    var modalInstance = $uibModal.open({
	    	      animation: $scope.animationsEnabled,
	    	      templateUrl: 'template/messages/message.html',
	    	      controller: 'MessageCtrl',
	    	      size: 'lg',
	    	      resolve: {
	    	        message: function () {
	    	          return message;
	    	        }
	    	      }
	    	    });

	    	    modalInstance.result.then(function (selectedItem) {
	    	      $scope.messages.splice(index,1);
	    	    }, function () {
	    	      
	    	    });
	    	  };
	    	  
	    	$scope.dismiss = function(message){
	    		message.$dismiss();
	    	}
	    }
	  }
	}).controller('MessageCtrl', function ($scope, $uibModalInstance, message) {
		  $scope.message = message;
		  $scope.dismiss = function () {
		    $scope.message.$dismiss(function(){$uibModalInstance.close($scope.message);});
		  };
		
		  $scope.close = function () {
		    $uibModalInstance.dismiss('cancel');
		  };
});

angular.module('template/messages/messages.html', []).run(['$templateCache', function($templateCache) {
	  $templateCache.put('template/messages/messages.html',
	'<div ng-repeat="message in messages">\
			  <div class="alert alert-danger" role="alert"> <i class="icon-warning-sign"></i> <b>{{message.created | date : "short"}}</b>: <a ng-click="open(message,$index)" href="#">"{{message.title}}"</a></div>\
	</div>'
	  );
	}]);
angular.module('template/messages/message.html', []).run(['$templateCache', function($templateCache) {
	  $templateCache.put('template/messages/message.html',
			  '<div class="modal-header">\
				  <h3 class="modal-title" id="modal-title">{{message.title}}</h3>\
				  </div>\
				  <div class="modal-body" id="modal-body">{{message.description}}</div>\
				  <div class="modal-footer">\
				  <button class="btn btn-primary" type="button" ng-click="dismiss()">Dismiss</button><button class="btn btn-warning" type="button" ng-click="close()">Close</button>\
			  </div>'
	  );
	}]);

