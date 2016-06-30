angular.module("bioshare")
.controller("LogController", ['$scope', 'NgTableParams', 'DRFNgTableParams',function($scope,NgTableParams, DRFNgTableParams) {
	$scope.init = function(share){
		$scope.tableParams = DRFNgTableParams('/bioshare/api/logs/',{sorting: { timestamp: "desc" },filter:{share:share}});
	}
 }]);