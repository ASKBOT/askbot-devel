/* global askbot, inherits, Category, CategoryEditorToggle, CategorySelectBox, Widget */
var CategorySelector = function () {
    Widget.call(this);
    this._data = null;
    this._select_handler = function () {};//dummy default
    this._current_path = [0];//path points to selected item in tree
};
inherits(CategorySelector, Widget);

/**
 * propagates state to the individual selectors
 */
CategorySelector.prototype.setState = function (state) {
    this._state = state;
    if (state === 'editing') {
        return;//do not propagate this state
    }
    $.each(this._selectors, function (idx, selector) {
        selector.setState(state);
    });
};

CategorySelector.prototype.getPathToItem = function (item) {
    function findPathToItemInTree(tree, item) {
        for (var i = 0; i < tree.length; i++) {
            var node = tree[i];
            if (node[2] === item) {
                return [i];
            }
            var path = findPathToItemInTree(node[1], item);
            if (path.length > 0) {
                path.unshift(i);
                return path;
            }
        }
        return [];
    }
    return findPathToItemInTree(this._data, item);
};

CategorySelector.prototype.applyToDataItems = function (func) {
    function applyToDataItems(tree) {
        $.each(tree, function (idx, item) {
            func(item);
            applyToDataItems(item[1]);
        });
    }
    if (this._data) {
        applyToDataItems(this._data);
    }
};

CategorySelector.prototype.filterAdminTags = function (data) {
    var enabled = askbot.data['adminTagsEnabled'];
    var isMod = askbot.data['userIsAdminOrMod'];
    if (enabled && isMod) {
        return data;
    }

    function selectPublicTags(item) {
        if (item[0] === 'ADMIN TAGS') return false;
        item[1] = item[1].filter(selectPublicTags);
        return true;
    }

    return data.filter(selectPublicTags);
};

CategorySelector.prototype.setData = function (data) {
    this._data = this.filterAdminTags(data);
    var tree = this;
    function attachCategory(item) {
        var name = item[0];
        var cat = new Category();
        cat.setName(name);
        cat.setCategoryTree(tree);
        item[2] = cat;
    }
    this.applyToDataItems(attachCategory);
};

/**
 * clears contents of selector boxes starting from
 * the given level, in range 0..2
 */
CategorySelector.prototype.clearCategoryLevels = function (level) {
    for (var i = level; i < 3; i++) {
        this._selectors[i].detachAllItems();
    }
};

CategorySelector.prototype.getLeafItems = function (selection_path) {
    //traverse the tree down to items pointed to by the path
    var data = this._data[0];
    for (var i = 1; i < selection_path.length; i++) {
        data = data[1][selection_path[i]];
    }
    return data[1];
};

/**
 * called when a sub-level needs to open
 */
CategorySelector.prototype.populateCategoryLevel = function (source_path) {
    var level = source_path.length - 1;
    if (level >= 3) {
        return;
    }
    //clear all items downstream
    this.clearCategoryLevels(level);

    //populate current selector
    var selector = this._selectors[level];
    var items  = this.getLeafItems(source_path);

    $.each(items, function (idx, item) {
        var category_subtree = item[1];
        var category_object = item[2];
        selector.addItemObject(category_object);
        if (category_subtree.length > 0) {
            category_object.addCssClass('js-subtree');
        }
    });

    this.setState(this._state);//update state

    selector.clearSelection();
};

CategorySelector.prototype.selectPath = function (path) {
    var i;
    for (i = 1; i <= path.length; i++) {
        this.populateCategoryLevel(path.slice(0, i));
    }
    for (i = 1; i < path.length; i++) {
        var sel_box = this._selectors[i - 1];
        var category = sel_box.getItemByIndex(path[i]);
        sel_box.selectItem(category);
    }
};

CategorySelector.prototype.getSelectBox = function (level) {
    return this._selectors[level];
};

CategorySelector.prototype.getSelectedPath = function (selected_level) {
    var path = [0];//root, todo: better use names for path???
    /*
     * upper limit capped by current clicked level
     * we ignore all selection above the current level
     */
    for (var i = 0; i < selected_level + 1; i++) {
        var selector = this._selectors[i];
        var item = selector.getSelectedItem();
        if (item) {
            path.push(selector.getItemIndex(item));
        } else {
            return path;
        }
    }
    return path;
};

/** getter and setter are not symmetric */
CategorySelector.prototype.setSelectHandler = function (handler) {
    this._select_handler = handler;
};

CategorySelector.prototype.getSelectHandlerInternal = function () {
    return this._select_handler;
};

CategorySelector.prototype.setCurrentPath = function (path) {
    this._current_path = path;
    return true;
};

CategorySelector.prototype.getCurrentPath = function () {
    return this._current_path;
};

CategorySelector.prototype.getEditorToggle = function () {
    return this._editor_toggle;
};

/*CategorySelector.prototype.closeAllEditors = function () {
    $.each(this._selectors, function (idx, sel) {
        sel._category_adder.setState('wait');
        $.each(sel._items, function (idx2, item) {
            item.setState('editable');
        });
    });
};*/

CategorySelector.prototype.getSelectHandler = function (level) {
    var me = this;
    return function (itemData) {
        if (me.getState() === 'editing') {
            return;//don't navigate when editing
        }
        //1) run the assigned select handler
        var tagName = itemData.title;
        if (me.getState() === 'select') {
            /* this one will actually select the tag
             * maybe a bit too implicit
             */
            if (!itemData.isAdminTagsRoot) {
                me.getSelectHandlerInternal()(tagName);
            }
        }
        //2) if appropriate, populate the higher level
        if (level < 2) {
            var currentPath = me.getSelectedPath(level);
            me.setCurrentPath(currentPath);
            me.populateCategoryLevel(currentPath);
        }
    };
};

CategorySelector.prototype.decorate = function (element) {
    this._element = element;
    this._selectors = [];

    var selector0 = new CategorySelectBox();
    selector0.setLevel(0);
    selector0.setCategoryTree(this);
    selector0.decorate(element.find('.js-cat-col-0'));
    selector0.setSelectHandler(this.getSelectHandler(0));
    this._selectors.push(selector0);

    var selector1 = new CategorySelectBox();
    selector1.setLevel(1);
    selector1.setCategoryTree(this);
    selector1.decorate(element.find('.js-cat-col-1'));
    selector1.setSelectHandler(this.getSelectHandler(1));
    this._selectors.push(selector1);

    var selector2 = new CategorySelectBox();
    selector2.setLevel(2);
    selector2.setCategoryTree(this);
    selector2.decorate(element.find('.js-cat-col-2'));
    selector2.setSelectHandler(this.getSelectHandler(2));
    this._selectors.push(selector2);

    if (askbot.data.userIsAdminOrMod) {
        var editor_toggle = new CategoryEditorToggle();
        editor_toggle.setCategorySelector(this);
        var toggle_element = $('.js-category-editor-toggle');
        toggle_element.show();
        editor_toggle.decorate(toggle_element);
        this._editor_toggle = editor_toggle;
    }

    this.populateCategoryLevel([0]);
};
