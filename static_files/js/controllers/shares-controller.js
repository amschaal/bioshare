angular.module("bioshare")
.controller("SharesController", ['$scope', 'DRFNgTableParams','LocationSearchState',function($scope, DRFNgTableParams,LocationSearchState) {
//	$scope.toggleFilters = function(){
//		$scope.show_filters = !$scope.show_filters;
//	};
	$scope.cols = {'Share':true,'Description':true,'Tags':true,'Owner':true,'Users':false,'Groups':false,'Created':false,'Modified':true,'Files':false,'Size':true}
	$scope.init = function(filters){
		$scope.tableSettings = {sorting: { updated: "desc" },filter:filters};
		$scope.loadState();
		$scope.tableParams = DRFNgTableParams('/bioshare/api/shares/',$scope.tableSettings);
	}
	$scope.setFilter = function (field,value){
		$scope.tableParams.filter()[field] = value;
	}
	$scope.loadState = function(){
		var state = LocationSearchState.get();
		if (state.cols)
			for (var key in state.cols){
				$scope.cols[key] = typeof(state.cols[key]) === "boolean" ? state.cols[key] : (state.cols[key].toLowerCase() === "true");
			}
		if (state.tableSettings)
			$scope.tableSettings = state.tableSettings; 
	};
	$scope.saveState = function(){
		var url_params = $scope.tableParams.url();
		var state = {tableSettings:{page:url_params.page,count:url_params.count,sorting:$scope.tableParams.sorting(),filter:$scope.tableParams.filter()},cols:$scope.cols};
		LocationSearchState.set(state);
	};
 }]);