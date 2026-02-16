/* global inherits, Attacklab, gettext, showMessage, WrappedElement, setupButtonEventHandlers */
var ImageChanger = function () {
    WrappedElement.call(this);
    this._image_element = undefined;
    this._delete_button = undefined;
    this._save_url = undefined;
    this._delete_url = undefined;
    this._messages = undefined;
};
inherits(ImageChanger, WrappedElement);

ImageChanger.prototype.setImageElement = function (image_element) {
    this._image_element = image_element;
};

ImageChanger.prototype.setMessages = function (messages) {
    this._messages = messages;
};

ImageChanger.prototype.setDeleteButton = function (delete_button) {
    this._delete_button = delete_button;
};

ImageChanger.prototype.setSaveUrl = function (url) {
    this._save_url = url;
};

ImageChanger.prototype.setDeleteUrl = function (url) {
    this._delete_url = url;
};

ImageChanger.prototype.setAjaxData = function (data) {
    this._ajax_data = data;
};

ImageChanger.prototype.showImage = function (image_url) {
    this._image_element.attr('src', image_url);
    this._image_element.show();
};

ImageChanger.prototype.deleteImage = function () {
    this._image_element.attr('src', '');
    this._image_element.css('display', 'none');

    var me = this;
    var delete_url = this._delete_url;
    var data = this._ajax_data;
    $.ajax({
        type: 'POST',
        dataType: 'json',
        url: delete_url,
        data: data,
        cache: false,
        success: function (data) {
            if (data.success) {
                showMessage(me.getElement(), data.message, 'after');
            }
        }
    });
};

ImageChanger.prototype.saveImageUrl = function (image_url) {
    var me = this;
    var data = this._ajax_data;
    data.image_url = image_url;
    var save_url = this._save_url;
    $.ajax({
        type: 'POST',
        dataType: 'json',
        url: save_url,
        data: data,
        cache: false,
        success: function (data) {
            if (!data.success) {
                showMessage(me.getElement(), data.message, 'after');
            }
        }
    });
};

ImageChanger.prototype.startDialog = function () {
    //reusing the wmd's file uploader
    var me = this;
    var change_image_text = this._messages.change_image;
    var change_image_button = this._element;
    Attacklab.Util.prompt(
        gettext('Enter the logo url or upload an image'),
        '',
        function (image_url) {
            if (image_url) {
                me.saveImageUrl(image_url);
                me.showImage(image_url);
                change_image_button.html(change_image_text);
                me.showDeleteButton();
            }
        },
        'image'
    );
};

ImageChanger.prototype.showDeleteButton = function () {
    this._delete_button.show();
    this._delete_button.prev().show();
};

ImageChanger.prototype.hideDeleteButton = function () {
    this._delete_button.hide();
    this._delete_button.prev().hide();
};


ImageChanger.prototype.startDeleting = function () {
    if (confirm(gettext('Do you really want to remove the image?'))) {
        this.deleteImage();
        this._element.html(this._messages.add_image);
        this.hideDeleteButton();
        this._delete_button.hide();
        var sep = this._delete_button.prev();
        sep.hide();
    }
};

/**
 * decorates an element that will serve as the image changer button
 */
ImageChanger.prototype.decorate = function (element) {
    this._element = element;
    var me = this;
    setupButtonEventHandlers(
        element,
        function () {
            me.startDialog();
        }
    );
    setupButtonEventHandlers(
        this._delete_button,
        function () {
            me.startDeleting();
        }
    );
};
