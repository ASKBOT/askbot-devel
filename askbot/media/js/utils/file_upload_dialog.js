/**
 * @constructor
 */
var FileUploadDialog = function () {
    ModalDialog.call(this);
    this._className = 'file-upload-dialog';
    this._post_upload_handler = undefined;
    this._fileType = 'image';
    this._headerEnabled = false;
};
inherits(FileUploadDialog, ModalDialog);

/**
 * allowed values: 'image', 'attachment'
 */
FileUploadDialog.prototype.setFileType = function (fileType) {
    this._fileType = fileType;
};

FileUploadDialog.prototype.getFileType = function () {
    return this._fileType;
};

FileUploadDialog.prototype.setButtonText = function (text) {
    this._fakeInput.html(text);
};

FileUploadDialog.prototype.setPostUploadHandler = function (handler) {
    this._post_upload_handler = handler;
};

FileUploadDialog.prototype.runPostUploadHandler = function (url, descr) {
    this._post_upload_handler(url, descr);
};

FileUploadDialog.prototype.setInputId = function (id) {
    this._input_id = id;
};

FileUploadDialog.prototype.getInputId = function () {
    return this._input_id;
};

FileUploadDialog.prototype.setErrorText = function (text) {
    this.setLabelText(text);
    this._label.addClass('error');
};

FileUploadDialog.prototype.setLabelText = function (text) {
    this._label.html(text);
    this._label.removeClass('error');
};

FileUploadDialog.prototype.setUrlInputTooltip = function (text) {
    this._url_input_tooltip = text;
};

FileUploadDialog.prototype.getUrl = function () {
    var val = $.trim(this._url_input_el.val());
    if (val.length > 0) {
        return val;
    }
    return '';
};

//disable description for now
//FileUploadDialog.prototype.getDescription = function () {
//    return this._description_input.getVal();
//};

FileUploadDialog.prototype.resetInputs = function () {
    this._url_input_el.val('');
    //this._description_input.reset();
    this._upload_input.val('');
    this._origFileName = undefined;
};

FileUploadDialog.prototype.getInputElement = function () {
    return $('#' + this.getInputId());
};

FileUploadDialog.prototype.installFileUploadHandler = function (handler) {
    var upload_input = this.getInputElement();
    upload_input.unbind('change');
    //todo: fix this - make event handler reinstall work
    upload_input.change(handler);
};

FileUploadDialog.prototype.show = function () {
    //hack around the ajaxFileUpload plugin
    FileUploadDialog.superClass_.show.call(this);
    var handler = this.getStartUploadHandler();
    this.installFileUploadHandler(handler);
};

FileUploadDialog.prototype.getUrlInputElement = function () {
    return this._url_input_el;
};

/*
 * argument startUploadHandler is very special it must
 * be a function calling this one!!! Todo: see if there
 * is a more civilized way to do this.
 */
FileUploadDialog.prototype.startFileUpload = function (startUploadHandler) {

    var spinner = this._spinner;
    var label = this._label;

    spinner.ajaxStart(function () {
        spinner.show();
        label.hide();
    });
    spinner.ajaxComplete(function () {
        spinner.hide();
        label.show();
    });

    /* important!!! upload input must be loaded by id
     * because ajaxFileUpload monkey-patches the upload form */
    var uploadInput = this.getInputElement();
    uploadInput.ajaxStart(function () { uploadInput.hide(); });
    uploadInput.ajaxComplete(function () { uploadInput.show(); });

    //var localFilePath = upload_input.val();

    var me = this;

    $.ajaxFileUpload({
        url: askbot.urls.upload,
        secureuri: false,//todo: check on https
        fileElementId: this.getInputId(),
        dataType: 'xml',
        success: function (data, status) {

            var fileURL = $(data).find('file_url').text();
            var origFileName = $(data).find('orig_file_name').text();
            var newStatus = interpolate(
                                gettext('Uploaded file: %s'),
                                [origFileName]
                            );
            /*
            * hopefully a fix for the "fakepath" issue
            * https://www.mediawiki.org/wiki/Special:Code/MediaWiki/83225
            */
            fileURL = fileURL.replace(/\w:.*\\(.*)$/, '$1');
            var error = $(data).find('error').text();
            if (error !== '') {
                me.setErrorText(error);
            } else {
                me._origFileName = origFileName;
                me.getUrlInputElement().attr('value', fileURL);
                me.setLabelText(newStatus);
                var buttonText = gettext('Choose a different file');
                if (me.getFileType() === 'image') {
                    buttonText = gettext('Choose a different image');
                }
                me.setButtonText(buttonText);
            }

            /* re-install this as the upload extension
             * will remove the handler to prevent double uploading
             * this hack is a manipulation around the
             * ajaxFileUpload jQuery plugin. */
            me.installFileUploadHandler(startUploadHandler);
        },
        error: function (data, status, e) {
            /* re-install this as the upload extension
            * will remove the handler to prevent double uploading */
            me.setErrorText(gettext('Oops, looks like we had an error. Sorry.'));
            me.installFileUploadHandler(startUploadHandler);
        }
    });
    return false;
};

