angular.module("bioshare")
.controller("SharesController", ['$scope', 'DRFNgTableParams','LocationSearchState',function($scope, DRFNgTableParams,LocationSearchState) {
//	$scope.toggleFilters = function(){
//		$scope.show_filters = !$scope.show_filters;
//	};
	$scope.cols = {'Share':true,'Description':true,'Tags':true,'Owner':true,'Users':false,'Groups':false,'Created':false,'Modified':true,'Files':false,'Size':true}
	$scope.filters = {'locked': false, 'contains_symlinks': false};
	$scope.filter_labels = {'locked': 'Locked', 'contains_symlinks': 'Contains Symlink'};
	$scope.init = function(filters){
		Object.assign($scope.filters, filters);	
		// console.log(filters, $scope.filters)
		$scope.tableSettings = {sorting: { updated: "desc" },filter:$scope.filters};
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
		console.log('url params', url_params);
		console.log('state', url_params);
		LocationSearchState.set(state);
	};
 }]);