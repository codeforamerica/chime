function MarkdownBar(bar, textarea) {

	var markdownBar = $(bar);
	var markdownTextarea = $(textarea);

	//Define Markdown Patterns
	var PATTERNS = [
		{
			'name': 'h1',
			'syntax': '# ${content}',
			'icon': 'h1',
			'filler': 'This is a level 1 heading',
			'type': 'block'
		},
		{
			'name': 'h2',
			'syntax': '## ${content}',
			'icon': 'h2',
			'filler': 'This is a level 2 heading',
			'type': 'block'
		},
		{
			'name': 'h3',
			'syntax': '### ${content}',
			'icon': 'h3',
			'filler': 'This is a level 3 heading',
			'type': 'block'
		},
		{
			'name': 'italics',
			'syntax': '_${content}_',
			'icon': '<i>i</i>',
			'filler': 'This is italicized text',
			'type': 'inline'
		},
		{
			'name': 'bold',
			'syntax': '**${content}**',
			'icon': '<b>b</b>',
			'filler': "This is bold text",
			'type': 'inline'
		},
		{
			'name': 'link',
			'syntax': '[${content}](http://www.example.com)',
			'icon': 'link',
			'filler': "This is a link",
			'type': 'inline'
		},
		{
			'name': 'unordered-list',
			'syntax': '- ${content}',
			'icon': 'ul',
			'filler': "This is an bulleted list item",
			'type': 'block'
		},
		{
			'name': 'ordered-list',
			'syntax': '1. ${content}',
			'icon': 'ol',
			'filler': "This is an numbered list item",
			'type': 'block'
		},
		{
			'name': 'blockquote',
			'syntax': '> ${content}',
			'icon': 'blockquote',
			'filler': "Lorem ipsum dolor sit amet, consectetur adipisicing elit. Id blanditiis voluptatem odit nesciunt. Fugit ipsam saepe, quisquam iste mollitia ducimus, recusandae, voluptatum libero eligendi nam sequi hic. Libero, tempore, suscipit!",
			'type': 'block'
		},

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


	var markdownify = function(event, syntax, filler, patternType) {
		event.preventDefault();

		// Inline Pattern Behavior

		// Single Empty line: insert pattern with filler text with filler text selected, cursor at selection beginning
		// Single Non-empty line: insert pattern with filler text with filler text selected, cursor at selection beginning
		// Single Line && Selection: replace selection with filler text, cursor at selection end.

		// Multiple Lines: Break up into single lines and do same as above for each line.


		// Block Pattern Behavior

		// Single Empty line: Create pattern (with appropriate whitespace) with filler text selected, cursor at selection beginning
		// Single Non-Empty line: Make entire line block pattern with cursor at end
		// Single Line && Selection: Make entire line block pattern with cursor at end

		// Multiple Empty Lines: Create pattern (with appropriate whitespace) with filler text selected, cursor at selection beginning.
		// Multiple Non-Empty Lines: Break up to individual lines and treat each as a single non-empty line
		// Multiple Lines with Partial or Complete Selection: Break up into individual lines and treat as single non-empty lines

		// ** For mixed multiline selections, keep empty lines as empty lines.

		//TODO: Fix selectionStart and selectionEnd to work with IE
		var selectionStart = markdownTextarea.get(0).selectionStart;
		var selectionEnd =  markdownTextarea.get(0).selectionEnd;
		
		var isSelection = selectionStart == selectionEnd ? false : true;

		// If patterntype is block, content should begin at beginning of line and end at the end of line
		if(patternType == "block") {
			while(markdownTextarea.val().charAt(selectionStart-1) != '\n' && selectionStart > 0) {
				selectionStart--;
			}
			while(markdownTextarea.val().charAt(selectionEnd) != '\n' && selectionEnd < markdownTextarea.val().length) {
				selectionEnd++;
			}
		}

		// Iterate over each line.
		// TODO: Deal with swapping of block patterns (turning a list item into a header)
		var newContent = "";
		var content = markdownTextarea.val().slice(selectionStart, selectionEnd).split(/\n/);
		$(content).each(function(index, contentLine) {

			if(contentLine == "") {
				contentLine = filler;
			}
			
			newContent = newContent + interpolate(syntax, {content: contentLine});
			if(index < content.length-1) {
				newContent = newContent + '\n';
			}
		});


		// Update undo/redo queue is possible with execCommand. Otherwise, replace text in textarea.
		// TODO: Would mutationObservers be a better way to implement this?
		if (document.queryCommandSupported('insertText')) {
			markdownTextarea.focus();
			//TODO: Fix selectionStart and selectionEnd to work with IE
			markdownTextarea.get(0).selectionStart = selectionStart;
			markdownTextarea.get(0).selectionEnd = selectionEnd;
		    document.execCommand('insertText', false, newContent);
		}
		else {
			var contentBefore = markdownTextarea.val().slice(0, selectionStart);
			var contentAfter = markdownTextarea.val().slice(selectionEnd, markdownTextarea.val().length)
			markdownTextarea.val(contentBefore + newContent + contentAfter)
		}
	}

	
	this.init = function() {

		// Add buttons to markdown bar and bind events
		$(PATTERNS).each(function(index, pattern) {
			var patternButton = $('<div class="button button--outline toolbar__item">' + pattern['icon'] +'</div>');
			patternButton.bind('click', function(event) {
				markdownify(event, pattern['syntax'], pattern['filler'], pattern['type']);
			});
			markdownBar.append(patternButton);
		});

		// TODO: Add undo/redo buttons
	}

	this.init();
}



$(document).ready(function() {
	var markdownBar = new MarkdownBar('.markdown-bar', '.markdown-textarea');
})