describe("The markdown bar", function() {

  var form;

  beforeEach(function(){
    form = $('<div class="markdown-bar"></div><textarea class="markdown-textarea"></textarea>');
    $(document.body).append(form);
    var markdownBar = new MarkdownBar('.markdown-bar', '.markdown-textarea');
  });

 
  afterEach(function(){
   form.remove();
   form = null;
  });
    
  it("should have a single bold button", function() {
    var button = $(".fa-bold");
    expect(button.length).toEqual(1);
  });

  it("should have a single italic button", function() {
    var button = $(".fa-italic");
    expect(button.length).toEqual(1);
  });

  it("should have a single link button", function() {
    var button = $(".fa-link");
    expect(button.length).toEqual(1);
  });

 /* it("should have a single h1 button", function() {
    var button = $(".fa-h1");
    expect(button.length).toEqual(1);
  });

  it("should have a single h2 button", function() {
    var button = $(".fa-h2");
    expect(button.length).toEqual(1);
  });

  it("should have a single h3 button", function() {
    var button = $(".fa-h3");
    expect(button.length).toEqual(1);
  });*/

  it("should have a single unordered list button", function() {
    var button = $(".fa-list-ul");
    expect(button.length).toEqual(1);
  });

  it("should have a single ordered list button", function() {
    var button = $(".fa-list-ol");
    expect(button.length).toEqual(1);
  });

  it("should have a single blockquote button", function() {
    var button = $(".fa-quote-right");
    expect(button.length).toEqual(1);
  });
});
describe("When the bold button is pressed", function() {
    it("should add placeholder text with the correct punctuation to the textarea", function(){
      expect( ).toEqual();

    });
    it("should wrap highlighted text in the correct punctuation", function(){
      expect( ).toEqual();

    });
});


