/* global askbot, AutoCompleter, cleanTag, inherits, WrappedElement, interpolate, gettext, ngettext,
 putCursorAtEnd, Tag */
var TagEditor = function () {
    WrappedElement.call(this);
    this._has_hot_backspace = false;
    this._settings = JSON.parse(askbot.settings.tag_editor);
};
inherits(TagEditor, WrappedElement);

TagEditor.prototype.getSelectedTags = function () {
    return $.trim(this._hidden_tags_input.val()).split(/\s+/);
};

TagEditor.prototype.setSelectedTags = function (tag_names) {
    this._hidden_tags_input.val($.trim(tag_names.join(' ')));
};

TagEditor.prototype.addSelectedTag = function (tag_name) {
    var tag_names = this._hidden_tags_input.val();
    this._hidden_tags_input.val(tag_names + ' ' + tag_name);
    $('.acResults').hide();//a hack to hide the autocompleter
};

TagEditor.prototype.isSelectedTagName = function (tag_name) {
    var tag_names = this.getSelectedTags();
    return $.inArray(tag_name, tag_names) !== -1;
};

TagEditor.prototype.removeSelectedTag = function (tag_name) {
    var tag_names = this.getSelectedTags();
    var idx = $.inArray(tag_name, tag_names);
    if (idx !== -1) {
        tag_names.splice(idx, 1);
    }
    this.setSelectedTags(tag_names);
};

TagEditor.prototype.getTagDeleteHandler = function (tag) {
    var me = this;
    return function () {
        me.removeSelectedTag(tag.getName());
        me.clearErrorMessage();
        var li = tag.getElement().parent();
        tag.dispose();
        li.remove();
        $('.acResults').hide();//a hack to hide the autocompleter
        me.fixHeight();
    };
};

TagEditor.prototype.cleanTag = function (tag_name, reject_dupe) {
    tag_name = $.trim(tag_name);
    tag_name = tag_name.replace(/\s+/, ' ');

    var force_lowercase = this._settings.force_lowercase_tags;
    if (force_lowercase) {
        tag_name = tag_name.toLowerCase();
    }

    if (reject_dupe && this.isSelectedTagName(tag_name)) {
        throw interpolate(
            gettext('tag "%s" was already added, no need to repeat (press "escape" to delete)'),
            [tag_name]
        );
    }

    var max_tags = this._settings.max_tags_per_post;
    if (this.getSelectedTags().length + 1 > max_tags) {//count current
        throw interpolate(
            ngettext(
                'a maximum of %s tag is allowed',
                'a maximum of %s tags are allowed',
                max_tags
            ),
            [max_tags]
        );
    }

    //generic cleaning
    return cleanTag(tag_name, this._settings);
};

TagEditor.prototype.addTag = function (tag_name) {
    var tag = new Tag();
    tag.setName(tag_name);
    tag.setDeletable(!tag.isAdminTag() || askbot.data["userIsAdminOrMod"]);
    tag.setLinkable(true);
    tag.setDeleteHandler(this.getTagDeleteHandler(tag));
    var li = this.makeElement('li');
    this._tags_container.append(li);
    li.append(tag.getElement());
    this.addSelectedTag(tag_name);
};

TagEditor.prototype.immediateClearErrorMessage = function () {
    this._error_alert.html('');
    this._error_alert.show();
    //this._element.css('margin-top', '18px');//todo: the margin thing is a hack
};

TagEditor.prototype.clearErrorMessage = function (fade) {
    if (fade) {
        var me = this;
        this._error_alert.fadeOut(function () {
            me.immediateClearErrorMessage();
        });
    } else {
        this.immediateClearErrorMessage();
    }
};

TagEditor.prototype.setErrorMessage = function (text) {
    var old_text = this._error_alert.html();
    this._error_alert.html(text);
    if (old_text === '') {
        this._error_alert.hide();
        this._error_alert.fadeIn(100);
    }
    //this._element.css('margin-top', '0');//todo: remove this hack
};

TagEditor.prototype.getAddTagHandler = function () {
    var me = this;
    return function (tag_name) {
        if (me.isSelectedTagName(tag_name)) {
            return;
        }
        try {
            var cleanTagName = me.cleanTag($.trim(tag_name));
            me.addTag(cleanTagName);
            me.clearNewTagInput();
            me.fixHeight();
        } catch (error) {
            me.setErrorMessage(error);
            setTimeout(function () {
                me.clearErrorMessage(true);
            }, 1000);
        }
    };
};

TagEditor.prototype.getRawNewTagValue = function () {
    return this._visible_tags_input.val();//without trimming
};

TagEditor.prototype.clearNewTagInput = function () {
    return this._visible_tags_input.val('');
};

