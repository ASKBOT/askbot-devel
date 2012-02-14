(function (w) {
	w.ajaxChart = function (id, path, options) {
		var jq = $;
		var el = jq('#' + id);
		var contents = el.html();
		jq.ajax(path,
			{
				success: function (data) {
					jq.jqplot(id, data, options);
				},
				dataType: 'json',
				error: function () {
					ajaxChartError(id, path, options, contents);
				}});
	}
})(window)
