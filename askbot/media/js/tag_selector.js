var TagDetailBox = function (boxType) {
    WrappedElement.call(this);
    this.boxType = boxType;
    this._is_blank = true;
    this._tags = [];
    this.wildcard = undefined;
};
inherits(TagDetailBox, WrappedElement);

TagDetailBox.prototype.createDom = function () {
    this._element = this.makeElement('div');
    this._element.addClass('wildcard-tags');
    this._headline = this.makeElement('p');
    this._headline.html(gettext('Tag "<span></span>" matches:'));
    this._element.append(this._headline);
    this._tag_list_element = this.makeElement('ul');
    this._tag_list_element.addClass('tags');
    this._element.append(this._tag_list_element);
    this._footer = this.makeElement('p');
    this._footer.css('clear', 'left');
    this._element.append(this._footer);
    this._element.hide();
};

TagDetailBox.prototype.belongsTo = function (wildcard) {
    return (this.wildcard === wildcard);
};

TagDetailBox.prototype.isBlank = function () {
    return this._is_blank;
};

TagDetailBox.prototype.clear = function () {
    if (this.isBlank()) {
        return;
    }
    this._is_blank = true;
    this.getElement().hide();
    this.wildcard = null;
    $.each(this._tags, function (idx, item) {
        item.dispose();
    });
    this._tags = [];
    this._tag_list_element.empty();
};

TagDetailBox.prototype.addTag = function (tag) {
    this._tags.push(tag);
    var li = this.makeElement('li');
    li.append(tag.getElement());
    this._tag_list_element.append(li);
    this._tag_list_element.addClass('js-has-tags');
};

TagDetailBox.prototype.loadTags = function (wildcard, callback) {
    var me = this;
    $.ajax({
        type: 'GET',
        dataType: 'json',
        cache: false,
        url: askbot.urls.get_tags_by_wildcard,
        data: { wildcard: wildcard },
        success: callback,
        failure: function () { me._loading = false; }
    });
};

TagDetailBox.prototype.renderFor = function (wildcard) {
    var me = this;
    if (this._loading === true) {
        return;
    }
    this._loading = true;
    this.loadTags(
        wildcard,
        function (data, text_status, xhr) {
            me._tag_names = data.tag_names;
            if (data.tag_count > 0) {
                var wildcard_display = wildcard.replace(/\*$/, '&#10045;');
                me._headline.find('span').html(wildcard_display);
                $.each(me._tag_names, function (idx, name) {
                    var tag = new Tag();
                    tag.setName(name);
                    tag.setUrlParams(name);
                    //tag.setLinkable(false);
                    me.addTag(tag);
                });
                me._is_blank = false;
                me.wildcard = wildcard;
                var tag_count = data.tag_count;
                if (tag_count > 20) {
                    var fmts = gettext('and %s more, not shown...');
                    var footer_text = interpolate(fmts, [tag_count - 20]);
                    me._footer.html(footer_text);
                    me._footer.show();
                } else {
                    me._footer.hide();
                }
                me._element.show();
            } else {
                me.clear();
            }
            me._loading = false;
        }
    );
};

