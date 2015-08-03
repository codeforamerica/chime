function Editor(title, content, preview) {

	var self = this;

	this.updatePreviewHeight = function() {
		$(preview).height($(preview).contents().height());
	}

  this.updateContent = function() {
    $(preview).contents().find('article').html(marked($(content).val()));
    // Give page a little bit of time to finish rendering
    setTimeout(function() {
      self.updatePreviewHeight();
    }, 100);
   
  };

  this.updateTitle = function() {
  	$(preview).contents().find('header h1').html($(title).val());
  	self.updatePreviewHeight();
  }

  this.init = function() {
  	$('.markdown-previewer').load(function() {
	  	$(content).bind('keyup change', function(e) {
	  		self.updateContent();
	  	});

	  	$(title).bind('keyup change', function(e) {
	  		self.updateTitle();
	  	})

	  	$(title).trigger('change');
	  	$(content).trigger('change');
  	});
  }

  this.init()

  return false;
}

$(function() {
		var markdownEditor = new Editor($('.edit-article__title'), $(".markdown-textarea"), $(".markdown-previewer"));

    // If markdown previewer is loaded, hide hints by default.
    $('.previewer__hints').addClass('is-hidden');
    $('#toggle-hints').removeClass('is-selected');
});