TagEditor.prototype.editLastTag = function () {
    //delete rendered tag
    var tc = this._tags_container;
    tc.find('li:last').remove();
    //remove from hidden tags input
    var tags = this.getSelectedTags();
    var last_tag = tags.pop();
    this.setSelectedTags(tags);
    //populate the tag editor
    this._visible_tags_input.val(last_tag);
    putCursorAtEnd(this._visible_tags_input);
};

TagEditor.prototype.setHotBackspace = function (is_hot) {
    this._has_hot_backspace = is_hot;
};

TagEditor.prototype.hasHotBackspace = function () {
    return this._has_hot_backspace;
};

TagEditor.prototype.completeTagInput = function (reject_dupe) {
    var tag_name = $.trim(this._visible_tags_input.val());
    try {
        tag_name = this.cleanTag(tag_name, reject_dupe);
        this.addTag(tag_name);
        this.clearNewTagInput();
    } catch (error) {
        this.setErrorMessage(error);
    }
};

TagEditor.prototype.saveHeight = function () {
    return;
    // var elem = this._visible_tags_input;
    // this._height = elem.offset().top;
};

TagEditor.prototype.fixHeight = function () {
    return;
    // var new_height = this._visible_tags_input.offset().top;
    // //@todo: replace this by real measurement
    // var element_height = parseInt(
    //     this._element.css('height').replace('px', '')
    // );
    // if (new_height > this._height) {
    //     this._element.css('height', element_height + 28);//magic number!!!
    // } else if (new_height < this._height) {
    //     this._element.css('height', element_height - 28);//magic number!!!
    // }
    // this.saveHeight();
};

TagEditor.prototype.closeAutoCompleter = function () {
    this._autocompleter.finish();
};

TagEditor.prototype.getTagInputKeyHandler = function () {
    var me = this;
    return function (e) {
        if (e.shiftKey) {
            return;
        }
        me.saveHeight();
        var key = e.which || e.keyCode;
        var text = me.getRawNewTagValue();

        //space 32, enter 13
        if (key === 32 || key === 13) {
            var tag_name = $.trim(text);
            if (tag_name.length > 0) {
                try {
                    tag_name = me.cleanTag(tag_name, true);
                    $.ajax({
                        type: 'POST',
                        url: askbot['urls']['cleanTagName'],
                        data: {'tag_name': tag_name},
                        dataType: 'json',
                        cache: false,
                        success: function (data) {
                            if (data['success']) {
                                me.addTag(data['cleaned_tag_name']);
                                me.clearNewTagInput();
                                me.fixHeight();
                            } else if (data['message']) {
                                me.setErrorMessage(data['message']);
                                setTimeout(function () {
                                    me.clearErrorMessage(true);
                                }, 1000);
                            }
                        }
                    });
                } catch (error) {
                    me.setErrorMessage(error);
                }
            }
            return false;
        }

        if (text === '') {
            me.clearErrorMessage();
            me.closeAutoCompleter();
        } else {
            try {
                /* do-nothing validation here
                 * just to report any errors while
                 * the user is typing */
                me.cleanTag(text);
                me.clearErrorMessage();
            } catch (error) {
                me.setErrorMessage(error);
            }
        }

        //8 is backspace
        if (key === 8 && text.length === 0) {
            if (me.hasHotBackspace() === true) {
                me.editLastTag();
                me.setHotBackspace(false);
            } else {
                me.setHotBackspace(true);
            }
        }

        //27 is escape
        if (key === 27) {
            me.clearNewTagInput();
            me.clearErrorMessage();
        }

        if (key !== 8) {
            me.setHotBackspace(false);
        }
        me.fixHeight();
        return false;
    };
};

TagEditor.prototype.decorate = function (element) {
    this._element = element;
    this._hidden_tags_input = element.find('input[name="tags"]');//this one is hidden
    this._tags_container = element.find('ul.tags');
    this._error_alert = $('.tag-editor-error-alert > span');

    var me = this;
    this._tags_container.children().each(function (idx, elem) {
        var tag = new Tag();
        tag.setDeletable(true);
        tag.setLinkable(false);
        tag.decorate($(elem));
        tag.setDeleteHandler(me.getTagDeleteHandler(tag));
    });

    var visible_tags_input = element.find('.js-new-tags-input');
    this._visible_tags_input = visible_tags_input;
    this.saveHeight();

    var tagsAc = new AutoCompleter({
        url: askbot.urls.get_tag_list,
        onItemSelect: function (item) {
            if (me.isSelectedTagName(item.value) === false) {
                me.completeTagInput();
            } else {
                me.clearNewTagInput();
            }
        },
        minChars: 1,
        useCache: true,
        matchInside: true,
        maxCacheLength: 100,
        delay: 10
    });
    tagsAc.decorate(visible_tags_input);
    this._autocompleter = tagsAc;
    visible_tags_input.keyup(this.getTagInputKeyHandler());

    element.click(function () {
        visible_tags_input.focus();
        return false;
    });
};
