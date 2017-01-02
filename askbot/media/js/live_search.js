var SearchDropMenu = function () {
    WrappedElement.call(this);
    this._data = undefined;
    this._selectedItemIndex = 0;
    this._askButtonEnabled = true;
};
inherits(SearchDropMenu, WrappedElement);

SearchDropMenu.prototype.setData = function (data) {
    this._data = data;
};

SearchDropMenu.prototype.setAskHandler = function (handler) {
    this._askHandler = handler;
};

SearchDropMenu.prototype.setSearchWidget = function (widget) {
    this._searchWidget = widget;
};

SearchDropMenu.prototype.getSearchWidget = function () {
    return this._searchWidget;
};

SearchDropMenu.prototype.setAskButtonEnabled = function (isEnabled) {
    this._askButtonEnabled = isEnabled;
};

/**
 * assumes that data is already set
 */
SearchDropMenu.prototype.render = function () {
    var list = this._resultsList;
    list.empty();
    var me = this;
    $.each(this._data, function (idx, item) {
        var listItem = me.makeElement('li');
        var link = me.makeElement('a');
        link.attr('href', item.url);
        link.html(item.title);
        listItem.append(link);
        list.append(listItem);
    });
    if (this._data.length === 0) {
        list.addClass('empty');
        this._element.addClass('empty');
    } else {
        list.removeClass('empty');
        this._element.removeClass('empty');
    }
};

SearchDropMenu.prototype.clearSelectedItem = function () {
    this._selectedItemIndex = 0;
    this._resultsList.find('li').removeClass('selected');
};

/**
 * @param {number} idx position of item starting from 1 for the topmost
 * Selects item inentified by position.
 * Scrolls the list to make top of the item visible.
 */
SearchDropMenu.prototype.selectItem = function (idx) {
    //idx is 1-based index
    this._selectedItemIndex = idx;
    var list = this._resultsList;
    list.find('li').removeClass('selected');
    var item = this.getItem(idx);
    if (item && idx > 0) {
        item.addClass('selected');
        var itemTopY = item.position().top;//relative to visible area
        var curScrollTop = list.scrollTop();

        /* if item is clipped on top, scroll down */
        if (itemTopY < 0) {
            list.scrollTop(curScrollTop + itemTopY);
            return;
        }

        var listHeight = list.outerHeight();
        /* pixels above the lower border of the list */
        var itemPeepHeight = listHeight - itemTopY;
        /* pixels below the lower border */
        var itemSinkHeight = item.outerHeight() - itemPeepHeight;
        if (itemSinkHeight > 0) {
            list.scrollTop(curScrollTop + itemSinkHeight);
        }
    }

};

SearchDropMenu.prototype.getItem = function (idx) {
    return $(this._resultsList.find('li')[idx - 1]);
};

SearchDropMenu.prototype.getItemCount = function () {
    return this._resultsList.find('li').length;
};

SearchDropMenu.prototype.getSelectedItemIndex = function () {
    return this._selectedItemIndex;
};

SearchDropMenu.prototype.navigateToItem = function (idx) {
    var item = this.getItem(idx);
    if (item) {
        window.location.href = item.find('a').attr('href');
    }
};

SearchDropMenu.prototype.makeKeyHandler = function () {
    var me = this;
    return function (e) {
        var keyCode = getKeyCode(e);
        if (keyCode === 27) {//escape
            me.hide();
            return false;
        }
        if (keyCode !== 38 && keyCode !== 40 && keyCode !== 13) {
            return;
        }
        var itemCount = me.getItemCount();
        if (itemCount > 0) {
            //count is 0 with no title matches, curItem is 0 when none is selected
            var curItem = me.getSelectedItemIndex();
            if (keyCode === 38) {//upArrow
                if (curItem > 0) {
                    curItem = curItem - 1;
                }
            } else if (keyCode === 40) {//downArrow
                if (curItem < itemCount) {
                    curItem = curItem + 1;
                }
            } else if (keyCode === 13) {//enter
                if (curItem === 0) {
                    return true;
                } else {
                    me.navigateToItem(curItem);
                    return false;
                }
            }

            var widget = me.getSearchWidget();
            if (curItem === 0) {
                //activate key handlers on input box
                widget.setFullTextSearchEnabled(true);
                me.clearSelectedItem();
            } else {
                //deactivate key handlers on input box
                widget.setFullTextSearchEnabled(false);
                me.selectItem(curItem);
            }
            return false;
        }
    };
};

