/* WCAG 7c — Label ng-table filter inputs and add aria-sort to sortable headers */
angular.module('ngTable')
.directive('ngTable', function() {
	return {
		restrict: 'A',
		priority: -1,
		link: function(scope, element) {
			function patchFilters() {
				element.find('.input-filter').each(function() {
					var input = $(this);
					if (input.attr('aria-label')) return;
					var th = input.closest('th');
					var title = th.attr('data-title-text') || th.find('[data-title-text]').attr('data-title-text') || th.text().trim();
					if (title) input.attr('aria-label', 'Filter by ' + title);
				});
				element.find('th[sortable]').each(function() {
					var th = $(this);
					var sortClass = th.attr('class') || '';
					if (sortClass.indexOf('sort-asc') >= 0) th.attr('aria-sort', 'ascending');
					else if (sortClass.indexOf('sort-desc') >= 0) th.attr('aria-sort', 'descending');
					else th.attr('aria-sort', 'none');
				});
			}
			scope.$watch(function() { return element.find('.input-filter').length; }, patchFilters);
			scope.$on('ngTableAfterReloadData', patchFilters);
		}
	};
})
.factory('DRFNgTableParams', ['NgTableParams','$http', function(NgTableParams,$http) {
	return function(url,ngparams,resource) {
		var params = {
//				page: 1, // show first page
//				filter:{foo:'bar'}, //filter stuff
				count: 10 // count per page
		}
		angular.merge(params,ngparams);
		return new NgTableParams(params, {
			filterOptions:{filterDelay: 1500},
			getData: function(params) {
				var url_params = params.url();
				console.log(params);
				console.log(url);
				var query_params = {page:url_params.page,page_size:url_params.count,ordering:params.orderBy().join(',').replace('+','')};
				angular.extend(query_params, params.filter());
				// ajax request to api
				return $http.get(url,{params:query_params}).then(function(response){
					console.log(response.data);
					params.total(response.data.count);
					if (resource)
						return response.data.results.map(function(obj){return new resource(obj);});
					else
						return response.data.results;
				});
			}
		});
	};
}]);