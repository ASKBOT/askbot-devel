/* global askbot, gettext, getObjectByPath, inherits, parseUrl, runMathJax, showMessage, hljs,
 stripTags, getAskbotMarkdownConverter,
 setupButtonEventHandlers, SimpleEditor, WrappedElement, WMD */
/**
 * @constructor
 * Adds in-place text editor for a text value
 * of a database object. Whether editing is
 * permissible is to be enforced in the backend
 */
var Editable = function(){
  WrappedElement.call(this);
  this._state = 'display';//'edit' or 'display'
  this._isEditorLoaded = false;
  this._enabledEditorButtons = null;
  this._isPreviewerEnabled = false;
};
inherits(Editable, WrappedElement);

Editable.prototype.backupContent = function(){
  this._contentBackup = this._contentBox.contents();
};

Editable.prototype.setEnabledEditorButtons = function(buttons){
  this._enabledEditorButtons = buttons;
};

Editable.prototype.setPreviewerEnabled = function(state){
  this._isPreviewerEnabled = state;
  if (this.isEditorLoaded()){
    this._editor.setPreviewerEnabled(state);
  }
};

Editable.prototype.setContent = function(content){
  this._content.empty();
  this._content.append(content);
  hljs.highlightAll();
  if (askbot.settings.mathjaxEnabled) {
    runMathJax();
  }
};

Editable.prototype.setState = function(state){
  if (state === 'edit'){
    this._state = state;
    this._editorBox.show();
    this._editBtn.hide();
    this._formControls.show();
    this._hideables.hide();
    this._content.hide();
  } else if (state === 'display'){
    this._editorBox.hide();
    this._formControls.hide();
    this._editBtn.show();
    this._hideables.show();
    this._content.show();
  }
};

Editable.prototype.restoreContent = function(){
  var content_box = this._contentBox;
  content_box.empty();
  $.each(this._contentBackup, function(idx, element){
    content_box.append(element);
  });
};

Editable.prototype.isEditorLoaded = function(){
  return this._isEditorLoaded;
};

Editable.prototype.setEditorLoaded = function(){
  return this._isEditorLoaded = true;
};

Editable.prototype.getObjectId = function() {
  return this._objectId;
};

Editable.prototype.getAttributeName = function() {
  return this._attributeName;
};

Editable.prototype.startEditingText = function (text) {
  var ed = this._editor;
  this.setState('edit');
  if (this.isEditorLoaded() === false){
    ed.start();
    this.setEditorLoaded();
  }
  var onFocus = function () {
    ed.setText(text);
    ed.putCursorAtEnd();
  };
  ed.focus(onFocus);
}

/**
 * loads initial data for the editor input and activates
 * the editor
 */
Editable.prototype.startActivatingEditor = function (evt) {
  evt.preventDefault();

  var me = this;
  var paramName = this._saveTextParamName;

  $.ajax({
    type: 'GET',
    url: this._getTextUrl,
    data: this._getTextUrlParams,
    cache: false,
    success: function(data){
      me.startEditingText(data[paramName]);
    }
  });
  return false;
};

Editable.prototype.setError = function (text) {
  this._error.html(text);
};

Editable.prototype.clearError = function () {
  this._error.html('');
};

Editable.prototype.cancelEdit = function () {
  this.setState('display');
  this.clearError();
};

Editable.prototype.saveText = function () {
  var me = this;
  var editorText = this._editor.getText();

  if (this._validator) {
    try {
      this._validator(editorText);
      this.clearError();
    } catch (e) {
      this.setError(e);
      return;
    }
  }

  //optimistic update
  if (this._editorType === 'markdown') {
    var converter = getAskbotMarkdownConverter();
    editorText = converter.makeHtml(editorText);
  }
  this.setContent(editorText);
  this.setState('display');
  
  var data = this._saveTextUrlParams;
  if (this._suppressEmailCb) {
    data['suppress_email'] = this._suppressEmailCb.is(':checked');
  }

  editorText = this._editor.getText();
  data[this._saveTextParamName] = editorText;
  var validatedParamName = this._validatedTextParamName;

  $.ajax({
    type: 'POST',
    dataType: 'json',
    url: this._saveTextUrl,
    data: data,
    cache: false,
    success: function(data){
      if (data['success']){
        me.setContent(data[validatedParamName]);
      } else {
        me.setState('edit');
        showMessage(me.getElement(), data['message']);
      }
    }
  });
};

