angular.module("bioshare")
.controller("SharesController", ['$scope', 'DRFNgTableParams',function($scope, DRFNgTableParams) {
	$scope.init = function(){
		$scope.tableParams = DRFNgTableParams('/bioshare/api/shares/',{sorting: { updated: "desc" },filter:{}});
	}
 }]);