/** todo: change this to state management as >1 thing happens */
SearchDropMenu.prototype.showWaitIcon = function () {
    if (this._askButtonEnabled) {
        this._waitIcon.show();
        this._footer.hide();
        this._element.addClass('empty');
    }
    this._element.addClass('waiting');
};

SearchDropMenu.prototype.hideWaitIcon = function () {
    if (this._askButtonEnabled) {
        this._waitIcon.hide();
        this._footer.show();
        this._element.removeClass('empty');
    }
    this._element.removeClass('waiting');
};

SearchDropMenu.prototype.hideHeader = function () {
    if (this._header) {
        this._header.hide();
    }
};

SearchDropMenu.prototype.showHeader = function () {
    if (this._header) {
        this._header.show();
    }
};

SearchDropMenu.prototype.createDom = function () {
    this._element = this.makeElement('div');
    this._element.addClass('search-drop-menu');
    this._element.hide();

    if (askbot.data.languageCode === 'ja') {
        var warning = this.makeElement('p');
        this._header = warning;
        warning.addClass('header');
        warning.html(gettext('To see search results, 2 or more characters may be required'));
        this._element.append(warning);
    }

    this._resultsList = this.makeElement('ul');
    this._element.append(this._resultsList);
    this._element.addClass('empty');

    var waitIcon = new WaitIcon();
    waitIcon.hide();
    this._element.append(waitIcon.getElement());
    this._waitIcon = waitIcon;

    //add ask button, @todo: make into separate class?
    var footer = this.makeElement('div');
    this._element.append(footer);
    this._footer = footer;

    if (this._askButtonEnabled) {
        footer.addClass('footer');
        var button = this.makeElement('button');
        button.addClass('submit btn btn-default');
        button.html(gettext('Ask Your Question'));
        footer.append(button);
        var handler = this._askHandler;
        setupButtonEventHandlers(button, handler);
    }

    $(document).keydown(this.makeKeyHandler());
};

SearchDropMenu.prototype.isOpen = function () {
    return this._element.is(':visible');
};

SearchDropMenu.prototype.show = function () {
    var searchBar = this.getSearchWidget();
    var searchBarHeight = searchBar.getWidgetHeight();
    var topOffset = searchBar.getElement().offset().top + searchBarHeight;
    this._element.show();//show so that size calcs work
    var footerHeight = this._footer.outerHeight();
    var windowHeight = $(window).height();
    this._resultsList.css(
        'max-height',
        windowHeight - topOffset - footerHeight - 40 //what is this number?
    );
};

SearchDropMenu.prototype.hide = function () {
    this._element.hide();
};

SearchDropMenu.prototype.reset = function () {
    this._data = undefined;
    this._resultsList.empty();
    this._selectedItemIndex = 0;
    this._element.hide();
};

var TagWarningBox = function () {
    WrappedElement.call(this);
    this._tags = [];
};
inherits(TagWarningBox, WrappedElement);

TagWarningBox.prototype.createDom = function () {
    this._element = this.makeElement('div');
    this._element.css('display', 'block');
    this._element.css('margin', '0 0 13px 2px');
    this._element.addClass('non-existing-tags');
    this._warning = this.makeElement('p');
    this._element.append(this._warning);
    this._tag_container = this.makeElement('ul');
    this._tag_container.addClass('tags');
    this._element.append(this._tag_container);
    this._element.append($('<div class="clearfix"></div>'));
    this._element.hide();
};

TagWarningBox.prototype.clear = function () {
    this._tags = [];
    if (this._tag_container) {
        this._tag_container.empty();
    }
    this._warning.hide();
    this._element.hide();
};

TagWarningBox.prototype.addTag = function (tag_name) {
    var tag = new Tag();
    tag.setName(tag_name);
    tag.setLinkable(false);
    tag.setDeletable(false);
    var elem = this.getElement();
    this._tag_container.append(tag.getElement());
    this._tag_container.css('display', 'block');
    this._tags.push(tag);
    elem.show();
};

