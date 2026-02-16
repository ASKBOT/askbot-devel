/* global askbot, getTemplate, Attacklab, SimpleEditor, inherits, WMDExpanderToggle, addExtraCssClasses, getSuperClass */
/**
 * @constructor
 * a wrapper for the WMD editor
 */
var WMD = function (opts) {
    SimpleEditor.call(this, opts);
    this._text = undefined;
    var allButtons = 'bold italic link blockquote code image attachment ol ul heading hr';
    this._enabled_buttons = this.filterEnabledButtons(allButtons);
    this._previewerEnabled = true;
};
inherits(WMD, SimpleEditor);

//@todo: implement getHtml method that runs text through showdown renderer

WMD.prototype.setEnabledButtons = function (buttons) {
  this._enabled_buttons = this.filterEnabledButtons(buttons);
};

WMD.prototype.filterEnabledButtons = function (buttons) {
  var buttonsList = buttons.split(' ');
  var filteredList = buttonsList.filter(function (button) {
    if (button === 'image') return askbot.data.userCanUploadImage;
    if (button === 'image') return askbot.data.userCanUploadAttachment;
    return true;
  });
  return filteredList.join(' ');
};

WMD.prototype.setPreviewerEnabled = function (enabledStatus) {
    this._previewerEnabled = enabledStatus;
    if (this._previewer) {
        if (enabledStatus) {
            this._previewer.show();
            this._previewerToggle.show();
        } else {
            this._previewer.hide();
            this._previewerToggle.hide();
        }
    }
};

WMD.prototype.getPreviewerEnabled = function () {
    return this._previewerEnabled;
};

WMD.prototype.getPreviewerElement = function () {
    return this._previewer;
};

WMD.prototype.getEditorElement = function () {
    return this._editor;
};

WMD.prototype.createDom = function () {
    this._element = this.makeElement('div');
    var clearfix = this.makeElement('div').addClass('clearfix');
    this._element.append(clearfix);

    var wmd_container = this.makeElement('div');
    wmd_container.addClass('wmd-container');
    this._editor = wmd_container;

    this._element.append(wmd_container);

    var wmd_buttons = this.makeElement('div')
                        .attr('id', this.makeId('wmd-button-bar'))
                        .addClass('wmd-panel');
    wmd_container.append(wmd_buttons);

    // Help panel is now rendered by Svelte component (EditorHelpPanel)
    // which is initialized when the WMD editor starts

    var editor = this.makeElement('textarea')
                        .attr('id', this.makeId('editor'));
    addExtraCssClasses(editor, 'editorClasses');
    if (this._textareaName) {
        editor.attr('name', this._textareaName);
    }

    wmd_container.append(editor);
    this._textarea = editor;

    var mirror = this.makeElement('pre').addClass('mirror');
    wmd_container.append(mirror);
    this._mirror = mirror;
    $(editor).on('change paste keyup keydown', this.getAutoResizeHandler());


    if (this._text) {
        editor.val(this._text);
    }

    var previewer = this.makeElement('div')
                        .attr('id', this.makeId('previewer'))
                        .addClass('wmd-preview');
    this._previewer = previewer;

    var toggle = new WMDExpanderToggle(this);
    this._previewerToggle = toggle;
    wmd_container.append(toggle.getElement());

    wmd_container.append(previewer);

    if (this._previewerEnabled === false) {
        previewer.hide();
        this._previewerToggle.hide();
    }
};

WMD.prototype.decorate = function (element) {
    this._element = element;
    this._textarea = element.find('textarea');
    this._previewer = element.find('.wmd-preview');
    this._mirror = element.find('.mirror');
    this._textarea.on('change paste keyup keydown', this.getAutoResizeHandler());
};

WMD.prototype.start = function () {
    Attacklab.Util.startEditor(true, this._enabled_buttons, this.getIdSeed());
    getSuperClass(WMD).start.call(this);
};
