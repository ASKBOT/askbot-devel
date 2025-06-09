/* global askbot, cleanTag, gettext, inherits, SelectBoxItem */
/**
 * @constructor
 * Category is a select box item
 * that has CategoryEditControls
 */
var Category = function () {
    SelectBoxItem.call(this);
    this._state = 'display';
    this._isAdminTagsRoot = false;
    this._settings = JSON.parse(askbot.settings.tag_editor);
};
inherits(Category, SelectBoxItem);

Category.prototype.getData = function () {
    var data = SelectBoxItem.prototype.getData.call(this);
    data.isAdminTagsRoot = this._isAdminTagsRoot;
    return data;
};

Category.prototype.setCategoryTree = function (tree) {
    this._tree = tree;
};

Category.prototype.getCategoryTree = function () {
    return this._tree;
};

Category.prototype.getName = function () {
    return this.getContent().getContent();
};

Category.prototype.getPath = function () {
    return this._tree.getPathToItem(this);
};

Category.prototype.setState = function (state) {
    if (this._isAdminTagsRoot && state !== 'display') return; // admin root cannot be edited or deleted
    this._state = state;
    if (!this._element) {
        return;
    }
    this._input_box.val('');
    if (state === 'display') {
        this.showContent();
        this.hideEditor();
        this.hideEditControls();
    } else if (state === 'editable') {
        this._tree._state = 'editable';//a hack
        this.showContent();
        this.hideEditor();
        this.showEditControls();
    } else if (state === 'editing') {
        this._prev_tree_state = this._tree.getState();
        this._tree._state = 'editing';//a hack
        this._input_box.val(this.getName());
        this.hideContent();
        this.showEditor();
        this.hideEditControls();
    }
};

Category.prototype.hideEditControls = function () {
    this._delete_button.hide();
    this._edit_button.hide();
    this._element.unbind('mouseenter mouseleave');
};

Category.prototype.showEditControls = function () {
    var del = this._delete_button;
    var edit = this._edit_button;
    this._element.hover(
        function () {
            del.show();
            edit.show();
        },
        function () {
            del.hide();
            edit.hide();
        }
    );
};

Category.prototype.showEditControlsNow = function () {
    this._delete_button.show();
    this._edit_button.show();
};

Category.prototype.hideContent = function () {
    this.getContent().getElement().hide();
};

Category.prototype.showContent = function () {
    this.getContent().getElement().show();
};

Category.prototype.showEditor = function () {
    this._input_box.show();
    this._input_box.focus();
    this._save_button.show();
    this._cancel_button.show();
};

Category.prototype.hideEditor = function () {
    this._input_box.hide();
    this._save_button.hide();
    this._cancel_button.hide();
};

Category.prototype.getInput = function () {
    return this._input_box.val();
};

Category.prototype.getDeleteHandler = function () {
    var me = this;
    return function () {
        if (confirm(gettext('Delete category?'))) {
            var tree = me.getCategoryTree();
            $.ajax({
                type: 'POST',
                dataType: 'json',
                data: JSON.stringify({
                    tag_name: me.getName(),
                    path: me.getPath()
                }),
                cache: false,
                url: askbot.urls.delete_tag,
                success: function (data) {
                    if (data.success) {
                        //rebuild category tree based on data
                        tree.setData(data.tree_data);
                        //re-open current branch
                        tree.selectPath(tree.getCurrentPath());
                        tree.setState('editable');
                    } else {
                        alert(data.message);
                    }
                }
            });
        }
        return false;
    };
};

Category.prototype.getSaveHandler = function () {
    var me = this;
    var settings = this._settings;
    //here we need old value and new value
    return function () {
        var to_name = me.getInput();
        try {
            to_name = cleanTag(to_name, settings);
            var data = {
                from_name: me.getOriginalName(),
                to_name: to_name,
                path: me.getPath()
            };
            $.ajax({
                type: 'POST',
                dataType: 'json',
                data: JSON.stringify(data),
                cache: false,
                url: askbot.urls.rename_tag,
                success: function (data) {
                    if (data.success) {
                        me.setName(to_name);
                        me.setState('editable');
                        me.showEditControlsNow();
                    } else {
                        alert(data.message);
                    }
                }
            });
        } catch (error) {
            alert(error);
        }
        return false;
    };
};

Category.prototype.addControls = function () {
    var input_box = this.makeElement('input');
    input_box.attr('type', 'text');
    this._input_box = input_box;
    this._element.append(input_box);

    var buttonsBox = this.makeElement('span');
    buttonsBox.addClass('js-category-btns');
    this._element.append(buttonsBox);

    var save_button = this.makeButton(
        gettext('save'),
        this.getSaveHandler()
    );
    this._save_button = save_button;
    buttonsBox.append(save_button);

    var me = this;
    var cancel_button = this.makeButton(
        'x',
        function () {
            me.setState('editable');
            me.showEditControlsNow();
            return false;
        }
    );
    this._cancel_button = cancel_button;
    buttonsBox.append(cancel_button);

    var edit_button = this.makeButton(
        gettext('edit'),
        function () {
            //todo: I would like to make only one at a time editable
            //var tree = me.getCategoryTree();
            //tree.closeAllEditors();
            //tree.setState('editable');
            //calc path, then select it
            var tree = me.getCategoryTree();
            tree.selectPath(me.getPath());
            me.setState('editing');
            return false;
        }
    );
    this._edit_button = edit_button;
    buttonsBox.append(edit_button);

    var delete_button = this.makeButton(
        'x', this.getDeleteHandler()
    );
    this._delete_button = delete_button;
    buttonsBox.append(delete_button);
};

Category.prototype.getOriginalName = function () {
    return this._original_name;
};

Category.prototype.createDom = function () {
    Category.superClass_.createDom.call(this);
    this.addControls();
    var name = this.getName();
    if (name === askbot.settings.adminTagsCategoryRoot) { // special name, not editable
        this.setName(gettext('Admin Tags')); // display value for the admin tags selector
        this._isAdminTagsRoot = true;
    }
    this.setState('display');
    this._original_name = name;
};

Category.prototype.decorate = function (element) {
    Category.superClass_.decorate.call(this, element);
    this.addControls();
    this.setState('display');
    this._original_name = this.getName();
};