TagWarningBox.prototype.showWarning = function () {
    this._warning.html(
        ngettext(
            'Sorry, this tag does not exist',
            'Sorry, these tags do not exist',
            this._tags.length
        )
    );
    this._warning.show();
};

/**
 * @constructor
 * tool tip to be shown on top of the search input
 */
var InputToolTip = function () {
    WrappedElement.call(this);
    this._promptText = gettext('Search or ask your question');
};
inherits(InputToolTip, WrappedElement);

InputToolTip.prototype.show = function () {
    this._element.removeClass('dimmed');
    this._element.show();
};

InputToolTip.prototype.hide = function () {
    this._element.removeClass('dimmed');
    this._element.hide();
};

InputToolTip.prototype.dim = function () {
    this._element.addClass('dimmed');
};

InputToolTip.prototype.setPromptText = function (text) {
    this._promptText = text;
};

InputToolTip.prototype.setClickHandler = function (handler) {
    this._clickHandler = handler;
};

InputToolTip.prototype.createDom = function () {
    var element = this.makeElement('div');
    this._element = element;
    element.addClass('input-tool-tip');
    element.html(this._promptText);
    this.decorate(element);
};

InputToolTip.prototype.decorate = function (element) {
    this._element = element;
    var handler = this._clickHandler;
    var me = this;
    element.click(function () {
        handler();
        me.dim();
        return false;
    });
    $(document).click(function () {
        if (element.css('display') === 'block') {
            element.removeClass('dimmed');
        }
    });
};


/**
 * @constructor
 * provides full text search functionality
 * which re-draws contents of the main page
 * in response to the search query
 */
var FullTextSearch = function () {
    WrappedElement.call(this);
    this._running = false;
    this._baseUrl = askbot.urls.questions;
    this._q_list_sel = 'question-list';//id of question listing div
    /** @todo: the questions/ needs translation... */
    this._searchUrl = '/scope:all/sort:activity-desc/page:1/';
    this._askButtonEnabled = true;
    this._fullTextSearchEnabled = true;
};
inherits(FullTextSearch, WrappedElement);

/**
 * @param {{boolean=}} optional, if given then function is setter
 * otherwise it is a getter
 * isRunning returns `true` when search is running
 */
FullTextSearch.prototype.isRunning = function (val) {
    if (val === undefined) {
        return this._running;
    } else {
        this._running = val;
    }
};

FullTextSearch.prototype.setAskButtonEnabled = function (isEnabled) {
    this._askButtonEnabled = isEnabled;
};

/**
 * @param {{string}} url for the page displaying search results
 */
FullTextSearch.prototype.setSearchUrl = function (url) {
    this._searchUrl = url;
};

FullTextSearch.prototype.getSearchUrl = function () {
    return this._searchUrl;
};

FullTextSearch.prototype.renderTagWarning = function (tag_list) {
    if (!tag_list) {
        return;
    }
    var tagWarningBox = this._tag_warning_box;
    tagWarningBox.clear();
    $.each(tag_list, function (idx, tag_name) {
        tagWarningBox.addTag(tag_name);
    });
    tagWarningBox.showWarning();
};

FullTextSearch.prototype.runTagSearch = function () {
    var search_tags = $('#ab-tag-search').val().split(/\s+/);
    if (search_tags.length === 0) {
        return;
    }
    var searchUrl = this.getSearchUrl();
    //add all tags to the url
    searchUrl = QSutils.add_search_tag(searchUrl, search_tags);
    var url = this._baseUrl + searchUrl;
    var me = this;
    $.ajax({
        url: url,
        dataType: 'json',
        success: function (data, text_status, xhr) {
            me.renderFullTextSearchResult(data, text_status, xhr);
            $('#ab-tag-search').val('');
        }
    });
    this.updateHistory(url);
};

FullTextSearch.prototype.updateHistory = function (url) {
    var context = { state:1, rand:Math.random() };
    History.pushState(context, 'Questions', url);
    setTimeout(function () {
            /* HACK: For some weird reson, sometimes
             * overrides the above pushState so we re-aplly it
             * This might be caused by some other JS plugin.
             * The delay of 10msec allows the other plugin to override the URL.
             */
            History.replaceState(context, 'Questions', url);
        },
        10
    );
};