FileUploadDialog.prototype.getStartUploadHandler = function () {
    var me = this;
    var handler = function () {
        /* the trick is that we need inside the function call
         * to have a reference to itself
         * in order to reinstall the handler later
         * because ajaxFileUpload jquery extension might be destroying it */
        return me.startFileUpload(handler);
    };
    return handler;
};

FileUploadDialog.prototype.createDom = function () {

    var superClass = FileUploadDialog.superClass_;

    var me = this;
    superClass.setAcceptHandler.call(this, function () {
        var url = $.trim(me.getUrl());
        //var description = me.getDescription();
        //@todo: have url cleaning code here
        if (url.length > 0) {
            me.runPostUploadHandler(url, me._origFileName);
            me.resetInputs();
        }
        me.hide();
    });
    superClass.setRejectHandler.call(this, function () {
        me.resetInputs();
        me.hide();
    });
    superClass.createDom.call(this);

    var form = this.makeElement('form');
    form.addClass('ajax-file-upload');
    form.css('margin-bottom', 0);
    this.prependContent(form);

    // Upload wrapper: hides native input behind styled button
    var uploadWrapper = this.makeElement('div');
    uploadWrapper.addClass('js-file-upload-wrapper');
    form.append(uploadWrapper);

    // Browser native file upload field (hidden via CSS, overlays the button)
    var upload_input = this.makeElement('input');
    upload_input.attr({
        id: this._input_id,
        type: 'file',
        name: 'file-upload'
    });
    uploadWrapper.append(upload_input);
    this._upload_input = upload_input;

    var fakeInput = this.makeElement('button');
    fakeInput.attr('type', 'button');
    fakeInput.addClass('btn');
    fakeInput.addClass('btn-muted');
    fakeInput.addClass('fake-file-input');
    var buttonText = gettext('Choose a file to insert');
    if (this._fileType === 'image') {
        buttonText = gettext('Choose an image to insert');
    }
    fakeInput.html(buttonText);
    this._fakeInput = fakeInput;
    uploadWrapper.append(fakeInput);

    setupButtonEventHandlers(fakeInput, function () { upload_input.click(); });

    // Label which will also serve as status display
    var label = this.makeElement('label');
    label.attr('for', this._input_id);
    var types = askbot.settings.allowedUploadFileTypes;
    types = types.join(', ');
    label.html(gettext('Allowed file types are:') + ' ' + types + '.');
    form.append(label);
    this._label = label;

    // Floating-label URL input
    var urlWrapper = this.makeElement('div');
    urlWrapper.addClass('js-labeled-input');
    urlWrapper.css('display', 'none');
    form.append(urlWrapper);
    this._urlWrapper = urlWrapper;

    var urlLabel = this.makeElement('label');
    urlLabel.attr('for', this._input_id + '-url');
    urlLabel.text(this._url_input_tooltip || gettext('Or paste file url here'));
    urlWrapper.append(urlLabel);

    var url_input_el = this.makeElement('input');
    url_input_el.attr('type', 'text');
    url_input_el.attr('id', this._input_id + '-url');
    urlWrapper.append(url_input_el);
    this._url_input_el = url_input_el;

    /* //Description input box
    var descr_input = new TippedInput();
    descr_input.setInstruction(gettext('Describe the image here'));
    this.makeElement('input');
    form.append(descr_input.getElement());
    form.append($('<br/>'));
    this._description_input = descr_input;
    */
    var spinner = this.makeElement('img');
    spinner.attr('src', mediaUrl('media/images/ajax-loader.gif'));
    spinner.css('display', 'none');
    spinner.addClass('spinner');
    form.append(spinner);
    this._spinner = spinner;

    upload_input.change(this.getStartUploadHandler());
};
