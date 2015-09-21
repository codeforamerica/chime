$(document).ready(function() {
	$('.button--new-activity').click(function(e) {
		e.preventDefault();
		$('.new-activity').parent().addClass('is-open');
		$('.new-activity textarea').focus();
	})
	$('.button--close-modal').click(function(e) {
		e.preventDefault();
		$('.new-activity').parent().removeClass('is-open');
	})
})