FullTextSearch.prototype.activateTagSearchInput = function () {
    //the autocomplete is set up in tag_selector.js
    var button = $('#ab-tag-search-add');
    if (button.length === 0) {//may be absent
        return;
    }
    var me = this;
    var ac = new AutoCompleter({
        url: askbot.urls.get_tag_list,
        minChars: 1,
        useCache: true,
        matchInside: true,
        maxCacheLength: 100,
        maxItemsToShow: 20,
        onItemSelect: function () { me.runTagSearch(); },
        delay: 10
    });
    ac.decorate($('#ab-tag-search'));
    setupButtonEventHandlers(
        button,
        function () { me.runTagSearch(); }
    );
};

FullTextSearch.prototype.sendTitleSearchQuery = function (query_text) {
    this.isRunning(true);
    this._prevText = query_text;
    var data = {query_text: query_text};
    var me = this;
    $.ajax({
        url: askbot.urls.apiGetQuestions,
        data: data,
        dataType: 'json',
        success: function (data, text_status, xhr) {
            me.renderTitleSearchResult(data, text_status, xhr);
        },
        complete: function () {
            me.isRunning(false);
            me.evalTitleSearchQuery();
        },
        cache: false
    });
};


FullTextSearch.prototype.sendFullTextSearchQuery = function (query_text) {
    this.isRunning(true);
    var searchUrl = this.getSearchUrl();
    var prevText = this._prevText;
    if (!prevText && query_text && askbot.settings.showSortByRelevance) {
        /* If there was no query but there is some
         * query now - and we support relevance search
         * - then switch to it
         */
        searchUrl = QSutils.patch_query_string(
                        searchUrl, 'sort:relevance-desc'
                    );
    }
    this._prevText = this.updateQueryString(query_text);

    /* if something has changed, then reset the page no. */
    searchUrl = QSutils.patch_query_string(searchUrl, 'page:1');
    var url = this._baseUrl + searchUrl;
    var me = this;
    $.ajax({
        url: url,
        dataType: 'json',
        success: function (data, text_status, xhr) {
            me.renderFullTextSearchResult(data, text_status, xhr);
        },
        complete: function () {
            me.isRunning(false);
        },
        cache: false
    });
    this.updateHistory(url);
};

FullTextSearch.prototype.refresh = function () {
    this.sendFullTextSearchQuery();/* used for tag search, maybe not necessary */
};

FullTextSearch.prototype.getSearchQuery = function () {
    return $.trim(this._query.val());
};

FullTextSearch.prototype.getWidgetHeight = function () {
    return this._element.outerHeight();
};

/**
 * renders title search result in the dropdown under the search input
 */
FullTextSearch.prototype.renderTitleSearchResult = function (data) {
    var menu = this._dropMenu;
    menu.hideWaitIcon();
    if (data.length > 0) {
        menu.hideHeader();
    }
    menu.setData(data);
    menu.render();
    menu.show();
};

FullTextSearch.prototype.renderFullTextSearchResult = function (data) {
    if (data.questions.length === 0) {
        return;
    }

    $('#pager').toggle(data.paginator !== '').html(data.paginator);
    $('#questionCount').html(data.question_counter);
    this.renderSearchTags(data.query_data.tags, data.query_string);
    if (data.faces.length > 0) {
        $('#contrib-users > a').remove();
        $('#contrib-users').append(data.faces.join(''));
    }
    this.renderRelatedTags(data.related_tags_html);
    this.renderRelevanceSortTab(data.query_string);
    this.renderTagWarning(data.non_existing_tags);
    this.setActiveSortTab(
        data.query_data.sort_order,
        data.query_string
    );
    if (data.feed_url) {
        // Change RSS URL
        $('#ContentLeft a.rss:first').attr('href', data.feed_url);
    }

    // Patch scope selectors
    var baseUrl = this._baseUrl;
    $('#scopeWrapper > a.scope-selector').each(function (index) {
        var old_qs = $(this).attr('href').replace(baseUrl, '');
        var scope = QSutils.get_query_string_selector_value(old_qs, 'scope');
        qs = QSutils.patch_query_string(data.query_string, 'scope:' + scope);
        $(this).attr('href', baseUrl + qs);
    });

    // Patch "Ask your question"
    var askButton = $('#askButton');
    var askHrefBase = askButton.attr('href').split('?')[0];
    askButton.attr(
        'href',
        askHrefBase + data.query_data.ask_query_string
    ); /* INFO: ask_query_string should already be URL-encoded! */

    this._query.focus();

    var old_list = $('#' + this._q_list_sel);
    var new_list = $('<div></div>').hide().html(data.questions);
    new_list.find('.timeago').timeago();

    var q_list_sel = this._q_list_sel;
    old_list.stop(true).after(new_list).fadeOut(200, function () {
        //show new div with a fadeIn effect
        old_list.remove();
        new_list.attr('id', q_list_sel);
        new_list.fadeIn(400);
    });
};

