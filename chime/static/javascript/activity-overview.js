$(document).ready(function() {
	$('.button--open-rename-modal').click(function(e) {
		e.preventDefault();
		$('.rename-modal').parent().addClass('is-open');
	})
	$('.button--close-rename-modal').click(function(e) {
		e.preventDefault();
		$('.rename-modal').parent().removeClass('is-open');
	})
})