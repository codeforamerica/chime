$(document).ready(function() {
	$('#toggle-hints').addClass('is-selected');

	$('#toggle-hints').click(function() {
		$('.previewer__hints, .previewer__content').toggleClass('is-hidden');
		$('#toggle-hints').toggleClass('is-selected');
	})
})