$(function() {

	$('.markdown-previewer').load(function() {
		// Preview Content in Editor
		var markdownEditor = new Editor($(".markdown-textarea"), $(".markdown-previewer"));
		$(".markdown-textarea").bind('change keyup', function(e) {
			markdownEditor.update();
		});

		// Preview Title
		$('.edit-article__title').bind('keyup change', function(e) {
			$('.markdown-previewer').contents().find('header h1').html($(this).val());
		})
		$('.edit-article__title').trigger('change');
	})
	
});

function Editor(input, preview) {
  this.update = function () {
  	var htmlContent = markdown.toHTML($(input).val())
    $(preview).contents().find('article').html(htmlContent);
  };

  $(input).get()[0].editor = this;
  this.update();
}