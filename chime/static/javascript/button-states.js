$(document).ready(function() {
	// Prevent duplicate form submits by ignoring subsequent clicks and providing click feedback to users.
	$('body').find('*[type="submit"]').click(function(e) {
		if($(this).hasClass('is-loading')) {
			e.preventDefault();
		}
		else {
			$(this).addClass('is-loading');
		}
	});
})