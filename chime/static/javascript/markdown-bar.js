function MarkdownBar(bar, textarea) {

	var markdownBar = $(bar);
	var markdownTextarea = $(textarea);

	//Define Markdown Patterns
	var PATTERNS = [
		{
			'name': 'h1',
			'syntax': '# ${content}',
			'icon': 'h1',
			'filler': 'This is a level 1 heading'
		},
		{
			'name': 'h2',
			'syntax': '## ${content}',
			'icon': 'h2',
			'filler': 'This is a level 2 heading'
		}
	];

	// String interpolation function
	var interpolate = function(formatString, data) {
	    var i, len,
	        formatChar,
	        prevFormatChar,
	        prevPrevFormatChar;
	    var prop, startIndex = -1, endIndex = -1,
	        finalString = '';
	    for (i = 0, len = formatString.length; i<len; ++i) {
	        formatChar = formatString[i];
	        prevFormatChar = i===0 ? '\0' : formatString[i-1],
	        prevPrevFormatChar =  i<2 ? '\0' : formatString[i-2];

	        if (formatChar === '{' && prevFormatChar === '$' && prevPrevFormatChar !== '\\' ) {
	            startIndex = i;
	        } else if (formatChar === '}' && prevFormatChar !== '\\' && startIndex !== -1) {
	            endIndex = i;
	            finalString += data[formatString.substring(startIndex+1, endIndex)];
	            startIndex = -1;
	            endIndex = -1;
	        } else if (startIndex === -1 && startIndex === -1){
	            if ( (formatChar !== '\\' && formatChar !== '$') || ( (formatChar === '\\' || formatChar === '$') && prevFormatChar === '\\') ) {
	                finalString += formatChar;
	            }
	        }
	    }
	    return finalString;
	};


	var markdownify = function(event, syntax, filler) {
		event.preventDefault();

		// Figure out whether function should:
		//	a. add markdown pattern to current cursor position
		//  b. append text to top of page
		//	c. replace selection with markdowned version of text

		var selectionStart = markdownTextarea.get(0).selectionStart;
		var selectionEnd =  markdownTextarea.get(0).selectionEnd;

		var textSelected = selectionStart == selectionEnd ? false : true;

		var content = textSelected ? markdownTextarea.val().slice(selectionStart, selectionEnd) : filler;
		var newContent = interpolate(syntax, {content: content});

		markdownTextarea.val(markdownTextarea.val().slice(0, selectionStart) + newContent + markdownTextarea.val().slice(selectionEnd, markdownTextarea.val().length))

	}

	
	this.init = function() {
		// Add buttons to markdown bar and bind events
		$(PATTERNS).each(function(index, pattern) {
			var patternButton = $('<div class="button button--outline toolbar__item">' + pattern['icon'] +'</div>');
			patternButton.bind('click', function(event) {
				markdownify(event, pattern['syntax'], pattern['filler']);
			});
			markdownBar.append(patternButton);
		});
	}

	this.init();
}



$(document).ready(function() {
	var markdownBar = new MarkdownBar('.markdown-bar', '.markdown-textarea');
})