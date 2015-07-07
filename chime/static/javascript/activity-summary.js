$(document).ready(function() {
	$('.activity-summary__table').addClass('is-hidden');

	$('.activity-summary__toggle').click(function(e) {
		e.preventDefault();
		$(this).toggleClass('is-open');
		$('.activity-summary__table').toggleClass('is-hidden');
	});
})