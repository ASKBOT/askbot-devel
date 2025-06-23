/* global askbot, gettext, getUniqueWords, inherits, WrappedElement, setupButtonEventHandlers,
 showMessage, Tag */
/*
 * @constructor
 * loads html for the category selector from
 * the server via ajax and activates the
 * CategorySelector on the loaded HTML
 */
var CategorySelectorLoader = function () {
    WrappedElement.call(this);
    this._is_loaded = false;
};
inherits(CategorySelectorLoader, WrappedElement);

CategorySelectorLoader.prototype.setCategorySelector = function (sel) {
    this._category_selector = sel;
};

CategorySelectorLoader.prototype.setLoaded = function (is_loaded) {
    this._is_loaded = is_loaded;
};

CategorySelectorLoader.prototype.isLoaded = function () {
    return this._is_loaded;
};

CategorySelectorLoader.prototype.setEditor = function (editor) {
    this._editor = editor;
};

CategorySelectorLoader.prototype.closeEditor = function () {
    this._editor.hide();
    this._editor_buttons.hide();
    this._display_tags_container.show();
    this._question_body.show();
    this._question_controls.show();
};

CategorySelectorLoader.prototype.openEditor = function () {
    this._editor.show();
    this._editor_buttons.show();
    this._display_tags_container.hide();
    this._question_body.hide();
    this._question_controls.hide();
    var sel = this._category_selector;
    sel.setState('select');
    sel.getEditorToggle().setState('off-state');
};

CategorySelectorLoader.prototype.addEditorButtons = function () {
    this._editor.after(this._editor_buttons);
};

CategorySelectorLoader.prototype.getOnLoadHandler = function () {
    var me = this;
    return function (html) {
        me.setLoaded(true);

        //append loaded html to dom
        var editor = $('<div>' + html + '</div>');
        me.setEditor(editor);
        $('.js-question-tags').after(editor);

        var selector = askbot.functions.initCategoryTree();
        me.setCategorySelector(selector);

        me.addEditorButtons();
        me.openEditor();
        //add the save button
    };
};

CategorySelectorLoader.prototype.startLoadingHTML = function (on_load) {
    var me = this;
    $.ajax({url: askbot.urls.get_html_template, type: 'GET',
        dataType: 'json',
        data: { template_name: 'widgets/tag_category_selector.html' },
        cache: true,
        success: function (data) {
            if (data.success) {
                on_load(data.html);
            } else {
                showMessage(me.getElement(), data.message);
            }
        }
    });
};

CategorySelectorLoader.prototype.getRetagHandler = function () {
    var me = this;
    return function () {
        if (me.isLoaded() === false) {
            me.startLoadingHTML(me.getOnLoadHandler());
        } else {
            me.openEditor();
        }
        return false;
    };
};

CategorySelectorLoader.prototype.drawNewTags = function (new_tags) {
    var container = this._display_tags_container;

    container.children().each(function(_, item) {
      var elem = $(item)
      if (!elem.hasClass('js-retag-btn-ctr')) {
        elem.remove();
      }
    });

    if (new_tags === '') {
        return;
    }

    new_tags = new_tags.split(/\s+/);
    var me = this;
    var retagBtnCtr = container.find('.js-retag-btn-ctr');
    $.each(new_tags, function (index, name) {
        var li = me.makeElement('li');
        retagBtnCtr.before(li);
        var tag = new Tag();
        tag.setName(name);
        li.append(tag.getElement());
    });
};

CategorySelectorLoader.prototype.getSaveHandler = function () {
    var me = this;
    return function () {
        var tagInput = $('input[name="tags"]');
        $.ajax({url: askbot.urls.retag, type: 'POST',
            dataType: 'json',
            data: { tags: getUniqueWords(tagInput.val()).join(' ') },
            success: function (json) {
                if (json.success) {
                    var new_tags = getUniqueWords(json.new_tags);
                    me.closeEditor();
                    me.drawNewTags(new_tags.join(' '));
                } else {
                    me.closeEditor();
                    showMessage(me.getElement(), json.message);
                }
            },
            error: function () {
                showMessage(me.getElement(), 'sorry, something is not right here');
                //cancelRetag();
            }
        });
        return false;
    };
};

CategorySelectorLoader.prototype.getCancelHandler = function () {
    var me = this;
    return function () {
        me.closeEditor();
    };
};

CategorySelectorLoader.prototype.decorate = function (element) {
    this._element = element;
    this._display_tags_container = $('.js-question-tags');
    this._question_body = $('.question .post-body');
    this._question_controls = $('.js-question-controls');

    this._editor_buttons = this.makeElement('div');
    this._done_button = this.makeElement('button');
    this._done_button.addClass('btn js-save-category-btn');
    this._done_button.html(gettext('save tags'));
    this._editor_buttons.append(this._done_button);

    this._cancel_button = this.makeElement('button');
    this._cancel_button.addClass('btn btn-muted');
    this._cancel_button.html(gettext('cancel'));
    this._editor_buttons.append(this._cancel_button);
    this._editor_buttons.addClass('retagger-buttons');

    //done button
    setupButtonEventHandlers(
        this._done_button,
        this.getSaveHandler()
    );
    //cancel button
    setupButtonEventHandlers(
        this._cancel_button,
        this.getCancelHandler()
    );

    //retag button
    setupButtonEventHandlers(
        element,
        this.getRetagHandler()
    );
};
