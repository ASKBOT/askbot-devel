/* global askbot, getFontProps, getKeyCode, getTemplate, putCursorAtEnd, WrappedElement, inherits, addExtraCssClasses */
/**
 * @constructor
 * a simple textarea-based editor
 */
var SimpleEditor = function (attrs) {
    WrappedElement.call(this);
    attrs = attrs || {};
    this._rows = attrs.rows || 10;
    this._cols = attrs.cols || 60;
    this._minLines = attrs.minLines || 1;
    this._maxlength = attrs.maxlength || 1000;
};
inherits(SimpleEditor, WrappedElement);

SimpleEditor.prototype.focus = function (onFocus) {
    this._textarea.focus();
    if (onFocus) {
        onFocus();
    }
};

SimpleEditor.prototype.putCursorAtEnd = function () {
    putCursorAtEnd(this._textarea);
};

SimpleEditor.prototype.putCursorAtStart = function () {
    var textarea = this._textarea[0];
    if (textarea.setSelectionRange) {
        textarea.setSelectionRange(0, 0);
    } else if (textarea.createTextRange) {
        // IE support
        var range = textarea.createTextRange();
        range.moveStart('character', 0);
        range.select();
    }
    textarea.scrollTop = 0;
};

SimpleEditor.prototype.start = function () {
    this.getAutoResizeHandler()();
};

SimpleEditor.prototype.setHighlight = function (isHighlighted) {
    if (isHighlighted === true) {
        this._textarea.addClass('highlight');
    } else {
        this._textarea.removeClass('highlight');
    }
};

SimpleEditor.prototype.setTextareaName = function (name) {
    this._textareaName = name;
};


SimpleEditor.prototype.getText = function () {
    return $.trim(this._textarea.val());
};

SimpleEditor.prototype.getHtml = function () {
    return '<div class="transient-comment"><p>' + this.getText() + '</p></div>';
};

SimpleEditor.prototype.setText = function (text) {
    this._text = text;
    if (this._textarea) {
        this._textarea.val(text);
        this.getAutoResizeHandler()();
    }
};

SimpleEditor.prototype.getAutoResizeHandler = function() {
    var textarea = this._textarea;
    var mirror = this._mirror;
    var minLines = this._minLines;
    var me = this;
    return function(evt) {
        me.setMirrorStyle();
        var text = me.getText();
        if (evt) {
            if (evt.type == 'keydown' && getKeyCode(evt) == 13) {
                text += '\nZ';//add one char after newline
            } else if (/(\r|\n)$/.exec(evt.target.value)) {
                text += '\nZ';//add one char after newline
            }
        }
        mirror.text(text);
        var height = mirror.height();
        var lineHeight = parseInt(textarea.css('line-height'));
        height = lineHeight * Math.max(Math.round(height/lineHeight), minLines);
        textarea.css('height', height + 8);
    }
};

SimpleEditor.prototype.setMirrorStyle = function() {
    //copy styles into mirror from the textarea
    var textarea = this._textarea;
    var mirrorCss = {
        'position': 'absolute',
        'left': '-999rem',
        'padding': textarea.css('padding'),
        'margin': textarea.css('margin'),
        'white-space': textarea.css('white-space'),
        'width': textarea.css('width'),
        'word-wrap': textarea.css('word-wrap'),
        'word-break': textarea.css('word-break'),
        'overflow': textarea.css('overflow')
    };
    //for IE, as .css('font') fails
    var fontProps = getFontProps(textarea);
    mirrorCss = $.extend(mirrorCss, fontProps);
    this._mirror.css(mirrorCss);
};

/**
 * a textarea inside a div,
 * the reason for this is that we subclass this
 * in WMD, and that one requires a more complex structure
 */
SimpleEditor.prototype.createDom = function () {
    this._element = getTemplate('.js-simple-editor');
    var textarea = this._element.find('textarea');
    var mirror = this._element.find('.mirror');

    this._textarea = textarea;
    this._mirror = mirror;

    addExtraCssClasses(textarea, 'editorClasses');
    if (this._text) {
        textarea.val(this._text);
    }
    textarea.attr({
        'cols': this._cols,
        'rows': this._rows,
        'maxlength': this._maxlength
    });
    if (this._textareaName) {
        textarea.attr('name', this._textareaName);
    }

    textarea.on('change paste keyup keydown', this.getAutoResizeHandler());
};