FullTextSearch.prototype.evalTitleSearchQuery = function () {
    var cur_query = this.getSearchQuery();
    var prevText = this._prevText;
    if (cur_query !== prevText && this.isRunning() === false) {
        if (cur_query.length >= askbot.settings.minSearchWordLength) {
            this.sendTitleSearchQuery(cur_query);
        } else if (cur_query.length === 0) {
            this.reset();
        }
    }
};

FullTextSearch.prototype.reset = function () {
    this._prevText = '';
    this._dropMenu.reset();
    this._element.val('');
    this._element.focus();
    this._xButton.hide();
};

FullTextSearch.prototype.refreshXButton = function () {
    if (this.getSearchQuery().length > 0) {
        if (this._query.hasClass('searchInput')) {
            $('#searchBar').addClass('cancelable');
            this._xButton.show();
        }
    } else {
        this._xButton.hide();
        $('#searchBar').removeClass('cancelable');
    }
};

FullTextSearch.prototype.updateQueryString = function (query_text) {
    if (query_text === undefined) { // handle missing parameter
        query_text = this.getSearchQuery();
    }
    var newUrl = QSutils.patch_query_string(
        this._searchUrl,
        'query:' + encodeURIComponent(query_text),
        query_text === ''   // remove if empty
    );
    this.setSearchUrl(newUrl);
    return query_text;
};

FullTextSearch.prototype.renderRelatedTags = function (tags_html) {
    $('.js-related-tags').html(tags_html);
};

FullTextSearch.prototype.renderSearchTags = function (tags, query_string) {
    var search_tags = $('#searchTags');
    search_tags.empty();
    var me = this;
    if (tags.length === 0) {
        $('#listSearchTags').hide();
        $('#search-tips').hide();//wrong - if there are search users
    } else {
        $('#listSearchTags').show();
        $('#search-tips').show();
        $.each(tags, function (idx, tag_name) {
            var el;
            var tag = new Tag();
            tag.setName(tag_name);
            tag.setLinkable(false);
            tag.setDeletable(true);
            tag.setDeleteHandler(
                function () {
                    me.removeSearchTag(tag_name, query_string);
                }
            );
            el = tag.getElement();
            // test if the Tag gets appended to a list
            if (search_tags.prop('tagName') === 'UL') {
                // wrap returns original element
                el = el.wrap('<li></li>').parent();
            }
            search_tags.append(el);
        });
    }
};

FullTextSearch.prototype.createRelevanceTab = function (query_string) {
    var relevance_tab = $('<a></a>');
    href = this._baseUrl + QSutils.patch_query_string(query_string, 'sort:relevance-desc');
    relevance_tab.attr('href', href);
    relevance_tab.attr('id', 'by_relevance');
    relevance_tab.html(
        '<span>' + askbot.data.sortButtonData.relevance.label + '</span>'
    );
    return relevance_tab;
};

FullTextSearch.prototype.removeSearchTag = function (tag) {
    var searchUrl = this.getSearchUrl();
    searchUrl = QSutils.remove_search_tag(searchUrl, tag);
    this.setSearchUrl(searchUrl);
    this.sendFullTextSearchQuery();
};

