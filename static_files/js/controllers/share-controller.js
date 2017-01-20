angular.module("bioshare")
.controller("LogController", ['$scope', 'NgTableParams', 'DRFNgTableParams',function($scope,NgTableParams, DRFNgTableParams) {
	$scope.init = function(share){
		$scope.tableParams = DRFNgTableParams('/bioshare/api/logs/',{sorting: { timestamp: "desc" },filter:{share:share}});
	}
 }]);
angular.module("bioshare")
.controller("SizeController", ['$scope', 'Share',function($scope,Share) {
	$scope.size = null;
	$scope.calculate = function(share,subdir){
		$scope.size = 'Loading...';
		Share.directory_size({id:share,subdir:subdir},function(data){
			$scope.size = data.size;
		});
	}
 }]);