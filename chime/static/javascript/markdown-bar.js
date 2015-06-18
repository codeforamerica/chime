// This js library builds the markdown formatting bar in Chime
// It also implements a custom undo/redo behavior for the markdown textarea using undo.js
// This is required to capture textarea content changes triggered from the formatting bar 
// Below is a list of expected behaviors:

// INLINE PATTERN BEHAVIOR

// Single Empty line: insert pattern with filler text
// Single Non-empty line: insert pattern with filler text
// Single Line && Selection: replace selection with filler text

// Multiple Lines: Break up into single lines and do same as above for each line.


// BLOCK PATTERN BEHAVIOR

// Single Empty line: Create pattern with filler text selected, cursor at selection beginning
// Single Non-Empty line: Make entire line block pattern with cursor at end
// Single Line && Selection: Make entire line block pattern with cursor at end

// Multiple Empty Lines: Create pattern with filler text selected, cursor at selection beginning.
// Multiple Non-Empty Lines: Break up to individual lines and treat each as a single non-empty line
// Multiple Lines with Partial or Complete Selection: Break up into individual lines and treat as single non-empty lines

// TODO: For mixed multiline selections, keep empty lines as empty lines.
// TODO: Deal with swapping of block patterns (e.g, turning a list item into a header)
// TOOD: Format whitespace around block elements.
// TODO: Implement ideal cursor position behavior after pattern is added
//	 - this includes preselection of filler text so user can start typing immediately without having to move the cursor.
// TODO: Make this work with IE.


function MarkdownBar(bar, textarea) {

	var self = this;
	var markdownBar = $(bar);
	var markdownTextarea = $(textarea);

	// This value is to keep track of where the current value is the textarea is. Used to compare 
	var startValue;

	//Implement Undo Stack
	var undoStack = new Undo.Stack();
	var EditCommand = Undo.Command.extend({
		constructor: function(textarea, oldValue, newValue) {
			this.textarea = textarea;
			this.oldValue = oldValue;
			this.newValue = newValue;
		},
		execute: function() {

		},
		undo: function() {
			this.textarea.val(this.oldValue)
			startValue = this.oldValue;
		},
		redo: function() {
			this.textarea.val(this.newValue)
			startValue = this.newValue;
		}
	})

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

	this.markdownify = function(event, syntax, filler, patternType) {
		event.preventDefault();

		startValue = markdownTextarea.val();

		//TODO: Fix selectionStart and selectionEnd to work with IE
		var selectionStart = markdownTextarea.get(0).selectionStart;
		var selectionEnd =  markdownTextarea.get(0).selectionEnd;

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
		var newContent = "";
		var content = markdownTextarea.val().slice(selectionStart, selectionEnd).split(/\n/);
		$(content).each(function(index, contentLine) {

			//Add filler text 
			if(contentLine == "") {
				contentLine = filler;
			}

			
			newContent = newContent + self.interpolate(syntax, {content: contentLine});
			if(index < content.length-1) {
				newContent = newContent + '\n';
			}
		});


		// Replace content in textarea
		var contentBefore = markdownTextarea.val().slice(0, selectionStart);
		var contentAfter = markdownTextarea.val().slice(selectionEnd, markdownTextarea.val().length)
		var newValue = (contentBefore + newContent + contentAfter);
		markdownTextarea.val(newValue);

		//Add to undo stack
		undoStack.execute(new EditCommand(markdownTextarea, startValue, newValue));
		startValue = newValue;

		markdownTextarea.focus();
	}

	// String interpolation function
	this.interpolate = function(formatString, data) {
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

	
	this.init = function() {

		// Bind Textarea to Undo Stack (reimplementing basic undo/redo functionality)
		var timer;
		markdownTextarea.bind('keyup', function(event) {
			// skip if keyup on 'Z' when undoing/redoing (metaKey is held down)
			if (event.metaKey && event.which == 90) {
				return false;
			}
			// skip if keyup on 'shift key' or 'command/window key'
			if(event.which == 16 || event.which == 91 || event.which == 93 || event.which == 224) {
				return false;
			}

			clearTimeout(timer);
			timer = setTimeout(function() {
				var newValue = markdownTextarea.val();
				// ignore meta key presses
				if (newValue != startValue) {
					undoStack.execute(new EditCommand(markdownTextarea, startValue, newValue));
					startValue = newValue;
				}
			}, 150);
		});


		// Add buttons to markdown bar and bind events
		$(PATTERNS).each(function(index, pattern) {
			var patternButton = $('<div class="button button--outline toolbar__item">' + pattern['icon'] +'</div>');
			patternButton.bind('click', function(event) {
				self.markdownify(event, pattern['syntax'], pattern['filler'], pattern['type']);
			});
			markdownBar.append(patternButton);
		});


		// Create Undo/Redo Keyboard Shortcuts
		$(document).keydown(function(event) {
			if (!event.metaKey || event.keyCode != 90) {
				return;
			}
			event.preventDefault();
			if (event.shiftKey) {
				undoStack.canRedo() && undoStack.redo()
			} else {
				undoStack.canUndo() && undoStack.undo();
			}
		});


		// Create Undo/redo buttons
		var undoButton = $('<button href="#" id="undo-button" class="toolbar__item button button--outline">undo</button>'),
			redoButton = $('<button href="#" id="redo-button" class="toolbar__item button button--outline">redo</button>')

		function updateUndoStackUI() {
			undoButton.attr("disabled", !undoStack.canUndo());
			redoButton.attr("disabled", !undoStack.canRedo());
		}

		undoStack.changed = function() {
			updateUndoStackUI();
		};


		undoButton.click(function(e) {
			undoStack['undo']();
			return false;
		});

		redoButton.click(function(e) {
			undoStack['redo']();
			return false;
		});

		markdownBar.append(undoButton);
		markdownBar.append(redoButton);
		updateUndoStackUI();
	}

	this.init();
}



$(document).ready(function() {
	var markdownBar = new MarkdownBar('.markdown-bar', '.markdown-textarea');
})