FullTextSearch.prototype.setActiveSortTab = function (sort_method, query_string) {
    var tabs = $('#sort_tabs > a');
    tabs.attr('class', 'off');
    var baseUrl = this._baseUrl;
    tabs.each(function (index, element) {
        var tab = $(element);
        if (tab.attr('id')) {
            var tab_name = tab.attr('id').replace(/^by_/, '');
            if (tab_name in askbot.data.sortButtonData) {
                href = baseUrl + QSutils.patch_query_string(
                                        query_string,
                                        'sort:' + tab_name + '-desc'
                                    );
                tab.attr('href', href);
                tab.attr(
                    'title',
                    askbot.data.sortButtonData[tab_name].desc_tooltip
                );
                tab.html(
                    askbot.data.sortButtonData[tab_name].label
                );
            }
        }
    });
    var bits = sort_method.split('-', 2);
    var name = bits[0];
    var sense = bits[1];//sense of sort
    var antisense = (sense === 'asc' ? 'desc' : 'asc');
    var arrow = (sense === 'asc' ? ' &#9650;' : ' &#9660;');
    var active_tab = $('#by_' + name);
    active_tab.attr('class', 'on');
    active_tab.attr(
        'title',
        askbot.data.sortButtonData[name][antisense + '_tooltip']
    );
    active_tab.html(
        askbot.data.sortButtonData[name].label + arrow
    );
};

FullTextSearch.prototype.renderRelevanceSortTab = function (query_string) {
    if (askbot.settings.showSortByRelevance === false) {
        return;
    }
    var relevance_tab = $('#by_relevance');
    var prevText = this._prevText;
    if (prevText && prevText.length > 0) {
        if (relevance_tab.length === 0) {
            relevance_tab = this.createRelevanceTab(query_string);
            $('#sort_tabs>span').after(relevance_tab);
        }
    } else {
        if (relevance_tab.length > 0) {
            relevance_tab.remove();
        }
    }
};

FullTextSearch.prototype.makeAskHandler = function () {
    var me = this;
    return function () {
        var query = me.getSearchQuery();
        window.location.href = askbot.urls.ask + '?title=' + query;
        return false;
    };
};

FullTextSearch.prototype.setFullTextSearchEnabled = function (enabled) {
    this._fullTextSearchEnabled = enabled;
};

FullTextSearch.prototype.getFullTextSearchEnabled = function () {
    return this._fullTextSearchEnabled;
};

/**
 * keydown handler operates on the tooltip and the X button
 * also opens and closes drop menu according to the min search word threshold
 * keyup is not good enough, because in that case
 * tooltip will be displayed with the input box simultaneously
 */
FullTextSearch.prototype.makeKeyDownHandler = function () {
    var me = this;
    var xButton = this._xButton;
    var dropMenu = this._dropMenu;
    var formSubmitHandler = this.makeFormSubmitHandler();
    return function (e) {//don't like the keyup delay to
        var keyCode = getKeyCode(e);

        if (keyCode === 27) {//escape key
            if (dropMenu.isOpen() === false) {
                me.reset();
                return false;
            }
        } else if (keyCode === 13) {
            if (me.getFullTextSearchEnabled()) {
                formSubmitHandler(e);
                return false;
            } else {
                return true;
            }
        }

        var query = me.getSearchQuery();
        if (query.length) {
            me.refreshXButton();
            var minQueryLength = askbot.settings.minSearchWordLength;
            if (query.length === minQueryLength) {
                if (keyCode !== 8 && keyCode !== 48) {//del and backspace
                    /* we get here if we were expanding the query
                       past the minimum length to trigger search */
                    dropMenu.show();
                    dropMenu.showWaitIcon();
                    dropMenu.showHeader();
                } else {
                    //close drop menu if we were deleting the query
                    dropMenu.reset();
                }
            }
        }
    };
};

FullTextSearch.prototype.makeFormSubmitHandler = function () {
    var me = this;
    var baseUrl = me._baseUrl;
    return function (evt) {
        // if user clicks the button the s(h)e probably wants page reload,
        // so provide that experience but first update the query string
        me.updateQueryString();
        var searchUrl = me.getSearchUrl();
        evt.preventDefault();
        $(document).trigger('askbot.liveSearchSubmit', [me._element]);
        window.location.href = baseUrl + searchUrl;
    };
};

