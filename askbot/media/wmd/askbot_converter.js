// Askbot adapter to markdown converter;
var getAskbotMarkdownConverter = function() {
    askbot['controllers'] = askbot['controllers'] || {};
    var converter = askbot['controllers']['markdownConverter'];
    if (!converter) {
        converter = new AskbotMarkdownConverter();
        askbot['controllers']['markdownConverter'] = converter;
    }
    return converter;
};

var AskbotMarkdownConverter = function() {
    this._converter = new Markdown.getSanitizingConverter();
    this._timeout = null;
};

AskbotMarkdownConverter.prototype.scheduleMathJaxRendering = function () {
    if (this._timeout) {
        clearTimeout(this._timeout);
    }
    var renderFunc = function () {
        MathJax.Hub.Queue(['Typeset', MathJax.Hub, 'previewer']);
    };
    this._timeout = setTimeout(renderFunc, 500);
};

AskbotMarkdownConverter.prototype.makeHtml = function (text) {
    var makeHtmlBase = this._converter.makeHtml;
    if (askbot['settings']['mathjaxEnabled'] === false){
        return makeHtmlBase(text);
    } else if (typeof MathJax != 'undefined') {
        MathJax.Hub.queue.Push(
            function(){
                $('#previewer').html(makeHtmlBase(text));
            }
        );
        this.scheduleMathJaxRendering();
        return $('#previewer').html();
    } else {
        console.log('Could not load MathJax');
        return makeHtmlBase(text);
    }
};
