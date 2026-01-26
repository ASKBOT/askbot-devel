/**
 * @contstructor
 * Simple modal dialog with Ok/Cancel buttons by default
 */
var ModalDialog = function () {
    WrappedElement.call(this);
    this._accept_button_text = gettext('Ok');
    this._acceptBtnEnabled = true;
    this._reject_button_text = gettext('Cancel');
    this._heading_text = 'Add heading by setHeadingText()';
    this._title = undefined;
    this._initial_content = undefined;
    this._accept_handler = function () {};
    var me = this;
    this._reject_handler = function () {
        me.hide();
    };
    this._content_element = undefined;
    this._headerEnabled = true;
    this._className = undefined;
    this._escHandler = null;
};
inherits(ModalDialog, WrappedElement);

ModalDialog.prototype.show = function () {
    var me = this;
    this._escHandler = function(evt) {
        if (evt.keyCode === 27) { // ESC
            me.hide();
        }
    };
    $(document).on('keydown.modalDialog', this._escHandler);
    this._element.modal('show');
};

ModalDialog.prototype.hide = function () {
    if (this._escHandler) {
        $(document).off('keydown.modalDialog', this._escHandler);
        this._escHandler = null;
    }
    $.modal.close();
};

ModalDialog.prototype.setClass = function (cls) {
    this._cssClass = cls;
    if (this._element) {
        this._element.addClass(cls);
    }
};

ModalDialog.prototype.setContent = function (content) {
    this._initial_content = content;
    if (this._content_element) {
        this._content_element.html(content);
    }
};

ModalDialog.prototype.prependContent = function (content) {
    this._content_element.prepend(content);
};

ModalDialog.prototype.appendContent = function (content) {
  this._content_element.append(content);
};

ModalDialog.prototype.setHeadingText = function (text) {
    this._heading_text = text;
    if (this._title) this._title.text(text);
};

ModalDialog.prototype.setAcceptButtonText = function (text) {
    this._accept_button_text = text;
    if (this._acceptBtn) {
        this._acceptBtn.html(text);
    }
};

ModalDialog.prototype.setRejectButtonText = function (text) {
    this._reject_button_text = text;
};

ModalDialog.prototype.hideRejectButton = function () {
    if (!this._rejectButton) return; 
    this._rejectBtn.hide();
};

ModalDialog.prototype.hideAcceptButton = function () {
    if (!this._acceptButton) return; 
    this._acceptButton.hide();
};

ModalDialog.prototype.setAcceptHandler = function (handler) {
    this._accept_handler = handler;
};

ModalDialog.prototype.setRejectHandler = function (handler) {
    this._reject_handler = handler;
};

ModalDialog.prototype.clearMessages = function () {
    this._element.find('.alert').remove();
};

ModalDialog.prototype.setMessage = function (text, message_type) {
    var box = new AlertBox();
    box.setText(text);
    if (message_type === 'error') {
        box.setError(true);
    }
    this.prependContent(box.getElement());
};

ModalDialog.prototype.disableAcceptButton = function () {
    this._acceptBtnEnabled = false;
    if (this._acceptBtn) {
        this._acceptBtn.prop('disabled', true);
    }
};

ModalDialog.prototype.enableAcceptButton = function () {
    this._acceptBtnEnabled = true;
    if (this._acceptBtn) {
        this._acceptBtn.prop('disabled', false);
    }
};

ModalDialog.prototype.createDom = function () {
    this._element = this.makeElement('div');
    var element = this._element;

    if (this._cssClass) {
        element.addClass(this._cssClass);
    }

    element.addClass('js-modal');
    if (this._className) {
        element.addClass(this._className);
    }

    //1) create header
    var close_link = this.makeElement('div');
    if (this._headerEnabled) {
        var header = this.makeElement('div');
        header.addClass('js-modal-header');
        element.append(header);
        /*
        close_link.addClass('js-close');
        close_link.attr('data-dismiss', 'modal');
        close_link.html('x');
        header.append(close_link);
        */
        var title = this.makeElement('h3');
        title.text(this._heading_text);
        header.append(title);
        this._title = title;
    }

    //2) create content
    var body = this.makeElement('div');
    body.addClass('js-modal-body');
    element.append(body);
    this._content_element = body;
    if (this._initial_content) {
        this._content_element.append(this._initial_content);
    }

    //3) create footer with accept and reject buttons (ok/cancel).
    var footer = this.makeElement('div');
    footer.addClass('js-modal-footer');
    element.append(footer);

    var accept_btn = this.makeElement('button');
    if (this._acceptBtnEnabled === false) {
        accept_btn.prop('disabled', true);
    }
    accept_btn.addClass('btn');
    accept_btn.html(this._accept_button_text);
    footer.append(accept_btn);
    this._acceptBtn = accept_btn;

    var reject_btn = this.makeElement('button');
    if (this._reject_button_text) {
        reject_btn.addClass('btn');
        reject_btn.html(this._reject_button_text);
        footer.append(reject_btn);
        this._rejectBtn = reject_btn;
    }

    //4) attach event handlers to the buttons
    setupButtonEventHandlers(accept_btn, this._accept_handler);
    if (this._reject_button_text) {
        setupButtonEventHandlers(reject_btn, this._reject_handler);
    }
    if (this._headerEnabled) {
        setupButtonEventHandlers(close_link, this._reject_handler);
    }

    this.hide();
    //have to do this on document since _element is not in the DOM yet
    $(document).trigger('askbot.afterModalDialogCreateDom', [this]);
};