function pickedTags() {

    var interestingTags = {};
    var ignoredTags = {};
    var subscribedTags = {};
    var interestingTagDetailBox = new TagDetailBox('interesting');
    var ignoredTagDetailBox = new TagDetailBox('ignored');
    var subscribedTagDetailBox = new TagDetailBox('subscribed');

    var sendAjax = function (tagnames, reason, action, callback) {
        var url = '';
        if (action === 'add') {
            if (reason === 'good') {
                url = askbot.urls.mark_interesting_tag;
            } else if (reason === 'bad') {
                url = askbot.urls.mark_ignored_tag;
            } else {
                url = askbot.urls.mark_subscribed_tag;
            }
        } else {
            url = askbot.urls.unmark_tag;
        }

        var data = JSON.stringify({
            tagnames: tagnames,
            reason: reason,
            user: askbot.data.viewUserId
        });
        var call_settings = {
            type:'POST',
            url:url,
            data: data,
            dataType: 'json'
        };
        if (callback !== false) {
            call_settings.success = callback;
        }
        $.ajax(call_settings);
    };

    var unpickTag = function (from_target, tagname, reason, send_ajax) {
        //send ajax request to delete tag
        var deleteTagLocally = function () {
            var tag = from_target[tagname];
            var li = tag.parent();
            var ul = li.parent();
            from_target[tagname].remove();
            if (li.prop('tagName') === 'LI') {
                li.remove();
            }
            if (ul.find('li').length === 0) {
              ul.removeClass('js-has-tags');
            }
            delete from_target[tagname];
        };
        if (send_ajax) {
            //unpick tag
            sendAjax(
                [tagname],
                reason,
                'remove',
                function (reData) {
                    if (reData.success) {
                        deleteTagLocally();
                        if ($('body').hasClass('main-page')) {
                            askbot.controllers.fullTextSearch.refresh();
                        }
                    } else if (reData.message) {
                        var tag = from_target[tagname];
                        showMessage(tag, reData.message, 'after');
                    }
                }
            );
        } else {
            deleteTagLocally();
        }
    };

    var getTagList = function (reason) {
        var base_selector = '.js-marked-tags';
        var extra_selector = '';
        if (reason === 'good') {
            extra_selector = '.js-interesting-tags';
        } else if (reason === 'bad') {
            extra_selector = '.js-ignored-tags';
        } else if (reason === 'subscribed') {
            extra_selector = '.subscribed';
        }
        return $(base_selector + extra_selector);
    };

    var getWildcardTagDetailBox = function (reason) {
        if (reason === 'good') {
            return interestingTagDetailBox;
        } else if (reason === 'bad') {
            return ignoredTagDetailBox;
        } else if (reason === 'subscribed') {
            return subscribedTagDetailBox;
        }
    };

    var handleWildcardTagClick = function (tag_name, reason) {
        var detail_box = getWildcardTagDetailBox(reason);
        var tag_box = getTagList(reason);
        if (detail_box.isBlank()) {
            detail_box.renderFor(tag_name);
        } else if (detail_box.belongsTo(tag_name)) {
            detail_box.clear();//toggle off
        } else {
            detail_box.clear();//redraw with new data
            detail_box.renderFor(tag_name);
        }
        if (!detail_box.inDocument()) {
            tag_box.after(detail_box.getElement());
            detail_box.enterDocument();
        }
    };

    var renderNewTags = function (
                        clean_tag_names,
                        reason,
                        to_target,
                        to_tag_container
                    ) {
        $.each(clean_tag_names, function (idx, tag_name) {
            var tag = new Tag();
            var delete_handler = function () {};
            tag.setName(tag_name);
            tag.setDeletable(true);

            if (/\*$/.test(tag_name)) {
                tag.setLinkable(false);
                var detail_box = getWildcardTagDetailBox(reason);
                tag.setHandler(function () {
                    handleWildcardTagClick(tag_name, reason);
                    if (detail_box.belongsTo(tag_name)) {
                        detail_box.clear();
                    }
                    return false;
                });
                delete_handler = function () {
                    unpickTag(to_target, tag_name, reason, true);
                    if (detail_box.belongsTo(tag_name)) {
                        detail_box.clear();
                    }
                };
            } else {
                delete_handler = function () {
                    unpickTag(to_target, tag_name, reason, true);
                };
            }

            tag.setDeleteHandler(delete_handler);
            var tag_element = tag.getElement();
            var li = $('<li></li>');//assumption that we have a list
            li.append(tag_element);
            to_tag_container.append(li);
            to_tag_container.addClass('js-has-tags');
            to_target[tag_name] = tag_element;
        });
    };

    var handlePickedTag = function (reason) {
        var to_target = interestingTags;
        var from_target = ignoredTags;
        var to_tag_container;
        var input_sel = '';
        if (reason === 'bad') {
            input_sel = '#js-ignored-tag-input';
            to_target = ignoredTags;
            from_target = interestingTags;
            to_tag_container = $('div .js-ignored-tags');
        } else if (reason === 'good') {
            input_sel = '#js-interesting-tag-input';
            to_tag_container = $('div .js-interesting-tags');
        } else if (reason === 'subscribed') {
            input_sel = '#js-subscribed-tag-input';
            to_target = subscribedTags;
            to_tag_container = $('div .js-subscribed-tags');
        } else {
            return;
        }

        var tags_input = $.trim($(input_sel).val());
        if (tags_input === '') {
            return;
        }
        var tagnames = getUniqueWords(tags_input);

        if (reason !== 'subscribed') {//for "subscribed" we do not remove
            $.each(tagnames, function (idx, tagname) {
                if (tagname in from_target) {
                    unpickTag(from_target, tagname, reason, false);
                }
            });
        }

        var tagSettings = JSON.parse(askbot.settings.tag_editor);
        var clean_tagnames = [];
        $.each(tagnames, function (idx, tagname) {
            if (!(tagname in to_target)) {
                try {
                    cleanTag(tagname, tagSettings);
                    clean_tagnames.push(tagname);
                } catch (e) {
                    alert(e);
                }
            }
        });

        if (clean_tagnames.length > 0) {
            //send ajax request to pick this tag
            sendAjax(
                clean_tagnames,
                reason,
                'add',
                function (reData) {
                    if (reData.success) {
                        renderNewTags(
                            clean_tagnames,
                            reason,
                            to_target,
                            to_tag_container
                        );
                        $(input_sel).val('');
                        askbot.controllers.fullTextSearch.refresh();
                    } else if (reData.message) {
                        showMessage(to_tag_container, reData.message, 'after');
                    }
                }
            );
        }
    };

    var collectPickedTags = function (section) {
        var reason = '';
        var tag_store;
        if (section === 'js-interesting-tags') {
            reason = 'good';
            tag_store = interestingTags;
        } else if (section === 'js-ignored-tags') {
            reason = 'bad';
            tag_store = ignoredTags;
        } else if (section === 'js-subscribed-tags') {
            reason = 'subscribed';
            tag_store = subscribedTags;
        } else {
            return;
        }
        $('.' + section + '.js-marked-tags .js-tag').each(
            function (i, item) {
                var tag = new Tag();
                tag.decorate($(item));
                tag.setDeleteHandler(function () {
                    unpickTag(
                        tag_store,
                        tag.getName(),
                        reason,
                        true
                    );
                });
                if (tag.isWildcard()) {
                    tag.setHandler(function () {
                        handleWildcardTagClick(tag.getName(), reason);
                        return false;
                    });
                }
                tag_store[tag.getName()] = $(item);
            }
        );
    };

    var setupTagFilterControl = function (control_type) {
        var radioButtons = $('#js-' + control_type + '-tag-filter-control input');
        radioButtons.unbind('click');
        radioButtons.click(function () {
            var clickedBtn = $(this);
            $.ajax({
                type: 'POST',
                dataType: 'json',
                cache: false,
                url: askbot.urls.set_tag_filter_strategy,
                data: {
                    filter_type: control_type,
                    filter_value: clickedBtn.val()
                },
                success: function () {
                    clickedBtn.prop('checked', true).trigger('change'); // trigger other listeners on the radio
                    askbot.controllers.fullTextSearch.refresh();
                }
            });
            return false;
        });
    };

    var getResultCallback = function (reason) {
        return function () {
            handlePickedTag(reason);
        };
    };

    return {
        init: function () {
            collectPickedTags('js-interesting-tags');
            collectPickedTags('js-ignored-tags');
            collectPickedTags('js-subscribed-tags');
            setupTagFilterControl('display');
            setupTagFilterControl('email');
            var ac = new AutoCompleter({
                url: askbot.urls.get_tag_list + '?include_admin_tags=true',
                minChars: 1,
                useCache: true,
                matchInside: true,
                maxCacheLength: 100,
                delay: 10
            });


            var interestingTagAc = $.extend(true, {}, ac);
            interestingTagAc.decorate($('#js-interesting-tag-input'));
            interestingTagAc.setOption('onItemSelect', getResultCallback('good'));

            var ignoredTagAc = $.extend(true, {}, ac);
            ignoredTagAc.decorate($('#js-ignored-tag-input'));
            ignoredTagAc.setOption('onItemSelect', getResultCallback('bad'));

            var subscribedTagAc = $.extend(true, {}, ac);
            subscribedTagAc.decorate($('#js-subscribed-tag-input'));
            subscribedTagAc.setOption('onItemSelect', getResultCallback('subscribed'));

            $('#js-interesting-tag-add').click(getResultCallback('good'));
            $('#js-ignored-tag-add').click(getResultCallback('bad'));
            $('#js-subscribed-tag-add').click(getResultCallback('subscribed'));
        }
    };
}

$(document).ready(function () {
    pickedTags().init();
});