Editable.prototype.decorate = function(element){
   /* expected markup
    <div class="js-editable"
      id="js-<something>" //here "something" must be unique enough
      // 1. urls below are parsed and parameters added as part of request
      //    this way url parameter input is more compact and comes with the 
      //    corresponding url
      // 2. the getTextUrl is optional - if absent, text will be taken as
      //    displayed in the html. This feature won't work with the markdown editor
      data-get-text-url="{% url user_get_description %}?user_id={{ view_user.pk }}"
      data-save-text-url="{% url user_set_description %}?user_id={{ view_user.pk }}"
      // this parameter will be added to the POST request made to saveTextUrl
      data-save-text-param-name="description"
      // this parameter is optional, used to retreive data from server after saving
      // i.e. when saved data is first validated and perhaps parsed
      //if absent, assumed value will be the same as saveTextParamName
      data-validated-text-param-name="description_html"
      // depending on the editor type we might ignore the getTextUrl
      // as we need the access the url only in the case of markdown editor
      data-editor-type="<one of supported editor types>"
      data-editor-compact="true"//optional
    >
      //this item must be inside of js-editable
      <div class="js-editable-content">some text which will be editable</div>
      // the button as shown below does not have to be inside of js-editable.
      // we find the button by the Id, which starts with js-edit-btn and 
      // ends the same as id of the .js-editable
      // Also, the html elements of button and the container are not important,
      // only ids, class names and "data" parameters on the .js-editable
      // the <something> in the id below must be the same as in the id of
      // the .js-editable
      <button id="js-edit-btn-<something>">{% trans %}edit{% endtrans %}</button>
    </div>
  */
  var parsed, editor;
  this._element = element;
  //validate that id starts with "js-" and is longer than 3 chars
  var id = element.attr('id');
  if ( !id || id.length <= 3 ) {
    throw "id of .js-editable must have > 3 characters";
  }
  if ( id.substr(0, 3) !== 'js-' ) {
    throw "id of .js-editable must start with js-";
  }
  this._id = id.substr(3);
  this._content = element.find('.js-editable-content');
  //must be defined
  var editBtn = $(document.getElementById('js-edit-btn-' + this._id));
  if ( !editBtn ) {
    throw "edit button with id js-edit-btn-" + this._id + " is required";
  }
  this._editBtn = editBtn;

  var err = element.find('.js-error');
  if (err.length === 0) {
    err = this.makeElement('div');
    err.addClass('js-error');
    this._element.prepend(err);
  }
  this._error = err;

  //parse these two urls and separate url and the params
  var getTextUrl = element.data('getTextUrl');
  if (getTextUrl) {
    parsed = parseUrl(element.data('getTextUrl'));
    this._getTextUrl = parsed[0];
    this._getTextUrlParams = parsed[1];
  } else {
    this._getTextUrl = undefined;
    this._getTextUrlParams = undefined;
  }

  parsed = parseUrl(element.data('saveTextUrl'));
  this._saveTextUrl = parsed[0];
  this._saveTextUrlParams = parsed[1];

  this._saveTextParamName = element.data('saveTextParamName');
  this._validatedTextParamName = element.data('validatedTextParamName') || this._saveTextParamName;

  this._useCompactEditor = element.data('editorCompact');

  var validatorPath = element.data('validator');
  if (validatorPath) {
    this._validator = getObjectByPath(validatorPath);
  }

  //create container for the editor and buttons
  var editorBox = this.makeElement('div');
  this._content.after(editorBox);
  this._editorBox = editorBox;

  //create editor
  var editorType = element.data('editorType') || askbot['settings']['editorType'];
  var minLines = element.data('minLines') || 1;
  this._editorType = editorType;
  if (editorType === 'markdown') {
    editor = new WMD({'minLines': minLines});
    if (this._useCompactEditor) {
      editor.setEnabledButtons('bold italic link code ol ul');
    }
    var preview = element.data('previewerEnabled');
    editor.setPreviewerEnabled(preview);
  } else {
    editor = new SimpleEditor({'minLines': minLines});
  }
  this._editor = editor;
  editorBox.append(editor.getElement());
  editorBox.hide();

  //adding two buttons...
  var formControls = element.find('.js-editable-controls');
  this._formControls = formControls;
  if (formControls.length === 0) {
    formControls = this.makeElement('div');
    formControls.addClass('.js-editable-controls');
    editorBox.append(formControls);
  }

  this._hideables = $('.js-editable-hide-' + this._id);

  var saveBtn = this.makeElement('button');
  saveBtn.addClass('btn');
  //saveBtn.addClass('btn btn-primary');
  saveBtn.html(gettext('save'));
  formControls.append(saveBtn);
  this._saveBtn = saveBtn;

  var cancelBtn = this.makeElement('button');
  cancelBtn.addClass('btn');
  cancelBtn.html(gettext('cancel'));
  //cancelBtn.addClass('btn');
  formControls.append(cancelBtn);
  this._cancelBtn = cancelBtn;

  if (element.data('withSuppressEmailCheckbox')) {
    var cb = $('<input type="checkbox" />');
    var cbId = this._id + '-suppress-email-cb'
    cb.attr('id', cbId);
    if (element.data('withSuppressEmailCheckboxChecked')) {
      cb.prop('checked', true);
    }
    this._suppressEmailCb = cb;
    formControls.append(cb);
    var label = $('<label>' + gettext("minor edit (don't send alerts)") + '</label>');
    label.attr('for', cbId);
    formControls.append(label);
  }

  this.setState('display');

  var me = this;
  setupButtonEventHandlers(editBtn, function(evt){ me.startActivatingEditor(evt) });
  setupButtonEventHandlers(cancelBtn, function(){ me.cancelEdit() });
  setupButtonEventHandlers(saveBtn, function(){ me.saveText() });
};

(function () {
  var items = $('.js-editable');
  $.each(items, function(idx, item) {
    var editable = new Editable();
    editable.decorate($(item));
  });
})();
