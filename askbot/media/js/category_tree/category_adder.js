/* global askbot, cleanTag, gettext, inherits, setupButtonEventHandlers, WrappedElement */
var CategoryAdder = function () {
    WrappedElement.call(this);
    this._state = 'disabled';//waitedit
    this._tree = undefined;//category tree
    this._settings = JSON.parse(askbot.settings.tag_editor);
};
inherits(CategoryAdder, WrappedElement);

CategoryAdder.prototype.setCategoryTree = function (tree) {
    this._tree = tree;
};

CategoryAdder.prototype.setLevel = function (level) {
    this._level = level;
};

CategoryAdder.prototype.setState = function (state) {
    this._state = state;
    if (!this._element) {
        return;
    }
    if (state === 'waiting') {
        this._element.show();
        this._input.val('');
        this._input.hide();
        this._save_button.hide();
        this._cancel_button.hide();
        this._trigger.show();
    } else if (state === 'editable') {
        this._element.show();
        this._input.show();
        this._input.val('');
        this._input.focus();
        this._save_button.show();
        this._cancel_button.show();
        this._trigger.hide();
    } else if (state === 'disabled') {
        this.setState('waiting');//a little hack
        this._state = 'disabled';
        this._element.hide();
    }
};

CategoryAdder.prototype.cleanCategoryName = function (name) {
    name = $.trim(name);
    if (name === '') {
        throw gettext('category name cannot be empty');
    }
    //if ( this._tree.hasCategory(name) ) {
        //throw interpolate(
        //throw gettext('this category already exists');
        //    [this._tree.getDisplayPathByName(name)]
        //)
    //}
    return cleanTag(name, this._settings);
};

CategoryAdder.prototype.getPath = function () {
    var path = this._tree.getCurrentPath();
    if (path.length > this._level + 1) {
        return path.slice(0, this._level + 1);
    } else {
        return path;
    }
};

CategoryAdder.prototype.getSelectBox = function () {
    return this._tree.getSelectBox(this._level);
};

CategoryAdder.prototype.startAdding = function () {
    var name;
    try {
        name = this._input.val();
        name = this.cleanCategoryName(name);
    } catch (error) {
        alert(error);
        return;
    }

    //don't add dupes to the same level
    var existing_names = this.getSelectBox().getNames();
    if ($.inArray(name, existing_names) !== -1) {
        alert(gettext('already exists at the current level!'));
        return;
    }

    var me = this;
    var tree = this._tree;
    var adder_path = this.getPath();

    $.ajax({url: askbot.urls.add_tag_category, type: 'POST',
        dataType: 'json',
        data: JSON.stringify({
            path: adder_path,
            new_category_name: name
        }),
        cache: false,
        success: function (data) {
            if (data.success) {
                //rebuild category tree based on data
                tree.setData(data.tree_data);
                tree.selectPath(data.new_path);
                tree.setState('editable');
                me.setState('waiting');
            } else {
                alert(data.message);
            }
        }
    });
};

CategoryAdder.prototype.createDom = function () {
    this._element = this.makeElement('li');
    //add open adder link
    var trigger = this.makeElement('a');
    this._trigger = trigger;
    trigger.html(gettext('add category'));
    this._element.append(trigger);

    //add input box
    var input = this.makeElement('input');
    this._input = input;
    input.addClass('add-category');
    input.attr({
        'name': 'add_category',
        'type': 'text'
    });
    this._element.append(input);

    var buttonsBox = this.makeElement('span');
    buttonsBox.addClass('js-category-btns');
    this._element.append(buttonsBox);

    //add save category button
    var save_button = this.makeElement('button');
    this._save_button = save_button;
    save_button.html(gettext('save'));
    buttonsBox.append(save_button);

    var cancel_button = this.makeElement('button');
    this._cancel_button = cancel_button;
    cancel_button.html('x');
    buttonsBox.append(cancel_button);

    this.setState(this._state);

    var me = this;
    setupButtonEventHandlers(
        trigger,
        function () { me.setState('editable'); }
    );
    setupButtonEventHandlers(
        save_button,
        function () {
            me.startAdding();
            return false;//prevent form submit
        }
    );
    setupButtonEventHandlers(
        cancel_button,
        function () {
            me.setState('waiting');
            return false;//prevent submit
        }
    );
    //create input box, button and the "activate" link
};
