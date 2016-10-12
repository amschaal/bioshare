angular.module("bioshare")
.controller("SharesController", ['$scope', 'DRFNgTableParams',function($scope, DRFNgTableParams) {
//	$scope.toggleFilters = function(){
//		$scope.show_filters = !$scope.show_filters;
//	};
	$scope.cols = {'Share':true,'Description':true,'Tags':true,'Owner':true,'Users':false,'Groups':false,'Created':false,'Modified':true,'Files':false,'Size':true}
	$scope.init = function(){
		$scope.tableParams = DRFNgTableParams('/bioshare/api/shares/',{sorting: { updated: "desc" },filter:{}});
	}
	$scope.setFilter = function (field,value){
		$scope.tableParams.filter()[field] = value;
	}
 }]);