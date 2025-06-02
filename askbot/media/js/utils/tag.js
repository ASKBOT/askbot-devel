var Tag = function () {
    SimpleControl.call(this);
    this._deletable = false;
    this._delete_handler = null;
    this._delete_icon_title = null;
    this._tag_title = null;
    this._name = null;
    this._url_params = '';
    this._inner_html_tag = 'a';
};
inherits(Tag, SimpleControl);

Tag.prototype.setName = function (name) {
    this._name = name;
};

Tag.prototype.getName = function () {
    return this._name;
};

Tag.prototype.setDeletable = function (is_deletable) {
    this._deletable = is_deletable;
};

Tag.prototype.setLinkable = function (is_linkable) {
    if (is_linkable === true) {
        this._inner_html_tag = 'a';
    } else {
        this._inner_html_tag = 'span';
    }
};

Tag.prototype.isLinkable = function () {
    return (this._inner_html_tag === 'a');
};

Tag.prototype.isDeletable = function () {
    return this._deletable;
};

Tag.prototype.isWildcard = function () {
    return (this.getName().substr(-1) === '*');
};

Tag.prototype.setUrlParams = function (url_params) {
    this._url_params = url_params;
};

Tag.prototype.setHandlerInternal = function () {
    setupButtonEventHandlers(this._element.find('.js-tag-name'), this._handler);
};

/* delete handler will be specific to the task */
Tag.prototype.setDeleteHandler = function (delete_handler) {
    this._delete_handler = delete_handler;
    if (this.hasElement() && this.isDeletable()) {
        this._delete_icon.setHandler(delete_handler);
    }
};

Tag.prototype.getDeleteHandler = function () {
    return this._delete_handler;
};

Tag.prototype.setDeleteIconTitle = function (title) {
    this._delete_icon_title = title;
};

Tag.prototype.decorate = function (element) {
    this._element = element;
    var del = element.find('.js-delete-icon');
    if (del.length === 1) {
        this.setDeletable(true);
        this._delete_icon = new DeleteIcon();
        if (this._delete_icon_title !== null) {
            this._delete_icon.setTitle(this._delete_icon_title);
        }
        //do not set the delete handler here
        this._delete_icon.decorate(del);
    }
    this._inner_element = this._element.find('.js-tag-name');
    this._name = this.decodeTagName(
        $.trim(this._inner_element.attr('data-tag-name'))
    );
    if (this._title !== null) {
        this._inner_element.attr('title', this._title);
    }
    if (this._handler !== null) {
        this.setHandlerInternal();
    }
};

Tag.prototype.getDisplayTagName = function () {
    //replaces the trailing * symbol with the unicode asterisk
    return this._name.replace(/\*$/, '&#10045;');
};

Tag.prototype.decodeTagName = function (encoded_name) {
    return encoded_name.replace('\u273d', '*');
};

Tag.prototype.isAdminTag = function () {
    var nameLower = this.getName().toLowerCase();
    return askbot.data['adminTagsLowerCased'].includes(nameLower);
};

Tag.prototype.createDom = function () {
    this._element = getTemplate('.js-tag');
    if (this.isAdminTag()) {
        this._element.addClass('js-admin-tag');
    }
    //render the outer element
    var deleter = this._element.find('.js-delete-icon');
    if (!this.isDeletable()) {
        this._element.removeClass('js-deletable-tag');
        deleter.remove();
    } else {
        var del = new DeleteIcon();
        del.setHandler(this.getDeleteHandler());
        if (this._delete_icon_title !== null) {
            del.setTitle(this._delete_icon_title);
        }
        del.decorate(deleter);
        this._delete_icon = del;
    }
    //render the inner element
    this._inner_element = this._element.find('.js-tag-name');
    if (this._title === null) {
        var name = this.getName();
        this.setTitle(interpolate(gettext('see questions tagged \'%s\''), [name]));
    }
    if (this.isLinkable()) {
        //"replace" tag to 'a'
        this._inner_element = setHtmlTag(this._inner_element, 'a');
        var url = askbot.urls.questions;
        url += QSutils.add_search_tag(this._url_params, this.getName());
        this._inner_element.attr('href', url);
    }
    this._inner_element.attr('title', this._title);
    this._inner_element.html(this.getDisplayTagName());
    this._inner_element.data('tagName', this.getName());


    if (!this.isLinkable() && this._handler !== null) {
        this.setHandlerInternal();
    }
};
