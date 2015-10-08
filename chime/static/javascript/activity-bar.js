$(document).ready(function() {
	$('.button--open-review-modal').click(function(e) {
		e.preventDefault();
		$('.review-modal').parent().addClass('is-open');
	})

	$('.button--close-review-modal').click(function(e) {
		e.preventDefault();
		$('.review-modal').parent().removeClass('is-open');
	})
});