FullTextSearch.prototype.decorate = function (element) {
    this._element = element;/* this is a bit artificial we don't use _element */
    this._query = element;
    this._xButton = $('input[name=reset_query]');
    this._prevText = this.getSearchQuery();
    this._tag_warning_box = new TagWarningBox();

    var dropMenu = new SearchDropMenu();
    dropMenu.setSearchWidget(this);
    dropMenu.setAskHandler(this.makeAskHandler());
    dropMenu.setAskButtonEnabled(this._askButtonEnabled);
    this._dropMenu = dropMenu;
    $('div.search-bar').append(this._dropMenu.getElement());

    $(element).click(function (e) { return false; });
    $(document).click(function () { dropMenu.reset(); });

    //the tag search input is optional in askbot
    $('#ab-tag-search').parent().before(
        this._tag_warning_box.getElement()
    );

    // make search tags functional
    var search_tags = $('#searchTags .js-tag');
    var searchUrl = this.getSearchUrl();
    var me = this;
    $.each(search_tags, function (idx, element) {
        var tag = new Tag();
        tag.decorate($(element));
        //todo: setDeleteHandler and setHandler
        //must work after decorate & must have getName
        tag.setDeleteHandler(
            function () {
                me.removeSearchTag(tag.getName(), searchUrl);
            }
        );
    });
    // enable x button (search reset)
    this._xButton.click(function () {
        /* wrapped in closure because it's not yet defined at this point */
        me.reset();
    });
    this.refreshXButton();

    // enable query box
    var main_page_eval_handle;
    this._query.keydown(this.makeKeyDownHandler());
    this._query.keyup(function (e) {
        me.refreshXButton();
        if (me.isRunning() === false) {
            clearTimeout(main_page_eval_handle);
            main_page_eval_handle = setTimeout(
                function () { me.evalTitleSearchQuery(); },
                400
            );
        }
    });

    this.activateTagSearchInput();

    $('form#searchForm').submit(me.makeFormSubmitHandler());
};

/**
 * @constructor
 */
var TagSearch = function () {
    WrappedElement.call(this);
    this._isRunning = false;
};
inherits(TagSearch, WrappedElement);

TagSearch.prototype.getQuery = function () {
    return $.trim(this._element.val());
};

TagSearch.prototype.setQuery = function (val) {
    this._element.val(val);
};

TagSearch.prototype.getSort = function () {
    //todo: read it off the page
    var link = $('.tabBar a.on');
    if (link.length === 1) {
        var sort = link.attr('id').replace('sort_', '');
        if (sort === 'name' || sort === 'used') {
            return sort;
        }
    }
    return 'name';
};

TagSearch.prototype.getIsRunning = function () {
    return this._isRunning;
};

TagSearch.prototype.setIsRunning = function (val) {
    this._isRunning = val;
};

TagSearch.prototype.renderResult = function (html) {
    this._contentBox.html(html);
};

TagSearch.prototype.runSearch = function () {
    var query = this.getQuery();
    var data = {
        'query': query,
        'sort': this.getSort(),
        'page': '1'
    };
    var me = this;
    $.ajax({
        dataType: 'json',
        data: data,
        cache: false,
        url: askbot.urls.tags,
        success: function (data) {
            if (data.success) {
                me.renderResult(data.html);
                me.setIsRunning(false);
                //rerun if query changed meanwhile
                if (query !== me.getQuery()) {
                    me.runSearch();
                }
            }
        },
        error: function () { me.setIsRunning(false); }
    });
    me.setIsRunning(true);
};

TagSearch.prototype.makeKeyUpHandler = function () {
    var me = this;
    return function (evt) {
        var keyCode = getKeyCode(evt);
        if (me.getIsRunning() === false) {
            me.runSearch();
        }
    };
};

TagSearch.prototype.makeKeyDownHandler = function () {
    var me = this;
    var xButton = this._xButton;
    return function (evt) {
        var query = me.getQuery();
        var keyCode = getKeyCode(evt);
        if (keyCode === 27) {//escape
            me.setQuery('');
            xButton.hide();
            return;
        }
        if (keyCode === 8 || keyCode === 48) {//del or backspace
            if (query.length === 1) {
                xButton.hide();
            }
        } else {
            xButton.show();
        }
    };
};

TagSearch.prototype.reset = function () {
    if (this.getIsRunning() === false) {
        this.setQuery('');
        this._xButton.hide();
        this.runSearch();
        this._element.focus();
    }
};

TagSearch.prototype.decorate = function (element) {
    this._element = element;
    this._contentBox = $('#ContentLeft');
    this._xButton = $('input[name=reset_query]');
    element.keyup(this.makeKeyUpHandler());
    element.keydown(this.makeKeyDownHandler());

    var me = this;
    this._xButton.click(function () { me.reset(); });
};
