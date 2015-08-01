$(document).ready(function() {
	$(".previewer__hints").addClass('is-hidden');

	$('#toggle-hints').click(function() {
		$('.previewer__hints, .previewer__content').toggleClass('is-hidden');
		$('#toggle-hints').toggleClass('is-selected');
	})
})