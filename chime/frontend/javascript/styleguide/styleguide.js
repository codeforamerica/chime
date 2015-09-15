$(function() {
	var content = $('.style-guide-content');
	var styleguide = new Styleguide(content);
})

function Styleguide(content) {
	this.content = content;

	this.generateTOC();
	this.generateCodeSnippets();
}


Styleguide.prototype.generateTOC = function() {
	var self = this;

	// Create TOC hierarchy as a json object
	this.buildTOC = function() {
		var toc = [];
		var currH1 = null;
		var currH1Hash = null;
		$(self.content).find('> h1, > h2').each(function(index, header) {
			if($(header).is('h1')) {
				var h1 = {
					title: $(header).text(),
					hash: $(header).attr('id'),
					contents: []
				}
				toc.push(h1);
				currH1 = h1;				
			}
			else if($(header).is('h2')) {
				var h2 = {
					title: $(header).text(),
					hash: $(header).attr('id')
				}
				currH1.contents.push(h2);
			}
		});
		
		return toc;
	}

	// Render the TOC
	this.render = function() {
		var tocView = $('<ul>');
		$(toc).each(function(index, h1) {
			var currH1El = $('<li>');
			currH1El.append('<a class="link-h1" href="#' + h1.hash + '">' + h1.title + '</a>');
			
			if(h1.contents) {
				var h1Contents = $("<ul>");
				$(h1.contents).each(function(index, h2) {
					var currH2El = $('<li>');
					$(currH2El).append('<a class="link-h2" href="#' + h2.hash + '">' + h2.title + '</a>');
					$(h1Contents).append(currH2El);
				});
				$(currH1El).append(h1Contents);
			}
			$(tocView).append(currH1El);
		})

		$('.nav-sidebar').append(tocView);

		$('.nav-sidebar a').click(function(e) {
			e.preventDefault();
			var hashLocation = $(this).attr('href');
			$('.main-content').animate({
				scrollTop: $(hashLocation).position().top
			}, 200);
			window.location.hash = hashLocation;
		})
	}	

	var toc = this.buildTOC();
	this.render();
}

Styleguide.prototype.generateCodeSnippets = function() {

	var self = this;

	this.parseCode = function(preview) {
		var sampleCode = $('<div>');
		$(sampleCode).html($(preview).html())
		$(sampleCode).find('.is-peripheral').remove();
		return sampleCode;
	}

	this.render = function(preview, sampleCode) {

		var sampleCodeBox = $('<div class="code-sample"><a class="button-toggle"></a><pre><code class="language-markup"></code></pre></div>');
		$(sampleCodeBox).find('code').text($(sampleCode).html());
		$(preview).after(sampleCodeBox);
	}

	$(this.content).find('.preview').each(function(index, preview) {

		var sampleCode = self.parseCode(preview);
		self.render(preview, sampleCode);

	});

	$('.button-toggle').click(function(e) {
		e.preventDefault();
		$(this).parent().toggleClass('is-open');
	})
}