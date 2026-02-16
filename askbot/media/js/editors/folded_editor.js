/**
 * @constructor
 * An element that encloses an editor and everything inside it.
 * By default editor is hidden and user sees a box with a prompt
 * suggesting to make a post.
 * When user clicks, editor becomes accessible.
 */
var FoldedEditor = function () {
    WrappedElement.call(this);
};
inherits(FoldedEditor, WrappedElement);

FoldedEditor.prototype.getEditor = function () {
    return this._editor;
};

FoldedEditor.prototype.getEditorInputId = function () {
    return this._element.find('textarea').attr('id');
};

FoldedEditor.prototype.onAfterOpenHandler = function () {
    var editor = this.getEditor();
    if (editor) {
        editor.start();
        editor.focus(function(){
            editor.putCursorAtStart();
            $(document).trigger('askbot.FoldedEditor.afterOpened', [this]);
        });
    }
};

FoldedEditor.prototype.getOpenHandler = function () {
    var editorBox = this._editorBox;
    var promptBox = this._prompt;
    var me = this;
    return function () {
        if (askbot.data.userIsReadOnly === true) {
            notify.show(gettext('Sorry, you have only read access'));
        } else {
            promptBox.hide();
            editorBox.show();
            var element = me.getElement();
            element.addClass('js-active');

            /* make the editor one shot - once it unfolds it's
            * not accepting any events
            */
            element.unbind('click');
            element.unbind('focus');

            /* this function will open the editor
            * and focus cursor on the editor
            */
            me.onAfterOpenHandler();
        }
    };
};

FoldedEditor.prototype.decorate = function (element) {
    this._element = element;
    this._prompt = element.find('.js-folded-editor-trigger');
    this._editorBox = element.find('.js-folded-editor-editor');

    var editorType = askbot.settings.editorType;
    var editor;

    if (editorType === 'markdown') {
        editor = new WMD({'minLines': 10});
        editor.setIdSeed('');
    } else {
        throw 'wrong editor type "' + editorType + '"'
    }
    editor.setTextareaName('text');
    this._editor = editor;

    var placeHolder = element.find('.js-editor-placeholder');
    editor.setText(placeHolder.data('draftAnswer'));
    placeHolder.append(editor.getElement());
    //editor.start();

    var openHandler = this.getOpenHandler();
    element.click(openHandler);
    element.focus(openHandler);
};
