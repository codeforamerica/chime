$(document).ready(function() {
	$('body').find('*[type="submit"]').click(function(e) {
		if($(this).hasClass('is-loading')) {
			e.preventDefault();
		}
		else {
			$(this).addClass('is-loading');
		}
	});
})