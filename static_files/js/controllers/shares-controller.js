angular.module("bioshare")
.controller("SharesController", ['$scope', 'DRFNgTableParams','LocationSearchState',function($scope, DRFNgTableParams,LocationSearchState) {
//	$scope.toggleFilters = function(){
//		$scope.show_filters = !$scope.show_filters;
//	};
	$scope.cols = {'Share':true,'Description':true,'Tags':true,'Owner':true,'Users':false,'Groups':false,'Created':false,'Modified':true,'Files':false,'Size':true}
	$scope.filters = {'locked': false, 'contains_symlinks': false, 'has_symlink_warning': false, 'symlink_target': ''};
	$scope.filter_labels = {'locked': 'Locked', 'contains_symlinks': 'Contains Symlink', 'has_symlink_warning': 'Contains bad symlink'};
	$scope.show_filters = false;
	$scope.init = function(filters){
		Object.assign($scope.filters, filters);	
		// console.log(filters, $scope.filters)
		$scope.tableSettings = {sorting: { updated: "desc" },filter:$scope.filters};
		$scope.loadState();
		$scope.tableParams = DRFNgTableParams('/bioshare/api/shares/',$scope.tableSettings);
	}
	$scope.setFilter = function (field,value){
		// $scope.tableParams.filter()[field] = value;
	}
	$scope.setAllFilters = function (){
		for (var filter in $scope.filters) {
			console.log(filter, $scope.filters[filter])
			$scope.tableParams.filter()[filter] = $scope.filters[filter];
		}
		$scope.saveState();
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
	$scope.toggleFilters = function(){
		$scope.show_filters = !$scope.show_filters;
		console.log('show filters', $scope.show_filters);
	};
 }]);