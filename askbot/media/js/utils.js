/**
 * attention - this function needs to be retired
 * as it cannot accurately give url to the media file
 */
var mediaUrl = function(resource){
    return askbot['settings']['static_url'] + 'default' + '/' + resource;
};

var cleanUrl = function(url){
    var re = new RegExp('//', 'g');
    return url.replace(re, '/');
};

var copyAltToTitle = function(sel){
    sel.attr('title', sel.attr('alt'));
};

var animateHashes = function(){
    var id_value = window.location.hash;
    if (id_value != ""){
        var previous_color = $(id_value).css('background-color');
        $(id_value).css('backgroundColor', '#FFF8C6');
        $(id_value)
            .animate({backgroundColor: '#ff7f2a'}, 500)
            .animate({backgroundColor: '#FFF8C6'}, 500, function(){
                $(id_value).css('backgroundColor', previous_color);
            });
    }
};

/**
 * @param {string} id_token - any token
 * @param {string} unique_seed - the unique part
 * @returns {string} unique id that can be used in DOM
 */
var askbotMakeId = function(id_token, unique_seed) {
    return id_token + '-' + unique_seed;
};

var getNewUniqueInt = function() {
    var num = askbot['data']['uniqueInt'] || 0;
    num = num + 1;
    askbot['data']['uniqueInt'] = num;
    return num;
};

/**
 * generic tag cleaning function, settings
 * are from askbot live settings and askbot.const
 */
var cleanTag = function(tag_name, settings) {
    var tag_regex = new RegExp(settings['tag_regex']);
    if (tag_regex.test(tag_name) === false) {
        var firstChar = tag_name.substring(0, 1);
        if (settings['tag_forbidden_first_chars'].indexOf(firstChar) > -1) {
            throw settings['messages']['wrong_first_char'];
        } else {
            throw settings['messages']['wrong_chars'];
        }
    }

    var max_length = settings['max_tag_length'];
    if (tag_name.length > max_length) {
        throw interpolate(
            ngettext(
                'must be shorter than %(max_chars)s character',
                'must be shorter than %(max_chars)s characters',
                max_length
            ),
            {'max_chars': max_length },
            true
        );
    }
    if (settings['force_lowercase_tags']) {
        return tag_name.toLowerCase();
    } else {
        return tag_name;
    }
};


var getSingletonController = function(controllerClass, name) {
    askbot['controllers'] = askbot['controllers'] || {};
    var controller = askbot['controllers'][name];
    if (controller === undefined) {
        controller = new controllerClass();
        askbot['controllers'][name] = controller;
    }
    return controller;
};

var setController = function(controller, name) {
    askbot['controllers'] = askbot['controllers'] || {};
    askbot['controllers'][name] = controller;
};

var sortChildNodes = function(node, cmpFunc) {
    var items = node.children().sort(cmpFunc);
    node.append(items);
};

var getUniqueValues = function(values) {
    var uniques = new Object();
    var out = new Array();
    $.each(values, function(idx, value){
        if (!(value in uniques)){
            uniques[value] = 1;
            out.push(value);
        };
    });
    return out;
}

var getUniqueWords = function(value){
    var words = $.trim(value).split(/\s+/);
    return getUniqueValues(words);
};

/**
 * comma-joins items and uses "and'
 * between the last and penultimate items
 * @param {Array<string>} values
 * @return {string}
 */
var joinAsPhrase = function(values) {
    var count = values.length;
    if (count === 0) {
        return '';
    } else if (count === 1) {
        return values[0];
    } else {
        var last = values.pop();
        var prev = values.pop();
        return values.join(', ') + prev + gettext('and') + last;
    }
};

/**
 * @return {boolean}
 */
var inArray = function(item, itemsList) {
    for (var i = 0; i < itemsList.length; i++) {
        if (item === itemsList[i]) {
            return true;
        }
    }
    return false;
};

var showMessage = function(element, msg, where) {
    var div = $('<div class="vote-notification"><h3>' + msg + '</h3>(' +
    gettext('click to close') + ')</div>');

    div.click(function(event) {
        $(".vote-notification").fadeOut("fast", function() { $(this).remove(); });
    });

    var where = where || 'parent';

    if (where == 'parent'){
        element.parent().append(div);
    }
    else {
        element.after(div);
    }

    div.fadeIn("fast");
};

//outer html hack - https://github.com/brandonaaron/jquery-outerhtml/
(function($){
    var div;
    $.fn.outerHTML = function() {
        var elem = this[0],
        tmp;
        return !elem ? null
        : typeof ( tmp = elem.outerHTML ) === 'string' ? tmp
        : ( div = div || $('<div/>') ).html( this.eq(0).clone() ).html();
    };
})(jQuery);

/**
 * @return {number} key code of the event or `undefined`
 */
var getKeyCode = function(e) {
    if (e.which) {
        return e.which;
    } else if (e.keyCode) {
        return e.keyCode;
    }
    return undefined;
};

var makeKeyHandler = function(key, callback){
    return function(e){
        if ((e.which && e.which == key) || (e.keyCode && e.keyCode == key)){
            if(!e.shiftKey){
                callback();
                return false;
            }
        }
    };
};


var setupButtonEventHandlers = function(button, callback){
    button.keydown(makeKeyHandler(13, callback));
    button.click(callback);
};

var removeButtonEventHandlers = function(button) {
    button.unbind('click');
    button.unbind('keydown');
};

var decodeHtml = function(encodedText) {
    return $('<div/>').html(encodedText).text();
};

var putCursorAtEnd = function(element){
    var el = $(element).get()[0];
    var jEl = $(el);
    if (el.setSelectionRange){
        var len = jEl.val().length * 2;
        el.setSelectionRange(len, len);
    }
    else{
        jEl.val(jEl.val());
    }
    jEl.scrollTop(999999);
};

var setCheckBoxesIn = function(selector, value){
    return $(selector + '> input[type=checkbox]').attr('checked', value);
};

/*
 * Old style notify handler
 */
var notify = function() {
    var visible = false;
    return {
        show: function(html, autohide) {
            if (html) {
                $("body").addClass('user-messages');
                var par = $('<p class="notification"></p>');
                par.html(html);
                $(".notify").prepend(par);
            }          
            $(".notify").fadeIn("slow");
            visible = true;
            if (autohide) {
                setTimeout(
                    function() { 
                        notify.close(false);
                        notify.clear();
                    },
                    3000
                );
            }
        },       
        clear: function() {
            $('.notify').empty();
        },
        close: function(doPostback) {
            if (doPostback) {
               $.post(
                   askbot['urls']['mark_read_message'],
                   { formdata: "required" }
               );
            }
            $(".notify").fadeOut("fast");
            $('body').removeClass('user-messages');
            visible = false;
        },     
        isVisible: function() { return visible; }     
    };
}();

/* **************************************************** */
// Search query-string manipulation utils
/* **************************************************** */

var QSutils = QSutils || {};  // TODO: unit-test me

QSutils.TAG_SEP = ','; // should match const.TAG_SEP; TODO: maybe prepopulate this in javascript.html ?

QSutils.get_query_string_selector_value = function (query_string, selector) {
    var params = query_string.split('/');
    for(var i=0; i<params.length; i++) {
        var param_split = params[i].split(':');
        if(param_split[0] === selector) {
            return param_split[1];
        }
    }
    return undefined;
};

QSutils.patch_query_string = function (query_string, patch, remove) {
    var params = query_string.split('/');
    var patch_split = patch.split(':');

    var new_query_string = '';
    var mapping = {};

    if(!remove) {
        // prepopulate the patched selector if it's not meant to be removed
        mapping[patch_split[0]] = patch_split[1];
    }

    for (var i = 0; i < params.length; i++) {
        var param_split = params[i].split(':');
        if(param_split[0] !== patch_split[0] && param_split[1]) {
            mapping[param_split[0]] = param_split[1];
        }
    }

    var add_selector = function(name) {
        if(name in mapping) {
            new_query_string += name + ':' + mapping[name] + '/';
        }
    };

    /* The order of selectors should match the Django URL */
    add_selector('scope');
    add_selector('sort');
    add_selector('tags');
    add_selector('author');
    add_selector('page');
    add_selector('page-size');
    add_selector('query');

    return new_query_string;
};

QSutils.remove_search_tag = function(query_string, tag){
    var tag_string = this.get_query_string_selector_value(query_string, 'tags');
    if(!tag_string) {
        return query_string;
    }

    var tags = tag_string.split(this.TAG_SEP);

    var pos = $.inArray(encodeURIComponent(tag), tags);
    if(pos > -1) {
        tags.splice(pos, 1); /* array.splice() works in-place */
    }

    if(tags.length === 0) {
        return this.patch_query_string(query_string, 'tags:', true);
    } else {
        return this.patch_query_string(query_string, 'tags:' + tags.join(this.TAG_SEP));
    }
};

QSutils.add_search_tag = function(query_string, tag){
    var tag_string = this.get_query_string_selector_value(query_string, 'tags');
    tag = encodeURIComponent(tag);
    if(!tag_string) {
        tag_string = tag;
    } else {
        tag_string = [tag_string, tag].join(this.TAG_SEP);
    }

    return this.patch_query_string(query_string, 'tags:' + tag_string);
};

/* **************************************************** */

/* some google closure-like code for the ui elements */
var inherits = function(childCtor, parentCtor) {
  /** @constructor taken from google closure */
    function tempCtor() {};
    tempCtor.prototype = parentCtor.prototype;
    childCtor.superClass_ = parentCtor.prototype;
    childCtor.prototype = new tempCtor();
    childCtor.prototype.constructor = childCtor;
};

/** wrapper around jQuery object
 * @constructor
 * the top level "class" for other elements
 * I.e. all other things must inherit this class.
 * For an example of the inheritance pattern,
 * please see the "TippedInput" below.
 */
var WrappedElement = function(){
    this._element = null;
    this._in_document = false;
    this._idSeed = null;
};
/* note that we do not call inherits() here
 * See TippedInput as an example of a subclass
 */

/**
 * returns a unique integer for any instance of WrappedElement
 * which can be used to construct a unique id for use in the DOM
 * @return {string}
 */
WrappedElement.prototype.getIdSeed = function() {
    var seed = this._idSeed || parseInt(getNewUniqueInt());
    this._idSeed = seed;
    return seed;
};

/**
 * returns unique ide based on the prefix and the id seed
 * @param {string} prefix
 * @return {string}
 */
WrappedElement.prototype.makeId = function(prefix) {
    return askbotMakeId(prefix, this.getIdSeed());
};

/**
 * notice that we use ObjCls.prototype.someMethod = function()
 * notation - as we use Javascript's prototypal inheritance
 * explicitly. The point of this is to be able to eventually
 * use the Closure Compiler
 */
WrappedElement.prototype.setElement = function(element){
    this._element = element;
};

/** 
 * this function must be overridden for any object
 * what will use "DOM generation" pattern
 *
 * Inside this function two things can happen:
 * 1) dom structure creation
 * 2) event handlers attached to the dom structure
 */
WrappedElement.prototype.createDom = function(){
    /* inside at the very least you must assign
     * a jQuery object to a parameter called _element
     */
    this._element = $('<div></div>');
};

/**
 * @param {object} element, a jQuery object wrapping a single
 * DOM element.
 *
 * This function must be overridden in the subclasses
 * that are used in the "decoration" pattern
 */
WrappedElement.prototype.decorate = function(element){
    this._element = element;
};

/**
 * This method should not be overridden
 * Normally you call this method to generate the dom
 * structure, if applicable, or just obtain the
 * jQuery object encapsulating the dom.
 * 
 * @return {object} jQuery
 */
WrappedElement.prototype.getElement = function(){
    if (this._element === null){
        this.createDom();
    }
    return this._element;
};

WrappedElement.prototype.hasElement = function() {
    return (this._element !== undefined);
};
WrappedElement.prototype.inDocument = function(){
    return (this._element && this._element.is(':hidden') === false);
};
WrappedElement.prototype.enterDocument = function(){
    return this._in_document = true;
};
WrappedElement.prototype.hasElement = function(){
    return (this._element !== null);
};
/**
 * A utility method, returning a new jQuery object for
 * some HTML tag
 *
 * Example:
 * var ageInput = this.makeElement('input');
 */
WrappedElement.prototype.makeElement = function(html_tag){
    //makes jQuery element with tags
    return $('<' + html_tag + '></' + html_tag + '>');
};
/**
 * Removes object's DOM element from the DOM tree
 * should be overridden to remove the event handlers
 * and properly destroy the dom structure
 * as well as any other included sub-elements
 */
WrappedElement.prototype.dispose = function(){
    this._element.remove();
    this._in_document = false;
};

/** 
 * @constructor
 * a loader
 */
var WaitIcon = function() {
    WrappedElement.call(this);
    this._isVisible = false;
};
inherits(WaitIcon, WrappedElement);

WaitIcon.prototype.setVisible = function(isVisible) {
    this._isVisible = isVisible;
    if (this._element) {
        if (this._isVisible === true) {
            this._element.show();
        } else {
            this._element.hide();
        }
    }
};

WaitIcon.prototype.hide = function() {
    this.setVisible(false);
};

WaitIcon.prototype.show = function() {
    this.setVisible(true);
};

WaitIcon.prototype.createDom = function() {
    var box = this.makeElement('div');
    box.addClass('wait-icon-box');
    this._element = box;
    var img = this.makeElement('img');
    img.attr('src', mediaUrl('media/images/ajax-loader.gif'));
    box.append(img);
    this.setVisible(this._isVisible); 
};

var Paginator = function() {
    WrappedElement.call(this);
};
inherits(Paginator, WrappedElement);

/** 
 * A mandotory method.
 * this method needs to be implemented by the subclass
 * @interface
 * @param data is json dict returted by the server
 */
Paginator.prototype.renderPage = function(data) {
    throw 'implement me in the subclass';
};

/**
 * A mandatory method.
 * @interface - implement in subclass
 * returns url that can be used to retrieve page data
 */
Paginator.prototype.getPageDataUrl = function(pageNo) {
    throw 'implement me in the subclass';
};

/** 
 * Optional method
 * @interface - implement in subclass
 * returns url parameters for the page request
 */
Paginator.prototype.getPageDataUrlParams = function(pageNo) {};

Paginator.prototype.setIsLoading = function(isLoading) {
    this._isLoading = isLoading;
};

Paginator.prototype.startLoadingPageData = function(pageNo) {
    if (this._isLoading) {
        return;
    }
    var me = this;
    var requestParams = {
        type: 'GET',
        dataType: 'json',
        url: this.getPageDataUrl(pageNo),
        cache: false,
        success: function(data) {
            me.renderPage(data);
            me.setCurrentPage(pageNo);
            me.setIsLoading(false);
        },
        failure: function() {
            me.setIsLoading(false);
        }
    };
    var urlParams = this.getPageDataUrlParams(pageNo);
    if (urlParams) {
        requestParams['data'] = urlParams;
    }
    $.ajax(requestParams);
    me.setIsLoading(true);
    return false;
};

Paginator.prototype.getCurrentPageNo = function() {
    var page = this._element.find('.curr');
    return parseInt(page.attr('data-page'));
};

Paginator.prototype.getIncrementalPageHandler = function(direction) {
    var me = this;
    return function() {
        var pageNo = me.getCurrentPageNo();
        if (direction === 'next') {
            pageNo = pageNo + 1;
        } else {
            pageNo = pageNo - 1;
        }
        me.startLoadingPageData(pageNo);
        return false;
    };
};

Paginator.prototype.getWindowStart = function(pageNo) {
    var totalPages = this._numPages;
    var activePages = this._numActivePages;

    //paginator is "short" w/o prev or next, no need to rerender
    if (totalPages === activePages) {
        return 1;
    }

    //we are in leading range
    if (pageNo < activePages) {
        return 1;
    }

    //we are in trailing range
    var lastWindowStart = totalPages - activePages + 1;
    if (pageNo > lastWindowStart) {
        return lastWindowStart;
    }

    return pageNo - Math.floor(activePages/2);
};

Paginator.prototype.renderPaginatorWindow = function(windowStart) {
    var anchors = this._paginatorAnchors;
    for (var i = 0; i < anchors.length; i++) {
        var anchor = $(anchors[i]);
        removeButtonEventHandlers(anchor);
        var pageNo = windowStart + i;
        //re-render displayed number
        anchor.html(pageNo);
        //re-render the tooltip text
        var labelTpl = gettext('page %s');
        anchor.attr('title', interpolate(labelTpl, [pageNo]));
        //re-render the "page" data value
        anchor.parent().attr('data-page', pageNo);
        //setup new event handler
        var pageHandler = this.getPageButtonHandler(pageNo);
        setupButtonEventHandlers(anchor, pageHandler);
    }
};

Paginator.prototype.renderPaginatorEdges = function(windowStart, pageNo) {
    //first page button
    var first = this._firstPageNav;
    if (windowStart === 1) {
        first.hide();
    } else {
        first.show();
    }

    //last page button
    var lastWindowStart = this._numPages - this._numActivePages + 1;
    var last = this._lastPageNav;
    if (windowStart === lastWindowStart) {
        last.hide();
    } else {
        last.show();
    }

    //show or hide "prev" and "next" buttons
    if (this._numPages === this._numActivePages) {
        this._prevPageButton.hide();
        this._nextPageButton.hide();
    } else {
        if (pageNo === 1) {
            this._prevPageButton.hide();
        } else {
            this._prevPageButton.show();
        }
        if (pageNo === this._numPages) {
            this._nextPageButton.hide();
        } else {
            this._nextPageButton.show();
        }
    }
};

Paginator.prototype.setCurrentPage = function(pageNo) {

    var currPageNo = this.getCurrentPageNo();
    var currWindow = this.getWindowStart(currPageNo);
    var newWindow = this.getWindowStart(pageNo);
    if (newWindow !== currWindow) {
        this.renderPaginatorWindow(newWindow);
    }

    //select the current page
    var page = this._mainPagesNav.find('[data-page="' + pageNo + '"]');
    if (page.length === 1) {
        var curr = this._element.find('.curr');
        curr.removeClass('curr');
        page.addClass('curr');
    }

    //show or hide ellipses (...) and the last/first page buttons
    //newWindow is starting page of the new paginator window
    this.renderPaginatorEdges(newWindow, pageNo);
};

Paginator.prototype.createButton = function(cls, label) {
    var btn = this.makeElement('span');
    btn.addClass(cls);
    var link = this.makeElement('a');
    link.html(label);
    btn.append(link);
    return btn;
};

Paginator.prototype.getPageButtonHandler = function(pageNo) {
    var me = this;
    return function() { 
        if (me.getCurrentPageNo() !== pageNo) {
            me.startLoadingPageData(pageNo); 
        }
        return false;
    };
};

Paginator.prototype.decorate = function(element) {
    this._element = element;
    var pages = element.find('.page');
    this._firstPageNav = element.find('.first-page-nav');
    this._lastPageNav = element.find('.last-page-nav');
    this._mainPagesNav = element.find('.main-pages-nav');
    var paginatorButtons = element.find('.paginator');
    this._numPages = paginatorButtons.data('numPages');

    var mainNavButtons = element.find('.main-pages-nav a');
    this._paginatorAnchors =  mainNavButtons;
    this._numActivePages = mainNavButtons.length;

    for (var i = 0; i < pages.length; i++) {
        var page = $(pages[i]);
        var pageNo = page.data('page');
        var link = page.find('a');
        var pageHandler = this.getPageButtonHandler(pageNo);
        setupButtonEventHandlers(link, pageHandler);
    }

    var currPageNo = element.find('.curr').data('page');
    
    //next page button
    var nextPage = element.find('.next');
    this._nextPageButton = nextPage;
    if (currPageNo === this._numPages) {
        this._nextPageButton.hide();
    }

    setupButtonEventHandlers(
        this._nextPageButton,
        this.getIncrementalPageHandler('next')
    );

    var prevPage = element.find('.prev');
    this._prevPageButton = prevPage;
    if (currPageNo === 1) {
        this._prevPageButton.hide();
    }

    setupButtonEventHandlers(
        this._prevPageButton,
        this.getIncrementalPageHandler('prev')
    );
};

/**
 * makes images never take more spaces then they can take
 * @param {<Array>} breakPoints
 * @param {number} maxWidth
 * an array of array values like (min-width, width-offset) 
 * where min-width is screen minimum width
 * width-offset - difference between the actual screen width and
 * max-width of the image.
 * width-offset may be undefined - this way we know that this is
 * the widest breakpoint and we apply the default max-width
 * instead.
 * We use this offset to calculate max-width in order to
 * have the images fit the layout no matter the size of the image
 */
var LimitedWidthImage = function(breakPoints, maxWidth) {
    /**
     * breakPoints must be sorted in decreasing
     * order of min-width
     */
    this._breakPoints = breakPoints;
    /**
     * this is width for the fully stretched
     * window, above the first widest breakpoint
     */
    this._maxWidth = maxWidth;
    WrappedElement.call(this);
};
inherits(LimitedWidthImage, WrappedElement);

LimitedWidthImage.prototype.getImageWidthOffset = function(width) {
    var numBreaks = this._breakPoints.length;
    var offset = this._breakPoints[0][1];
    for (var i = 0; i < numBreaks; i++) {
        var point = this._breakPoints[i];
        var minWidth = point[0];
        if (width >= minWidth) {
            break;
        } else {
            offset = point[1];
        }
    }
    return offset;
};

LimitedWidthImage.prototype.autoResize = function() {
    var windowWidth = $(window).width();
    //1) find the offset for the nearest breakpoint
    var widthOffset = this.getImageWidthOffset(windowWidth);
    var maxWidth = '100%';
    if (widthOffset !== undefined) {
        maxWidth = windowWidth - widthOffset;
    } else {
        maxWidth = this._maxWidth;
    }
    this._element.css('max-width', maxWidth);
    this._element.css('height', 'auto');
};

LimitedWidthImage.prototype.decorate = function(element) {
    this._element = element;
    this.autoResize();
    var me = this;
    $(window).resize(function() { me.autoResize(); });
};

/**
 * @contsructor
 * a form helper that disables submit button
 * after it is submitted the first time
 * to prevent double submits
 */
var OneShotForm = function() {
    WrappedElement.call(this);
    this._submitBtn = undefined;
};
inherits(OneShotForm, WrappedElement);

OneShotForm.prototype.setSubmitButton = function(button) {
    this._submitBtn = button;
};

OneShotForm.prototype.enable = function() {
    this._element.data('submitted', false);
    this._submitBtn.removeClass('disabled');
};

OneShotForm.prototype.disable = function() {
    this._element.data('submitted', true);
    this._submitBtn.addClass('disabled');
};

OneShotForm.prototype.decorate = function(element) {
    this._element = element;
    var me = this;
    var button = this._submitBtn;
    var disabler = function(evt) {
        if (element.data('submitted') === true) {
            evt.preventDefault();
        } else {
            me.disable();
            return true;
        }
    };
    element.submit(disabler);
};

/**
 * @constructor
 * a simple link
 */
var Link = function() {
    WrappedElement.call(this);
};
inherits(Link, WrappedElement);

Link.prototype.setUrl = function(url) {
    this._url = url;
};

Link.prototype.setText = function(text) {
    this._text = text;
};

Link.prototype.createDom = function() {
    var link = this.makeElement('a');
    this._element = link;
    link.attr('href', this._url);
    link.html(this._text);
};

/**
 * @constructor
 * Widget is a Wrapped element with state
 */
var Widget = function() {
    WrappedElement.call(this);
    this._state = undefined;
};
inherits(Widget, WrappedElement);

Widget.prototype.setState = function(state) {
    this._state = state;
};

Widget.prototype.getState = function() {
    return this._state;
};

Widget.prototype.makeButton = function(label, handler) {
    var button = this.makeElement('button');
    button.html(label);
    setupButtonEventHandlers(button, handler);
    return button;
};

/**
 * Can be used for an input box or textarea.
 * The original value will be treated as an instruction.
 * When user focuses on the field, the tip will be gone,
 * when the user escapes without typing anything besides 
 * perhaps empty text, the instruction is restored.
 * When instruction is shown, class "blank" is present
 * in the input/textare element.
 *
 * For the usage examples - search for "new TippedInput"
 * there is at least one example for both - decoration and
 * the "dom creation" patterns.
 * 
 * Also - in the FileUploadDialog the TippedInput is used
 * as a sub-element - the widget composition use case.
 */
var TippedInput = function(){
    /* the call below is part 1 of the inheritance pattern */
    WrappedElement.call(this);
    this._instruction = null;
    this._attrs = {};
    //this._is_one_shot = false;//if true on starting typing effect is gone
};
inherits(TippedInput, WrappedElement);
/* the line above is part 2 of the inheritance pattern
 see definition of the function "inherits" for more details
*/

/* Below are all the custom methods of the
  TippedInput class, as well as some required functions
*/

TippedInput.prototype.reset = function(){
    $(this._element).val(this._instruction);
    $(this._element).addClass('blank');
};

/*TippedInput.prototype.setIsOneShot = function(boolValue) {
    this._is_one_shot = boolValue;
};*/

TippedInput.prototype.setInstruction = function(text) {
    this._instruction = text;
};

TippedInput.prototype.setAttr = function(key, value) {
    this._attrs[key] = value;
};

TippedInput.prototype.isBlank = function(){
    return this.getVal() === this._instruction;
};

TippedInput.prototype.getVal = function(){
    return this._element.val();
};

TippedInput.prototype.setVal = function(value){
    if (value) {
        this._element.val(value);
        if (this.isBlank()){
            this._element.addClass('blank');
        } else {
            this._element.removeClass('blank');
        }
    }
};
/**
 * Creates the DOM of tipped input from scratch
 * Notice that there is also a "decorate" method.
 * At least one - createDom or decorate is required,
 * depending on the usage.
 */
TippedInput.prototype.createDom = function() {
    this._element = this.makeElement('input');
    var element = this._element;
    element.val(this._instruction);

    //here we re-use the decorate call (next method)
    //to avoid copy-pasting code
    this.decorate(element);
};

/**
 * Attaches the TippedInput behavior to
 * a pre-existing <input> element
 * 
 * decorate() method normally does not create
 * new dom elements, but it might add some missing elements,
 * if necessary.
 *
 * for example the decorate might be composing inside
 * a more complex widget, in which case other elements
 * can be added via a "composition" pattern, or 
 * just "naked dom elements" added to the current widget's element
 *
 */
TippedInput.prototype.decorate = function(element){
    this._element = element;//mandatory line

    //part 1 - initialize some values and create dom
    element.attr(this._attrs);

    var instruction_text = this.getVal();
    this._instruction = instruction_text;
    this.reset();
    var me = this;

    //part 2 - attach event handlers
    $(element).focus(function(){
        if (me.isBlank()){
            $(element)
                .val('')
                .removeClass('blank');
        }
    });
    $(element).blur(function(){
        var val = $(element).val();
        if ($.trim(val) === ''){
            $(element)
                .val(instruction_text)
                .addClass('blank');
        }
    });
    $(element).keydown(
        makeKeyHandler(27, function(){
            $(element).blur();
        })
    );
};

/**
 * creates an alert that will momentarily flash
 * and then self-destruct
 */
var FlashAlert = function(text) {
    WrappedElement.call(this);
    this._text = text;
};
inherits(FlashAlert, WrappedElement);

FlashAlert.prototype.setPostRunHandler = function(handler) {
    this._postRunHandler = handler;
};

FlashAlert.prototype.setText = function(text) {
    this._text = text;
    if (this.hasElement()) {
        this._element.html(text);
    };
};

FlashAlert.prototype.run = function() {
    var element = this._element;
    var me = this;
    var postRunHandler = this._postRunHandler;
    var finish = function() {
        element.fadeOut();
        me.dispose();
        if (postRunHandler) {
            postRunHandler();
        }
    };
    element.fadeIn(function() { setTimeout(finish, 1000) });
};

FlashAlert.prototype.createDom = function() {
    var element = this.makeElement('div');
    element.addClass('flash-alert');
    element.hide();
    this._element = element;
    if (this._text) {
        element.html(this._text);
    }
};

/**
 * will setup a bootstrap.js alert
 * programmatically
 */
var AlertBox = function(){
    WrappedElement.call(this);
    this._text = null;
};
inherits(AlertBox, WrappedElement);

AlertBox.prototype.setClass = function(classes){
    this._classes = classes;
    if (this._element){
        this._element.addClass(classes);
    }
};

AlertBox.prototype.setError = function(state){
    this._is_error = state;
    if (this._element) {
        if (state === true) {
            this._element.addClass('alert-error');
        } else {
            this._element.removeClass('alert-error');
        }
    }
};

AlertBox.prototype.setText = function(text){
    this._text = text;
    if (this._content){
        this._content.html(text);
    }
};

AlertBox.prototype.getContent = function(){
    if (this._content){
        return this._content;
    } else {
        this._content = this.makeElement('div');
        return this._content;
    }
};

AlertBox.prototype.setContent = function(content){
    var container = this.getContent();
    container.empty()
    container.append(content);
};

AlertBox.prototype.addContent = function(content){
    var container = this.getContent();
    container.append(content);
};

AlertBox.prototype.createDom = function(){
    this._element = this.makeElement('div');
    this._element.addClass('alert fade in');

    if (this._is_error) {
        this.setError(this._is_error);
    }

    if (this._classes){
        this._element.addClass(this._classes);
    }

    this._cancel_button = this.makeElement('button');
    this._cancel_button
        .addClass('close')
        .attr('data-dismiss', 'alert')
        .html('&times;');
    this._element.append(this._cancel_button);

    this._element.append(this.getContent());
    if (this._text){
        this.setText(this._text);
    }

    this._element.alert();//bootstrap.js alert
};

/**
 * @constructor
 * just a span with content
 * useful for subclassing
 */
var SimpleContent = function(){
    WrappedElement.call(this);
    this._content = '';
};
inherits(SimpleContent, WrappedElement);

SimpleContent.prototype.setContent = function(text) {
    this._content = text;
    if (this._element) {
        this._element.html(text);
    }
};

SimpleContent.prototype.getContent = function() {
    return this._content;
};

SimpleContent.prototype.createDom = function() {
    this._element = this.makeElement('span');
    this._element.html(this._content);
};

var SimpleControl = function(){
    WrappedElement.call(this);
    this._handler = null;
    this._title = null;
};
inherits(SimpleControl, WrappedElement);

SimpleControl.prototype.setHandler = function(handler){
    this._handler = handler;
    if (this.hasElement()){
        this.setHandlerInternal();
    }
};

SimpleControl.prototype.getHandler = function(){
    return this._handler;
};

SimpleControl.prototype.setHandlerInternal = function(){
    //default internal setHandler behavior
    setupButtonEventHandlers(this._element, this._handler);
};

SimpleControl.prototype.setTitle = function(title){
    this._title = title;
};

SimpleControl.prototype.decorate = function(element) {
    this._element = element;
    this.setHandlerInternal();
};

/**
 * @constructor
 */
var PostExpander = function() {
    SimpleControl.call(this);
    this._handler = this.getExpandHandler();
};
inherits(PostExpander, SimpleControl);

PostExpander.prototype.setPostId = function(postId) {
    this._postId = postId;
};

PostExpander.prototype.getPostId = function() {
    return this._postId;
};

PostExpander.prototype.showWaitIcon = function() {
    var icon = new WaitIcon();
    this._element.html(icon.getElement());
    icon.show();
};

PostExpander.prototype.updateTheDots = function() {
    var numDots = this._cNumDots + 1;
    if (numDots > this._maxNumDots) {
        numDots = 1;
    }
    this._cNumDots = numDots;
    var dots = '';
    for (var i = 0; i < numDots; i++) {
        dots += '&bull;';
    }
    for (; i < this._maxNumDots; i++) {
        dots += '&nbsp;';
    }
    this._element.html(dots);
};

PostExpander.prototype.stopTheDots = function() {
    clearInterval(this._dotsInterval);
};

PostExpander.prototype.startTheDots = function() {
    var numDots = this._element.find('a').html().length + 2;
    this._maxNumDots = numDots;
    this._cNumDots = 0;
    var dots = '';
    for (var i = 0; i < numDots; i++) {
        dots += '&nbsp;';
    }
    this._element.html(dots);
    var me = this;
    var handler = function() {
        me.updateTheDots();
    };
    this._dotsInterval = setInterval(handler, 150);
};

PostExpander.prototype.getExpandHandler = function() {
    var me = this;
    return function() {
        var element = me.getElement();
        var snippet = $(element.parents('.snippet')[0]);
        $.ajax({
            type: 'GET',
            dataType: 'json',
            data: {'post_id': me.getPostId()},
            url: askbot['urls']['getPostHtml'],
            success: function(data) {
                if (data['post_html']) {
                    snippet.hide();
                    snippet.html(data['post_html']);
                    snippet.fadeIn();
                }
            }
        });
        me.showWaitIcon();
    };
};

var EditLink = function(){
    SimpleControl.call(this)
};
inherits(EditLink, SimpleControl);

EditLink.prototype.createDom = function(){
    var element = $('<a></a>');
    element.addClass('edit');
    this.decorate(element);
};

EditLink.prototype.decorate = function(element){
    this._element = element;
    this._element.attr('title', gettext('click to edit this comment'));
    this._element.html(gettext('edit'));
    this.setHandlerInternal();
};

var CommentConvertLink = function(comment_id){
    WrappedElement.call(this)
    this._comment_id = comment_id;
};
inherits(CommentConvertLink, WrappedElement);

CommentConvertLink.prototype.createDom = function(){
    var element = this.makeElement('form');
    element.addClass('convert-comment');
    element.attr('method', 'POST');
    element.attr('action', askbot['urls']['convertComment']);
    var hidden_input = this.makeElement('input');
    hidden_input.attr('type', 'hidden');
    hidden_input.attr('value', this._comment_id);
    hidden_input.attr('name', 'comment_id');
    hidden_input.attr('id', 'id_comment_id');
    element.append(hidden_input);

    var submit = this.makeElement('input');
    submit.attr('type', 'submit');
    submit.attr('value', gettext('convert to answer'));
    element.append(submit);
    this.decorate(element);
};


CommentConvertLink.prototype.decorate = function(element){
    this._element = element;
};

var DeleteIcon = function(title){
    SimpleControl.call(this);
    this._title = title;
    this._content = null;
};
inherits(DeleteIcon, SimpleControl);

DeleteIcon.prototype.decorate = function(element){
    this._element = element;
    this._element.attr('class', 'delete-icon');
    this._element.attr('title', this._title);
    if (this._handler !== null){
        this.setHandlerInternal();
    }
};

DeleteIcon.prototype.setHandlerInternal = function(){
    setupButtonEventHandlers(this._element, this._handler);
};

DeleteIcon.prototype.createDom = function(){
    this._element = this.makeElement('span');
    this.decorate(this._element);
    if (this._content !== null){
        this.setContent(this._content);
    }
};

DeleteIcon.prototype.setContent = function(content){
    if (this._element === null){
        this._content = content;
    } else {
        this._content = content;
        this._element.html(content);
    }
}

/**
 * @contstructor
 * Simple modal dialog with Ok/Cancel buttons by default
 */
var ModalDialog = function() {
    WrappedElement.call(this);
    this._accept_button_text = gettext('Ok');
    this._reject_button_text = gettext('Cancel');
    this._heading_text = 'Add heading by setHeadingText()';
    this._initial_content = undefined;
    this._accept_handler = function(){};
    var me = this;
    this._reject_handler = function() { me.hide(); };
    this._content_element = undefined;
    this._headerEnabled = true;
    this._className = undefined;
};
inherits(ModalDialog, WrappedElement);

ModalDialog.prototype.show = function() {
    this._element.modal('show');
};

ModalDialog.prototype.hide = function() {
    this._element.modal('hide');
};

ModalDialog.prototype.setContent = function(content) {
    this._initial_content = content;
    if (this._content_element) {
        this._content_element.html(content);
    }
};

ModalDialog.prototype.prependContent = function(content) {
    this._content_element.prepend(content);
};

ModalDialog.prototype.setHeadingText = function(text) {
    this._heading_text = text;
};

ModalDialog.prototype.setAcceptButtonText = function(text) {
    this._accept_button_text = text;
};

ModalDialog.prototype.setRejectButtonText = function(text) {
    this._reject_button_text = text;
};

ModalDialog.prototype.setAcceptHandler = function(handler) {
    this._accept_handler = handler;
};

ModalDialog.prototype.setRejectHandler = function(handler) {
    this._reject_handler = handler;
};

ModalDialog.prototype.clearMessages = function() {
    this._element.find('.alert').remove();
};

ModalDialog.prototype.setMessage = function(text, message_type) {
    var box = new AlertBox();
    box.setText(text);
    if (message_type === 'error') {
        box.setError(true);
    }
    this.prependContent(box.getElement());
};

ModalDialog.prototype.createDom = function() {
    this._element = this.makeElement('div')
    var element = this._element;

    element.addClass('modal');
    if (this._className) {
        element.addClass(this._className);
    }

    //1) create header
    if (this._headerEnabled) {
        var header = this.makeElement('div')
        header.addClass('modal-header');
        element.append(header);
        var close_link = this.makeElement('div');
        close_link.addClass('close');
        close_link.attr('data-dismiss', 'modal');
        close_link.html('x');
        header.append(close_link);
        var title = this.makeElement('h3');
        title.html(this._heading_text);
        header.append(title);
    }



    //2) create content
    var body = this.makeElement('div')
    body.addClass('modal-body');
    element.append(body);
    this._content_element = body;
    if (this._initial_content) {
        this._content_element.append(this._initial_content);
    }

    //3) create footer with accept and reject buttons (ok/cancel).
    var footer = this.makeElement('div');
    footer.addClass('modal-footer');
    element.append(footer);

    var accept_btn = this.makeElement('button');
    accept_btn.addClass('submit');
    accept_btn.html(this._accept_button_text);
    footer.append(accept_btn);

    if (this._reject_button_text) {
        var reject_btn = this.makeElement('button');
        reject_btn.addClass('submit cancel');
        reject_btn.html(this._reject_button_text);
        footer.append(reject_btn);
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
};

/**
 * @constructor
 */
var FileUploadDialog = function() {
    ModalDialog.call(this);
    this._className = 'file-upload-dialog';
    this._post_upload_handler = undefined;
    this._fileType = 'image';
    this._headerEnabled = false;
};
inherits(FileUploadDialog, ModalDialog);

/**
 * allowed values: 'image', 'attachment'
 */
FileUploadDialog.prototype.setFileType = function(fileType) {
    this._fileType = fileType;
};

FileUploadDialog.prototype.getFileType = function() {
    return this._fileType;
};

FileUploadDialog.prototype.setButtonText = function(text) {
    this._fakeInput.val(text);
};

FileUploadDialog.prototype.setPostUploadHandler = function(handler) {
    this._post_upload_handler = handler;
};

FileUploadDialog.prototype.runPostUploadHandler = function(url, descr) {
    this._post_upload_handler(url, descr);
};

FileUploadDialog.prototype.setInputId = function(id) {
    this._input_id = id;
};

FileUploadDialog.prototype.getInputId = function() {
    return this._input_id;
};

FileUploadDialog.prototype.setErrorText = function(text) {
    this.setLabelText(text);
    this._label.addClass('error');
};

FileUploadDialog.prototype.setLabelText= function(text) {
    this._label.html(text);
    this._label.removeClass('error');
};

FileUploadDialog.prototype.setUrlInputTooltip = function(text) {
    this._url_input_tooltip = text;
};

FileUploadDialog.prototype.getUrl = function() {
    var url_input = this._url_input;
    if (url_input.isBlank() === false) {
        return url_input.getVal();
    }
    return '';
};

//disable description for now
//FileUploadDialog.prototype.getDescription = function() {
//    return this._description_input.getVal();
//};

FileUploadDialog.prototype.resetInputs = function() {
    this._url_input.reset();
    //this._description_input.reset();
    this._upload_input.val('');
};

FileUploadDialog.prototype.getInputElement = function() {
    return $('#' + this.getInputId());
};

FileUploadDialog.prototype.installFileUploadHandler = function(handler) {
    var upload_input = this.getInputElement();
    upload_input.unbind('change');
    //todo: fix this - make event handler reinstall work
    upload_input.change(handler);
};

FileUploadDialog.prototype.show = function() {
    //hack around the ajaxFileUpload plugin
    FileUploadDialog.superClass_.show.call(this);
    var handler = this.getStartUploadHandler();
    this.installFileUploadHandler(handler);
};

FileUploadDialog.prototype.getUrlInputElement = function() {
    return this._url_input.getElement();
};

/*
 * argument startUploadHandler is very special it must
 * be a function calling this one!!! Todo: see if there
 * is a more civilized way to do this.
 */
FileUploadDialog.prototype.startFileUpload = function(startUploadHandler) {

    var spinner = this._spinner;
    var label = this._label;

    spinner.ajaxStart(function(){ 
        spinner.show();
        label.hide();
    });
    spinner.ajaxComplete(function(){
        spinner.hide();
        label.show();
    });

    /* important!!! upload input must be loaded by id
     * because ajaxFileUpload monkey-patches the upload form */
    var uploadInput = this.getInputElement();
    uploadInput.ajaxStart(function(){ uploadInput.hide(); });
    uploadInput.ajaxComplete(function(){ uploadInput.show(); });

    //var localFilePath = upload_input.val();

    var me = this;

    $.ajaxFileUpload({
        url: askbot['urls']['upload'],
        secureuri: false,//todo: check on https
        fileElementId: this.getInputId(),
        dataType: 'xml',
        success: function (data, status) {

            var fileURL = $(data).find('file_url').text();
            var origFileName = $(data).find('orig_file_name').text();
            var newStatus = interpolate(
                                gettext('Uploaded file: %s'),
                                [origFileName]
                            );
            /*
            * hopefully a fix for the "fakepath" issue
            * https://www.mediawiki.org/wiki/Special:Code/MediaWiki/83225
            */
            fileURL = fileURL.replace(/\w:.*\\(.*)$/,'$1');
            var error = $(data).find('error').text();
            if (error != ''){
                me.setErrorText(error);
            } else {
                me.getUrlInputElement().attr('value', fileURL);
                me.setLabelText(newStatus);
                if (me.getFileType() === 'image') {
                    var buttonText = gettext('Choose a different image');
                } else {
                    var buttonText = gettext('Choose a different file');
                }
                me.setButtonText(buttonText);
            }

            /* re-install this as the upload extension
             * will remove the handler to prevent double uploading
             * this hack is a manipulation around the 
             * ajaxFileUpload jQuery plugin. */
            me.installFileUploadHandler(startUploadHandler);
        },
        error: function (data, status, e) {
            /* re-install this as the upload extension
            * will remove the handler to prevent double uploading */
            me.setErrorText(gettext('Oops, looks like we had an error. Sorry.'));
            me.installFileUploadHandler(startUploadHandler);
        }
    });
    return false;
};

FileUploadDialog.prototype.getStartUploadHandler = function(){
    var me = this;
    var handler = function() {
        /* the trick is that we need inside the function call
         * to have a reference to itself
         * in order to reinstall the handler later
         * because ajaxFileUpload jquery extension might be destroying it */
        return me.startFileUpload(handler);
    };
    return handler;
};

FileUploadDialog.prototype.createDom = function() {

    var superClass = FileUploadDialog.superClass_;

    var me = this;
    superClass.setAcceptHandler.call(this, function(){
        var url = $.trim(me.getUrl());
        //var description = me.getDescription();
        //@todo: have url cleaning code here
        if (url.length > 0) {
            me.runPostUploadHandler(url);//, description);
            me.resetInputs();
        }
        me.hide();
    });
    superClass.setRejectHandler.call(this, function(){
        me.resetInputs();
        me.hide();
    });
    superClass.createDom.call(this);

    var form = this.makeElement('form');
    form.addClass('ajax-file-upload');
    form.css('margin-bottom', 0);
    this.prependContent(form);

    // Browser native file upload field
    var upload_input = this.makeElement('input');
    upload_input.attr({
        id: this._input_id,
        type: 'file',
        name: 'file-upload'
        //size: 26???
    });
    form.append(upload_input);
    this._upload_input = upload_input;

    var fakeInput = this.makeElement('input');
    fakeInput.attr('type', 'button');
    fakeInput.addClass('submit');
    fakeInput.addClass('fake-file-input');
    if (this._fileType === 'image') {
        var buttonText = gettext('Choose an image to insert');
    } else {
        var buttonText = gettext('Choose a file to insert');
    }
    fakeInput.val(buttonText);
    this._fakeInput = fakeInput;
    form.append(fakeInput);

    setupButtonEventHandlers(fakeInput, function() { upload_input.click() });

    // Label which will also serve as status display
    var label = this.makeElement('label');
    label.attr('for', this._input_id);
    var types = askbot['settings']['allowedUploadFileTypes'];
    types = types.join(', ');
    label.html(gettext('Allowed file types are:') + ' ' + types + '.');
    form.append(label);
    this._label = label;

    // The url input text box, probably unused in fact
    var url_input = new TippedInput();
    url_input.setInstruction(this._url_input_tooltip || gettext('Or paste file url here'));
    var url_input_element = url_input.getElement();
    url_input_element.css({
        'width': '200px',
        'display': 'none'
    });
    form.append(url_input_element);
    //form.append($('<br/>'));
    this._url_input = url_input;

    /* //Description input box
    var descr_input = new TippedInput();
    descr_input.setInstruction(gettext('Describe the image here'));
    this.makeElement('input');
    form.append(descr_input.getElement());
    form.append($('<br/>'));
    this._description_input = descr_input;
    */
    var spinner = this.makeElement('img');
    spinner.attr('src', mediaUrl('media/images/ajax-loader.gif'));
    spinner.css('display', 'none');
    spinner.addClass('spinner');
    form.append(spinner);
    this._spinner = spinner;

    upload_input.change(this.getStartUploadHandler());
};

/**
 * attaches a modal menu with a text editor
 * to a link. The modal menu is from bootstrap.js
 * todo: this should probably be a subclass of ModalDialog,
 * triggered by a link click, then a whole bunch of methods
 * would be simply inherited from the modal dialog:
 * clearMessages, etc.
 */
var TextPropertyEditor = function(){
    WrappedElement.call(this);
    this._editor = null;
};
inherits(TextPropertyEditor, WrappedElement);

TextPropertyEditor.prototype.getWidgetData = function(){
    var data = this._element.data();
    return {
        object_id: data['objectId'],
        model_name: data['modelName'],
        property_name: data['propertyName'],
        url: data['url'],
        help_text: data['helpText'],
        editor_heading: data['editorHeading']
    };
};

TextPropertyEditor.prototype.makeEditor = function(){
    if (this._editor) {
        return this._editor;
    }
    var editor = new ModalDialog();
    this._editor = editor;
    editor.setHeadingText(this.getWidgetData()['editor_heading']);

    //create main content for the editor
    var textarea = this.makeElement('textarea');
    textarea.addClass('tipped-input blank');
    textarea.val(this.getWidgetData()['help_text']);

    var tipped_input = new TippedInput();
    tipped_input.decorate(textarea);
    this._text_input = tipped_input;

    editor.setContent(textarea);
    //body.append(textarea);

    editor.setAcceptButtonText(gettext('Save'));
    editor.setRejectButtonText(gettext('Cancel'));

    var me = this;
    editor.setAcceptHandler(function(){
        me.saveData();
    });

    $(document).append(editor.getElement());
    return editor;
};

TextPropertyEditor.prototype.openEditor = function(){
    this._editor.show();
};

TextPropertyEditor.prototype.clearMessages = function(){
    this._editor.clearMessages()
};

TextPropertyEditor.prototype.showAlert = function(text){
    this._editor.setMessage(text, 'alert');
};

TextPropertyEditor.prototype.showError = function(text){
    this._editor.setMessage(text, 'error');
};

TextPropertyEditor.prototype.setText = function(text){
    this._text_input.setVal(text);
};

TextPropertyEditor.prototype.getText = function(){
    return this._text_input.getVal();
};

TextPropertyEditor.prototype.hideDialog = function(){
    this._editor.hide();
};

TextPropertyEditor.prototype.startOpeningEditor = function(){
    var me = this;
    $.ajax({
        type: 'GET',
        dataType: 'json',
        cache: false,
        url: me.getWidgetData()['url'],
        data: me.getWidgetData(),
        success: function(data){
            if (data['success']) {
                me.makeEditor();
                me.setText($.trim(data['text']));
                me.openEditor();
            } else {
                showMessage(me.getElement(), data['message']);
            }
        }
    });
};

TextPropertyEditor.prototype.saveData = function(){
    var data = this.getWidgetData();
    data['text'] = this.getText();
    var me = this;
    $.ajax({
        type: 'POST',
        dataType: 'json',
        cache: false,
        url: me.getWidgetData()['url'],
        data: data,
        success: function(data) {
            if (data['success']) {
                me.showAlert(gettext('saved'));
                setTimeout(function(){
                    me.clearMessages();
                    me.hideDialog();
                }, 1000);
            } else {
                me.showError(data['message']);
            }
        }
    });
};

TextPropertyEditor.prototype.decorate = function(element){
    this._element = element;
    var me = this;
    setupButtonEventHandlers(element, function(){ me.startOpeningEditor() });
};

/**
 * A button on which user can click
 * and become added to some group (followers, group members, etc.)
 * or toggle some state on/off
 * The button has four states on-prompt, off-prompt, on-state and off-state
 * on-prompt is activated on mouseover, when user is not part of group
 * off-prompt - on mouseover, when user is part of group
 * on-state - when user is part of group and mouse is not over the button
 * off-state - same as above, but when user is not part of the group
 */
var TwoStateToggle = function(){
    SimpleControl.call(this);
    this._state = null;
    this._state_messages = {};
    this._states = [
        'on-state',
        'off-state',
        'on-prompt',
        'off-prompt'
    ];
    this._handler = this.getDefaultHandler();
    this._post_data = {};
    this.toggleUrl = '';//public property
};
inherits(TwoStateToggle, SimpleControl);

TwoStateToggle.prototype.setPostData = function(data){
    this._post_data = data;
};

TwoStateToggle.prototype.getPostData = function(){
    return this._post_data;
};

TwoStateToggle.prototype.resetStyles = function(){
    var element = this._element;
    var states = this._states;
    $.each(states, function(idx, state){
        element.removeClass(state);
    });
    this._element.html('');
};

TwoStateToggle.prototype.isOn = function(){
    return this._element.hasClass('on');
};

TwoStateToggle.prototype.getDefaultHandler = function(){
    var me = this;
    return function(){
        var data = me.getPostData();
        data['disable'] = me.isOn();
        $.ajax({
            type: 'POST',
            dataType: 'json',
            cache: false,
            url: me.toggleUrl,
            data: data,
            success: function(data) {
                if (data['success']) {
                    if ( data['is_enabled'] ) {
                        me.setState('on-state');
                    } else {
                        me.setState('off-state');
                    }
                } else {
                    showMessage(me.getElement(), data['message']);
                }
            }
        });
    };
};

TwoStateToggle.prototype.isCheckBox = function(){
    var element = this._element;
    return element.attr('type') === 'checkbox';
};

TwoStateToggle.prototype.setState = function(state){
    var element = this._element;
    this._state = state;
    if (element) {
        this.resetStyles();
        element.addClass(state);
        if (state === 'on-state') {
            element.addClass('on');
        } else if (state === 'off-state') {
            element.removeClass('on');
        }
        if ( this.isCheckBox() ) {
            if (state === 'on-state') {
                element.attr('checked', true);
            } else if (state === 'off-state') {
                element.attr('checked', false);
            }
        } else {
            this._element.html(this._state_messages[state]);
        }
    }
};

TwoStateToggle.prototype.decorate = function(element){
    this._element = element;
    //read messages for all states
    var messages = {};
    messages['on-state'] =
        element.attr('data-on-state-text') || gettext('enabled');
    messages['off-state'] = 
        element.attr('data-off-state-text') || gettext('disabled');
    messages['on-prompt'] =
        element.attr('data-on-prompt-text') || messages['on-state'];
    messages['off-prompt'] = 
        element.attr('data-off-prompt-text') || messages['off-state'];
    this._state_messages = messages;

    this.toggleUrl = element.attr('data-toggle-url');

    //detect state and save it
    if (this.isCheckBox()) {
        this._state = element.attr('checked') ? 'state-on' : 'state-off';
    } else {
        var text = $.trim(element.html());
        for (var i = 0; i < this._states.length; i++){
            var state = this._states[i];
            if (text === messages[state]){
                this._state = state;
                break;
            }
        }
    }

    //set mouseover handler only for non-checkbox version
    if (this.isCheckBox() === false) {
        var me = this;
        element.mouseover(function(){
            var is_on = me.isOn();
            if (is_on){
                me.setState('off-prompt');
            } else {
                me.setState('on-prompt');
            }
            //element.css('background-color', 'red');
            return false;
        });
        element.mouseout(function(){
            var is_on = me.isOn();
            if (is_on){
                me.setState('on-state');
            } else {
                me.setState('off-state');
            }
            //element.css('background-color', 'white');
            return false;
        });
    }

    setupButtonEventHandlers(element, this.getHandler());
};

/**
 * @contstructor
 * a simple dropdown select element
 * which saves data to the server on change
 */
var DropdownSelect = function() {
    WrappedElement.call(this);
};
inherits(DropdownSelect, WrappedElement);

DropdownSelect.prototype.setPostData = function(data) {
    this._postData = data;
};

/**
 * posts value of selection to the url given
 * with data-url and parameter called "value"
 */
DropdownSelect.prototype.saveChoice = function() {
    var element = this._element;
    var url = this._url;
    var data = this._postData;
    data['value'] = element.val();
    $.ajax({
        type: 'POST',
        dataType: 'json',
        data: data,
        cache: false,
        url: url,
        success: function(data) {
            if (!data['success']) {
                showMessage(element, data['message']);
            }
        }
    });
};

DropdownSelect.prototype.decorate = function(element) {
    this._element = element;
    this._url = $(element).data('url');
    var me = this;
    this._element.change(function() {
        me.saveChoice();
    });
};

var BoxItemContent = function() {
    SimpleContent.call(this);
};
inherits(BoxItemContent, SimpleContent);

/**
 * @override to allow for more complex content
 */
BoxItemContent.prototype.setName = function(name) {
    BoxItemContent.superClass_.setContent.call(this, name);
};
BoxItemContent.prototype.getName = function() {
    return BoxItemContent.superClass_.getContent.call(this);
};

/**
 * @constructor
 * an item used for the select box described below
 */
var SelectBoxItem = function() {
    Widget.call(this);
    this._id = null;
    this._name = null;
    this._description = null;
    this._content_class = BoxItemContent;//default expects a single text node
    //content element - instance of this._content_class
    this._content = undefined;
    this._selector = undefined;//the selector object
};
inherits(SelectBoxItem, Widget);

SelectBoxItem.prototype.setId = function(id) {
    this._id = id;
    if (this._element) {
        this._element.data('itemId', id);
    }
};

SelectBoxItem.prototype.getId = function() {
    return this._id;
};

SelectBoxItem.prototype.setName = function(name) {
    this._name = name;
    if (this._content) {
        this._content.setName(name);
    }
};

SelectBoxItem.prototype.setDescription = function(description) {
    this._description = description;
    if (this._element) {
        this._element.data('originalTitle');
    }
};

SelectBoxItem.prototype.getData = function () {
    //todo: stuck using old key names, change after merge
    //with the user-groups branch
    return {
        id: this._id,
        title: this._name,
        details: this._description
    };
};

SelectBoxItem.prototype.setSelector = function(sel) {
    this._selector = sel;
};

SelectBoxItem.prototype.getSelector = function(sel) {
    return this._selector;
};

SelectBoxItem.prototype.getContent = function() {
    return this._content;
};

SelectBoxItem.prototype.isSelected = function() {
    return this._element.hasClass('selected');
};

SelectBoxItem.prototype.setSelected = function(is_selected) {
    if (is_selected) {
        this._element.addClass('selected');
    } else {
        this._element.removeClass('selected');
    }
}

SelectBoxItem.prototype.detach = function() {
    this._element.detach();
};

SelectBoxItem.prototype.createDom = function() {
    var elem = this.makeElement('li');
    this._element = elem;
    elem.data('itemId', this._id);
    elem.data('itemOriginalTitle', this._description);
    var content = new this._content_class();
    content.setName(this._name);
    elem.append(content.getElement());
    this._content = content;
}
/**
 * this method sets css class to the item's DOM element
 */
SelectBoxItem.prototype.addCssClass = function(css_class) {
    this._element.addClass(css_class);
};

SelectBoxItem.prototype.decorate = function(element) {
    this._element = element;
    //set id and description
    this._id = element.data('itemId');
    this._description = element.data('originalTitle');

    //work on setting name
    var content_source = element.contents().detach();
    var content = new this._content_class();
    //assume that we want first node only
    content.setContent(content_source[0]);
    this._content = content;
    this._name = content.getName();//allows to abstract from structure

    this._element.append(content.getElement());
};

/**
 * A list of items from where one can be selected
 */
var SelectBox = function(){
    Widget.call(this);
    this._items = [];
    this._select_handler = function(){};//empty default
    this._is_editable = false;
    this._item_class = SelectBoxItem;
};
inherits(SelectBox, Widget);

SelectBox.prototype.setItemClass = function(itemClass) {
    this._item_class = itemClass;
};

SelectBox.prototype.setEditable = function(is_editable) {
    this._is_editable = is_editable;
};

SelectBox.prototype.isEditable = function() {
    return this._is_editable;
};

SelectBox.prototype.detachAllItems = function() {
    var items = this._items;
    $.each(items, function(idx, item){
        item.detach();
    });
    this._items = [];
};

SelectBox.prototype.getItem = function(id){
    var items = this._items;
    for (var i = 0; i < items.length; i++) {
        if (items[i].getId() === id) {
            return items[i];
        }
    }
    return undefined;
};

SelectBox.prototype.getItemByIndex = function(idx) {
    return this._items[idx];
};

/**
 * removes all items
 */
SelectBox.prototype.empty = function() {
    var items = this._items;
    $.each(items, function(idx, item){
        item.dispose();
    });
    this._items = [];
};

/* 
 * why do we have these two almost identical methods?
 * the difference seems to be remove/vs fade out
 */
SelectBox.prototype.removeItem = function(id){
    var item = this.getItem(id);
    item.getElement().fadeOut();
    item.dispose();
    var idx = $.inArray(item, this._items);
    if (idx !== -1) {
        this._items.splice(idx, 1);
    }
};
SelectBox.prototype.deleteItem = function(id) {
    var item = this.getItem(id);
    if (item === undefined) {
        return;
    }
    item.dispose();
    var idx = $.inArray(item, this._items);
    if (idx !== -1) {
        this._items.splice(idx, 1);
    }
};

SelectBox.prototype.createItem = function() {
    return new this._item_class();
};

SelectBox.prototype.getItemIndex = function(item) {
    var idx = $.inArray(item, this._items);
    if (idx === -1) {
        throw "index error";
    }
    return idx;
};

SelectBox.prototype.addItemObject = function(item) {
    this._items.push(item);
    this._element.append(item.getElement());
    this.selectItem(item);
    item.setSelector(this);
    //set event handler
    var me = this;
    setupButtonEventHandlers(
        item.getElement(),
        me.getSelectHandler(item)
    );
};

/** @todo: rename to setItem?? have a problem when id's are all say 0 */
SelectBox.prototype.addItem = function(id, name, description){

    if (this.hasElement() === false) {
        return;
    }
    //delete old item
    this.deleteItem(id);
    //create new item
    var item = this.createItem();
    item.setId(id);
    item.setName(name);
    item.setDescription(description);
    //add item to the SelectBox
    this.addItemObject(item);

    return item;
};

SelectBox.prototype.getSelectedItem = function() {
    for (var i = 0; i < this._items.length; i++) {
        var item = this._items[i];
        if (item.isSelected()) {
            return item;
        }
    }
    return undefined;
};

SelectBox.prototype.getSelectedItemData = function() {
    var item = this.getSelectedItem();
    if (item) {
        return item.getData() || undefined;
    } else {
        return undefined;
    }
};

SelectBox.prototype.selectItem = function(item){
    this.clearSelection();
    item.setSelected(true);
};

SelectBox.prototype.clearSelection = function(){
    $.each(this._items, function(idx, item) {
        item.setSelected(false);
    });
};

SelectBox.prototype.setSelectHandler = function(handler) {
    this._select_handler = handler;
};

SelectBox.prototype.getSelectHandler = function(item) {
    var me = this;
    var handler = this._select_handler;
    return function(){
        me.selectItem(item);
        handler(item.getData());
    };
};

SelectBox.prototype.decorate = function(element){
    this._element = element;
    var me = this;
    var box_items = this._items;
    var item_elements = this._element.find('.select-box-item');
    item_elements.each(function(idx, item_element){
        var item = me.createItem();
        item.decorate($(item_element));
        box_items.push(item);
        setupButtonEventHandlers(
            item.getElement(),
            me.getSelectHandler(item)
        );
    });
};

SelectBox.prototype.createDom = function() {
    var element = this.makeElement('ul');
    this._element = element;
    element.addClass('select-box');
};

/**
 * This is a dropdown list elment 
 */

var GroupDropdown = function(groups){
    WrappedElement.call(this);
    this._group_list = groups; 
};
inherits(GroupDropdown, WrappedElement);

GroupDropdown.prototype.createDom =  function(){
    this._element = this.makeElement('ul');
    this._element.attr('class', 'dropdown-menu');
    this._element.attr('id', 'groups-dropdown');
    this._element.attr('role', 'menu');
    this._element.attr('aria-labelledby', 'navGroups');

    this._input_box = new TippedInput();
    this._input_box.setInstruction(gettext('group name'));
    this._input_box.createDom();
    this._input_box_element = this._input_box.getElement();
    this._input_box_element.attr('class', 'group-name');
    this._input_box_element.hide();
    this._add_link = this.makeElement('a');
    this._add_link.attr('href', '#');
    this._add_link.attr('class', 'group-name');
    this._add_link.text(gettext('add new group'));

    for (var i=0; i<this._group_list.length; i++){
        var li = this.makeElement('li');
        var a = this.makeElement('a');
        a.text(this._group_list[i].name);
        a.attr('href', this._group_list[i].link);
        a.attr('class', 'group-name');
        li.append(a);
        this._element.append(li);
    }
    if (askbot['data']['userIsAdmin']) {
        this.enableAddGroups();
    }
};

/**
 * inserts a link to group with a given url to the group page
 * and name
 */
GroupDropdown.prototype.insertGroup = function(group_name, url){

    //1) take out first and last list elements: 
    // everyone and the "add group" item
    var list = this._element.children();
    var everyoneGroup = list.first().detach();
    var groupAdder = list.last().detach();
    var divider = this._element.find('.divider').detach();

    //2) append group link into the list
    var li = this.makeElement('li');
    var a = this.makeElement('a');
    a.attr('href', url);
    a.attr('class', 'group-name');
    a.text(group_name);
    li.append(a);
    li.hide();
    this._element.append(li);

    //3) sort rest of the list alphanumerically
    sortChildNodes(
        this._element,
        function(a, b) {
            var valA = $(a).find('a').text().toLowerCase();
            var valB = $(b).find('a').text().toLowerCase();
            return (valA < valB) ? -1: (valA > valB) ? 1: 0;
        }
    );

    //a dramatic effect
    li.fadeIn();

    //4) reinsert the first and last elements of the list:
    this._element.prepend(everyoneGroup);
    this._element.append(divider);
    this._element.append(groupAdder);
};

GroupDropdown.prototype.setState = function(state) {
    if (state === 'display') {
        this._input_box_element.hide();
        this._add_link.show();
    }
};

GroupDropdown.prototype.hasGroup = function(groupName) {
    var items = this._element.find('li');
    for (var i=1; i < items.length - 1; i++) {
        var cGroupName = $(items[i]).find('a').text();
        if (cGroupName.toLowerCase() === groupName.toLowerCase()) {
            return true;
        }
    }
    return false;
};

GroupDropdown.prototype._add_group_handler = function(group_name){
    var group_name = this._input_box_element.val();
    var me = this;
    if (!group_name){
        return;
    }

    $.ajax({
        type: 'POST',
        url: askbot['urls']['add_group'],
        data: {group: group_name},
        success: function(data){
            if (data['success']){
                var groupName = data['group_name'];
                if (me.hasGroup(groupName)) {
                    var message = interpolate(gettext(
                            'Group %(name)s already exists. Group names are case-insensitive.'
                        ), {'name': groupName}, true
                    );
                    notify.show(message);
                    return false;
                } else {
                    me.insertGroup(data['group_name'], data['url']);
                    me.setState('display');
                    return true; 
                }
            } else{
                notify.show(data['message']);
                return false;
            }
        },
        error: function(){console.log('error');}
    });
};

GroupDropdown.prototype.enableAddGroups = function(){
    var self = this;
    this._add_link.click(function(){ 
        self._add_link.hide();
        self._input_box_element.show(); 
        self._input_box_element.focus(); 
    });
    this._input_box_element.keydown(function(event){
        if (event.which == 13 || event.keyCode==13){
            self._add_group_handler(); 
            self._input_box_element.val('');
        }
    });

    var divider = this.makeElement('li');
    divider.attr('class', 'divider');
    this._element.append(divider);

    var container = this.makeElement('li');
    container.append(this._add_link);
    container.append(this._input_box_element);

    this._element.append(container);
};

var Tag = function(){
    SimpleControl.call(this);
    this._deletable = false;
    this._delete_handler = null;
    this._delete_icon_title = null;
    this._tag_title = null;
    this._name = null;
    this._url_params = null;
    this._inner_html_tag = 'a';
    this._html_tag = 'li';
}
inherits(Tag, SimpleControl);

Tag.prototype.setName = function(name){
    this._name = name;
};

Tag.prototype.getName = function(){
    return this._name;
};

Tag.prototype.setHtmlTag = function(html_tag){
    this._html_tag = html_tag;
};

Tag.prototype.setDeletable = function(is_deletable){
    this._deletable = is_deletable;
};

Tag.prototype.setLinkable = function(is_linkable){
    if (is_linkable === true){
        this._inner_html_tag = 'a';
    } else {
        this._inner_html_tag = 'span';
    }
};

Tag.prototype.isLinkable = function(){
    return (this._inner_html_tag === 'a');
};

Tag.prototype.isDeletable = function(){
    return this._deletable;
};

Tag.prototype.isWildcard = function(){
    return (this.getName().substr(-1) === '*');
};

Tag.prototype.setUrlParams = function(url_params){
    this._url_params = url_params;
};

Tag.prototype.setHandlerInternal = function(){
    setupButtonEventHandlers(this._element.find('.tag'), this._handler);
};

/* delete handler will be specific to the task */
Tag.prototype.setDeleteHandler = function(delete_handler){
    this._delete_handler = delete_handler;
    if (this.hasElement() && this.isDeletable()){
        this._delete_icon.setHandler(delete_handler);
    }
};

Tag.prototype.getDeleteHandler = function(){
    return this._delete_handler;
};

Tag.prototype.setDeleteIconTitle = function(title){
    this._delete_icon_title = title;
};

Tag.prototype.decorate = function(element){
    this._element = element;
    var del = element.find('.delete-icon');
    if (del.length === 1){
        this.setDeletable(true);
        this._delete_icon = new DeleteIcon();
        if (this._delete_icon_title != null){
            this._delete_icon.setTitle(this._delete_icon_title);
        }
        //do not set the delete handler here
        this._delete_icon.decorate(del);
    }
    this._inner_element = this._element.find('.tag');
    this._name = this.decodeTagName(
        $.trim(this._inner_element.attr('data-tag-name'))
    );
    if (this._title !== null){
        this._inner_element.attr('title', this._title);
    }
    if (this._handler !== null){
        this.setHandlerInternal();
    }
};

Tag.prototype.getDisplayTagName = function(){
    //replaces the trailing * symbol with the unicode asterisk
    return this._name.replace(/\*$/, '&#10045;');
};

Tag.prototype.decodeTagName = function(encoded_name){
    return encoded_name.replace('\u273d', '*');
};

Tag.prototype.createDom = function(){
    this._element = this.makeElement(this._html_tag);
    //render the outer element
    if (this._deletable){
        this._element.addClass('deletable-tag');
    }
    this._element.addClass('tag-left');

    //render the inner element
    this._inner_element = this.makeElement(this._inner_html_tag);
    if (this.isLinkable()){
        var url = askbot['urls']['questions'];
        var flag = false
        var author = ''
        if (this._url_params){
            url += QSutils.add_search_tag(this._url_params, this.getName());
        }
        this._inner_element.attr('href', url);
    }
    this._inner_element.addClass('tag tag-right');
    this._inner_element.attr('rel', 'tag');
    if (this._title === null) {
        var name = this.getName();
        this.setTitle(interpolate(gettext("see questions tagged '%s'"), [name,]));
    }
    this._inner_element.attr('title', this._title);
    this._inner_element.html(this.getDisplayTagName());
    this._inner_element.data('tagName', this.getName());

    this._element.append(this._inner_element);

    if (!this.isLinkable() && this._handler !== null){
        this.setHandlerInternal();
    }

    if (this._deletable){
        this._delete_icon = new DeleteIcon();
        this._delete_icon.setHandler(this.getDeleteHandler());
        if (this._delete_icon_title !== null){
            this._delete_icon.setTitle(this._delete_icon_title);
        }
        var del_icon_elem = this._delete_icon.getElement();
        del_icon_elem.text('x'); // HACK by Tomasz
        this._element.append(del_icon_elem);
    }
};

var PermsHoverCard = function() {
    WrappedElement.call(this);
    this._isLoaded = false;
};
inherits(PermsHoverCard, WrappedElement);

PermsHoverCard.prototype.setContent = function(data) {
    this._element.html(data['html']);
};

PermsHoverCard.prototype.setTrigger = function(trigger) {
    this._trigger = trigger;
};

PermsHoverCard.prototype.setPosition = function() {
    var trigger = this._trigger.getElement();
    var coors = trigger.offset();
    var height = trigger.outerHeight();
    var triangle = this._element.find('.triangle')
    var triangleHeight = triangle.outerHeight();
    this._element.css({
        'top': coors.top + height + triangleHeight,
        'left': coors.left
    });
};

PermsHoverCard.prototype.setUrl = function(url) {
    this._url = url;
};

PermsHoverCard.prototype.startLoading = function(onLoad) {
    var me = this;
    $.ajax({
        type: 'GET',
        dataType: 'json',
        cache: false,
        url: this._url,
        success: function(data) {
            if (data['success']) {
                me.setContent(data);
                me.setPosition();
                onLoad();
                me.setIsLoaded();
            } else {
                notify.show(data['message']);
            }
        }
    });
};

PermsHoverCard.prototype.isLoaded = function() {
    return this._isLoaded;
};

PermsHoverCard.prototype.setIsLoaded = function() {
    this._isLoaded = true;
};

PermsHoverCard.prototype.getOpenHandler = function() {
    var me = this;
    return function() {
        me.clearCancelOpenTimeout();
        if (me.isLoaded()) {
            me.getElement().show();
        } else {
            var onload = function() {
                me.getElement().show();
            }
            me.startLoading(onload);
        }
    };
};

PermsHoverCard.prototype.setCancelOpenTimoutId = function(timeoutId) {
    this._cancelOpenTimeoutId = timeoutId;
};

PermsHoverCard.prototype.clearCancelOpenTimeout = function() {
    var timeout = this._cancelOpenTimeoutId;
    if (timeout) {
        clearTimeout(timeout);
    }
};

PermsHoverCard.prototype.getCloseHandler = function() {
    var me = this;
    return function() {
        var element = me.getElement();
        //start timeout to close
        var timeout = setTimeout(function() {
            element.hide();
            //element.fadeOut('fast');
        }, 200);
        me.setCancelOpenTimoutId(timeout);
    };
};

PermsHoverCard.prototype.getImmediateCloseHandler = function() {
    var me = this;
    return function() {
        me.getElement().hide();
    };
};

PermsHoverCard.prototype.getKeepHandler = function() {
    var me = this;
    return function() {
        me.clearCancelOpenTimeout();
    };
};

PermsHoverCard.prototype.createDom = function() {
    var element = this.makeElement('div');
    this._element = element;
    element.addClass('hovercard');
    element.hover(
        this.getKeepHandler(),
        this.getCloseHandler()
    );
    this._element.hide();
};

var ShowPermsTrigger = function() {
    WrappedElement.call(this);
};
inherits(ShowPermsTrigger, WrappedElement);

ShowPermsTrigger.prototype.decorate = function(element) {
    this._element = element;
    var hoverCard = new PermsHoverCard();
    this._hoverCard = hoverCard;
    $('body').append(hoverCard.getElement());

    hoverCard.setTrigger(this);
    hoverCard.setUrl(element.data('url'));

    var onEnter = hoverCard.getOpenHandler();
    var onExit = hoverCard.getCloseHandler();
    element.hover(onEnter, onExit);
    var onClose = hoverCard.getImmediateCloseHandler();
    $('body').click(onClose);
};

//Search Engine Keyword Highlight with Javascript
//http://scott.yang.id.au/code/se-hilite/
Hilite={elementid:"content",exact:true,max_nodes:1000,onload:true,style_name:"hilite",style_name_suffix:true,debug_referrer:""};Hilite.search_engines=[["local","q"],["cnprog\\.","q"],["google\\.","q"],["search\\.yahoo\\.","p"],["search\\.msn\\.","q"],["search\\.live\\.","query"],["search\\.aol\\.","userQuery"],["ask\\.com","q"],["altavista\\.","q"],["feedster\\.","q"],["search\\.lycos\\.","q"],["alltheweb\\.","q"],["technorati\\.com/search/([^\\?/]+)",1],["dogpile\\.com/info\\.dogpl/search/web/([^\\?/]+)",1,true]];Hilite.decodeReferrer=function(d){var g=null;var e=new RegExp("");for(var c=0;c<Hilite.search_engines.length;c++){var f=Hilite.search_engines[c];e.compile("^http://(www\\.)?"+f[0],"i");var b=d.match(e);if(b){var a;if(isNaN(f[1])){a=Hilite.decodeReferrerQS(d,f[1])}else{a=b[f[1]+1]}if(a){a=decodeURIComponent(a);if(f.length>2&&f[2]){a=decodeURIComponent(a)}a=a.replace(/\'|"/g,"");a=a.split(/[\s,\+\.]+/);return a}break}}return null};Hilite.decodeReferrerQS=function(f,d){var b=f.indexOf("?");var c;if(b>=0){var a=new String(f.substring(b+1));b=0;c=0;while((b>=0)&&((c=a.indexOf("=",b))>=0)){var e,g;e=a.substring(b,c);b=a.indexOf("&",c)+1;if(e==d){if(b<=0){return a.substring(c+1)}else{return a.substring(c+1,b-1)}}else{if(b<=0){return null}}}}return null};Hilite.hiliteElement=function(f,e){if(!e||f.childNodes.length==0){return}var c=new Array();for(var b=0;b<e.length;b++){e[b]=e[b].toLowerCase();if(Hilite.exact){c.push("\\b"+e[b]+"\\b")}else{c.push(e[b])}}c=new RegExp(c.join("|"),"i");var a={};for(var b=0;b<e.length;b++){if(Hilite.style_name_suffix){a[e[b]]=Hilite.style_name+(b+1)}else{a[e[b]]=Hilite.style_name}}var d=function(m){var j=c.exec(m.data);if(j){var n=j[0];var i="";var h=m.splitText(j.index);var g=h.splitText(n.length);var l=m.ownerDocument.createElement("SPAN");m.parentNode.replaceChild(l,h);l.className=a[n.toLowerCase()];l.appendChild(h);return l}else{return m}};Hilite.walkElements(f.childNodes[0],1,d)};Hilite.hilite=function(){var a=Hilite.debug_referrer?Hilite.debug_referrer:document.referrer;var b=null;a=Hilite.decodeReferrer(a);if(a&&((Hilite.elementid&&(b=document.getElementById(Hilite.elementid)))||(b=document.body))){Hilite.hiliteElement(b,a)}};Hilite.walkElements=function(d,f,e){var a=/^(script|style|textarea)/i;var c=0;while(d&&f>0){c++;if(c>=Hilite.max_nodes){var b=function(){Hilite.walkElements(d,f,e)};setTimeout(b,50);return}if(d.nodeType==1){if(!a.test(d.tagName)&&d.childNodes.length>0){d=d.childNodes[0];f++;continue}}else{if(d.nodeType==3){d=e(d)}}if(d.nextSibling){d=d.nextSibling}else{while(f>0){d=d.parentNode;f--;if(d.nextSibling){d=d.nextSibling;break}}}}};if(Hilite.onload){if(window.attachEvent){window.attachEvent("onload",Hilite.hilite)}else{if(window.addEventListener){window.addEventListener("load",Hilite.hilite,false)}else{var __onload=window.onload;window.onload=function(){Hilite.hilite();__onload()}}}};

if(!this.JSON){this.JSON={}}(function(){function f(n){return n<10?"0"+n:n}if(typeof Date.prototype.toJSON!=="function"){Date.prototype.toJSON=function(key){return isFinite(this.valueOf())?this.getUTCFullYear()+"-"+f(this.getUTCMonth()+1)+"-"+f(this.getUTCDate())+"T"+f(this.getUTCHours())+":"+f(this.getUTCMinutes())+":"+f(this.getUTCSeconds())+"Z":null};String.prototype.toJSON=Number.prototype.toJSON=Boolean.prototype.toJSON=function(key){return this.valueOf()}}var cx=/[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,escapable=/[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,gap,indent,meta={"\b":"\\b","\t":"\\t","\n":"\\n","\f":"\\f","\r":"\\r",'"':'\\"',"\\":"\\\\"},rep;function quote(string){escapable.lastIndex=0;return escapable.test(string)?'"'+string.replace(escapable,function(a){var c=meta[a];return typeof c==="string"?c:"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)})+'"':'"'+string+'"'}function str(key,holder){var i,k,v,length,mind=gap,partial,value=holder[key];if(value&&typeof value==="object"&&typeof value.toJSON==="function"){value=value.toJSON(key)}if(typeof rep==="function"){value=rep.call(holder,key,value)}switch(typeof value){case"string":return quote(value);case"number":return isFinite(value)?String(value):"null";case"boolean":case"null":return String(value);case"object":if(!value){return"null"}gap+=indent;partial=[];if(Object.prototype.toString.apply(value)==="[object Array]"){length=value.length;for(i=0;i<length;i+=1){partial[i]=str(i,value)||"null"}v=partial.length===0?"[]":gap?"[\n"+gap+partial.join(",\n"+gap)+"\n"+mind+"]":"["+partial.join(",")+"]";gap=mind;return v}if(rep&&typeof rep==="object"){length=rep.length;for(i=0;i<length;i+=1){k=rep[i];if(typeof k==="string"){v=str(k,value);if(v){partial.push(quote(k)+(gap?": ":":")+v)}}}}else{for(k in value){if(Object.hasOwnProperty.call(value,k)){v=str(k,value);if(v){partial.push(quote(k)+(gap?": ":":")+v)}}}}v=partial.length===0?"{}":gap?"{\n"+gap+partial.join(",\n"+gap)+"\n"+mind+"}":"{"+partial.join(",")+"}";gap=mind;return v}}if(typeof JSON.stringify!=="function"){JSON.stringify=function(value,replacer,space){var i;gap="";indent="";if(typeof space==="number"){for(i=0;i<space;i+=1){indent+=" "}}else{if(typeof space==="string"){indent=space}}rep=replacer;if(replacer&&typeof replacer!=="function"&&(typeof replacer!=="object"||typeof replacer.length!=="number")){throw new Error("JSON.stringify")}return str("",{"":value})}}if(typeof JSON.parse!=="function"){JSON.parse=function(text,reviver){var j;function walk(holder,key){var k,v,value=holder[key];if(value&&typeof value==="object"){for(k in value){if(Object.hasOwnProperty.call(value,k)){v=walk(value,k);if(v!==undefined){value[k]=v}else{delete value[k]}}}}return reviver.call(holder,key,value)}text=String(text);cx.lastIndex=0;if(cx.test(text)){text=text.replace(cx,function(a){return"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)})}if(/^[\],:{}\s]*$/.test(text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g,"@").replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,"]").replace(/(?:^|:|,)(?:\s*\[)+/g,""))){j=eval("("+text+")");return typeof reviver==="function"?walk({"":j},""):j}throw new SyntaxError("JSON.parse")}}}());
//jquery fieldselection
(function(){var a={getSelection:function(){var b=this.jquery?this[0]:this;return(("selectionStart" in b&&function(){var c=b.selectionEnd-b.selectionStart;return{start:b.selectionStart,end:b.selectionEnd,length:c,text:b.value.substr(b.selectionStart,c)}})||(document.selection&&function(){b.focus();var d=document.selection.createRange();if(d==null){return{start:0,end:b.value.length,length:0}}var c=b.createTextRange();var e=c.duplicate();c.moveToBookmark(d.getBookmark());e.setEndPoint("EndToStart",c);return{start:e.text.length,end:e.text.length+d.text.length,length:d.text.length,text:d.text}})||function(){return{start:0,end:b.value.length,length:0}})()},replaceSelection:function(){var b=this.jquery?this[0]:this;var c=arguments[0]||"";return(("selectionStart" in b&&function(){b.value=b.value.substr(0,b.selectionStart)+c+b.value.substr(b.selectionEnd,b.value.length);return this})||(document.selection&&function(){b.focus();document.selection.createRange().text=c;return this})||function(){b.value+=c;return this})()}};jQuery.each(a,function(b){jQuery.fn[b]=this})})();
/**
 * AutoCompleter Object, refactored closure style from
 * jQuery autocomplete plugin
 * @param {Object=} options Settings
 * @constructor
 */
var AutoCompleter = function(options) {

    /**
     * Default options for autocomplete plugin
     */
    var defaults = {
        promptText: '',
        autocompleteMultiple: true,
        multipleSeparator: ' ',//a single character
        inputClass: 'acInput',
        loadingClass: 'acLoading',
        resultsClass: 'acResults',
        selectClass: 'acSelect',
        queryParamName: 'q',
        limitParamName: 'limit',
        extraParams: {},
        lineSeparator: '\n',
        cellSeparator: '|',
        minChars: 2,
        maxItemsToShow: 10,
        delay: 400,
        useCache: true,
        maxCacheLength: 10,
        matchSubset: true,
        matchCase: false,
        matchInside: true,
        mustMatch: false,
        preloadData: false,
        selectFirst: false,
        stopCharRegex: /\s+/,
        selectOnly: false,
        formatItem: null,           // TBD
        onItemSelect: false,
        autoFill: false,
        filterResults: true,
        sortResults: true,
        sortFunction: false,
        onNoMatch: false
    };

    /**
     * Options dictionary
     * @type Object
     * @private
     */
    this.options = $.extend({}, defaults, options);

    /**
     * Cached data
     * @type Object
     * @private
     */
    this.cacheData_ = {};

    /**
     * Number of cached data items
     * @type number
     * @private
     */
    this.cacheLength_ = 0;

    /**
     * Class name to mark selected item
     * @type string
     * @private
     */
    this.selectClass_ = 'jquery-autocomplete-selected-item';

    /**
     * Handler to activation timeout
     * @type ?number
     * @private
     */
    this.keyTimeout_ = null;

    /**
     * Last key pressed in the input field (store for behavior)
     * @type ?number
     * @private
     */
    this.lastKeyPressed_ = null;

    /**
     * Last value processed by the autocompleter
     * @type ?string
     * @private
     */
    this.lastProcessedValue_ = null;

    /**
     * Last value selected by the user
     * @type ?string
     * @private
     */
    this.lastSelectedValue_ = null;

    /**
     * Is this autocompleter active?
     * @type boolean
     * @private
     */
    this.active_ = false;

    /**
     * Is it OK to finish on blur?
     * @type boolean
     * @private
     */
    this.finishOnBlur_ = true;

    this._isRunning = false;

    this.options.minChars = parseInt(this.options.minChars, 10);
    if (isNaN(this.options.minChars) || this.options.minChars < 1) {
        this.options.minChars = 2;
    }

    this.options.maxItemsToShow = parseInt(this.options.maxItemsToShow, 10);
    if (isNaN(this.options.maxItemsToShow) || this.options.maxItemsToShow < 1) {
        this.options.maxItemsToShow = 10;
    }

    this.options.maxCacheLength = parseInt(this.options.maxCacheLength, 10);
    if (isNaN(this.options.maxCacheLength) || this.options.maxCacheLength < 1) {
        this.options.maxCacheLength = 10;
    }

    if (this.options['preloadData'] === true){
        this.fetchRemoteData('', function(){});
    }
};
inherits(AutoCompleter, WrappedElement);

AutoCompleter.prototype.decorate = function(element){

    /**
     * Init DOM elements repository
     */
    this._element = element;

    /**
     * Switch off the native autocomplete
     */
    this._element.attr('autocomplete', 'off');

    /**
     * Set prompt text
     */
    if (this.options['promptText']) {
        this.setPrompt();
    }

    /**
     * Create DOM element to hold results
     */
    this._results = $('<div></div>').hide();
    if (this.options.resultsClass) {
        this._results.addClass(this.options.resultsClass);
    }
    this._results.css({
        position: 'absolute'
    });
    $('body').append(this._results);

    this.setEventHandlers();
};

AutoCompleter.prototype.setPrompt = function() {
    this._element.val(this.options['promptText']);
    this._element.addClass('prompt');
};

AutoCompleter.prototype.removePrompt = function() {
    if (this._element.hasClass('prompt')) {
        this._element.removeClass('prompt');
        var val = this._element.val();
        if (val === this.options['promptText']) {
            this._element.val('');
        }
    }
};

AutoCompleter.prototype.setEventHandlers = function(){
    /**
     * Shortcut to self
     */
    var self = this;

    /**
     * Attach keyboard monitoring to $elem
     */
    self._element.keydown(function(e) {

        self.removePrompt();

        self.lastKeyPressed_ = e.keyCode;
        switch(self.lastKeyPressed_) {

            case 38: // up
                e.preventDefault();
                if (self.active_) {
                    self.focusPrev();
                } else {
                    self.activate();
                }
                return false;
            break;

            case 40: // down
                e.preventDefault();
                if (self.active_) {
                    self.focusNext();
                } else {
                    self.activate();
                }
                return false;
            break;

            case 9: // tab
            case 13: // return
                if (self.active_) {
                    e.preventDefault();
                    self.selectCurrent();
                    return false;
                }
            break;

            case 27: // escape
                if ($.trim(self._element.val()) === '') {
                    self._element.blur();
                    return false;
                }
                if (self.active_) {
                    e.preventDefault();
                    self.finish();
                    return false;
                }
            break;

            default:
                self.activate();

        }
    });
    self._element.focus(function() {
        self.removePrompt();
    });
    self._element.blur(function() {
        if ($.trim(self._element.val()) === '') {
            self.setPrompt();
            self._results.hide();
            return true;
        }
        if (self.finishOnBlur_) {
            setTimeout(function() { self.finish(); }, 200);
        }
    });
};

AutoCompleter.prototype.position = function() {
    var offset = this._element.offset();
    this._results.css({
        top: offset.top + this._element.outerHeight(),
        left: offset.left
    });
};

AutoCompleter.prototype.cacheRead = function(filter) {
    var filterLength, searchLength, search, maxPos, pos;
    if (this.options.useCache) {
        filter = String(filter);
        filterLength = filter.length;
        if (this.options.matchSubset) {
            searchLength = 1;
        } else {
            searchLength = filterLength;
        }
        while (searchLength <= filterLength) {
            if (this.options.matchInside) {
                maxPos = filterLength - searchLength;
            } else {
                maxPos = 0;
            }
            pos = 0;
            while (pos <= maxPos) {
                search = filter.substr(0, searchLength);
                if (this.cacheData_[search] !== undefined) {
                    return this.cacheData_[search];
                }
                pos++;
            }
            searchLength++;
        }
    }
    return false;
};

AutoCompleter.prototype.cacheWrite = function(filter, data) {
    if (this.options.useCache) {
        if (this.cacheLength_ >= this.options.maxCacheLength) {
            this.cacheFlush();
        }
        filter = String(filter);
        if (this.cacheData_[filter] !== undefined) {
            this.cacheLength_++;
        }
        return this.cacheData_[filter] = data;
    }
    return false;
};

AutoCompleter.prototype.cacheFlush = function() {
    this.cacheData_ = {};
    this.cacheLength_ = 0;
};

AutoCompleter.prototype.callHook = function(hook, data) {
    var f = this.options[hook];
    if (f && $.isFunction(f)) {
        return f(data, this);
    }
    return false;
};

AutoCompleter.prototype.activate = function() {
    var self = this;
    var activateNow = function() {
        self.activateNow();
    };
    var delay = parseInt(this.options.delay, 10);
    if (isNaN(delay) || delay <= 0) {
        delay = 250;
    }
    if (this.keyTimeout_) {
        clearTimeout(this.keyTimeout_);
    }
    this.keyTimeout_ = setTimeout(activateNow, delay);
};

AutoCompleter.prototype.activateNow = function() {
    if (this._isRunning) {
        return;
    }
    var value = this.getValue();
    if (value.length === 0) {
        this.finish();
    }
    if (value !== this.lastProcessedValue_ && value !== this.lastSelectedValue_) {
        if (value.length >= this.options.minChars) {
            this.active_ = true;
            this.lastProcessedValue_ = value;
            this.fetchData(value);
        }
    }
};

AutoCompleter.prototype.setIsRunning = function(isRunning) {
    this._isRunning = isRunning;
};

AutoCompleter.prototype.fetchData = function(value) {
    var self = this;
    this.fetchRemoteData(value, function(remoteData) {
        self.filterAndShowResults(remoteData, value);
    });
};

AutoCompleter.prototype.fetchRemoteData = function(filter, callback) {
    var data = this.cacheRead(filter);
    if (data) {
        callback(data);
    } else {
        var self = this;
        if (this._element){
            this._element.addClass(this.options.loadingClass);
        }
        var ajaxCallback = function(data) {
            var parsed = false;
            if (data !== false) {
                parsed = self.parseRemoteData(data);
                self.options.data = parsed;//cache data forever - E.F.
                self.cacheWrite(filter, parsed);
            }
            if (self._element){
                self._element.removeClass(self.options.loadingClass);
            }
            callback(parsed);
        };
        $.ajax({
            url: this.makeUrl(filter),
            success: function(data) {
                ajaxCallback(data);
                self.setIsRunning(false);
                //if query changed - rerun the search immediately
                var newQuery = self.getValue();
                if (newQuery && newQuery !== filter) {
                    self.activateNow();
                }
            },
            error: function() {
                ajaxCallback(false);
                self.setIsRunning(false);
            }
        });
        self.setIsRunning(true);
    }
};

AutoCompleter.prototype.setOption = function(name, value){
    this.options[name] = value;
};

AutoCompleter.prototype.setExtraParam = function(name, value) {
    var index = $.trim(String(name));
    if (index) {
        if (!this.options.extraParams) {
            this.options.extraParams = {};
        }
        if (this.options.extraParams[index] !== value) {
            this.options.extraParams[index] = value;
            this.cacheFlush();
        }
    }
};

AutoCompleter.prototype.makeUrl = function(param) {
    var self = this;
    var url = this.options.url;
    var params = $.extend({}, this.options.extraParams);
    // If options.queryParamName === false, append query to url
    // instead of using a GET parameter
    if (this.options.queryParamName === false) {
        url += encodeURIComponent(param);
    } else {
        params[this.options.queryParamName] = param;
    }

    if (this.options.limitParamName && this.options.maxItemsToShow) {
        params[this.options.limitParamName] = this.options.maxItemsToShow;
    }

    var urlAppend = [];
    $.each(params, function(index, value) {
        urlAppend.push(self.makeUrlParam(index, value));
    });
    if (urlAppend.length) {
        url += url.indexOf('?') == -1 ? '?' : '&';
        url += urlAppend.join('&');
    }
    return url;
};

AutoCompleter.prototype.makeUrlParam = function(name, value) {
    return String(name) + '=' + encodeURIComponent(value);
};

/**
 * Sanitize CR and LF, then split into lines
 */
AutoCompleter.prototype.splitText = function(text) {
    return String(text).replace(/(\r\n|\r|\n)/g, '\n').split(this.options.lineSeparator);
};

AutoCompleter.prototype.parseRemoteData = function(remoteData) {
    var value, lines, i, j, data;
    var results = [];
    var lines = this.splitText(remoteData);
    for (i = 0; i < lines.length; i++) {
        var line = lines[i].split(this.options.cellSeparator);
        data = [];
        for (j = 0; j < line.length; j++) {
            data.push(unescape(line[j]));
        }
        value = data.shift();
        results.push({ value: unescape(value), data: data });
    }
    return results;
};

AutoCompleter.prototype.filterAndShowResults = function(results, filter) {
    this.showResults(this.filterResults(results, filter), filter);
};

AutoCompleter.prototype.filterResults = function(results, filter) {

    var filtered = [];
    var value, data, i, result, type, include;
    var regex, pattern, testValue;

    for (i = 0; i < results.length; i++) {
        result = results[i];
        type = typeof result;
        if (type === 'string') {
            value = result;
            data = {};
        } else if ($.isArray(result)) {
            value = result[0];
            data = result.slice(1);
        } else if (type === 'object') {
            value = result.value;
            data = result.data;
        }
        value = String(value);
        if (value > '') {
            if (typeof data !== 'object') {
                data = {};
            }
            if (this.options.filterResults) {
                pattern = String(filter);
                testValue = String(value);
                if (!this.options.matchCase) {
                    pattern = pattern.toLowerCase();
                    testValue = testValue.toLowerCase();
                }
                include = testValue.indexOf(pattern);
                if (this.options.matchInside) {
                    include = include > -1;
                } else {
                    include = include === 0;
                }
            } else {
                include = true;
            }
            if (include) {
                filtered.push({ value: value, data: data });
            }
        }
    }

    if (this.options.sortResults) {
        filtered = this.sortResults(filtered, filter);
    }

    if (this.options.maxItemsToShow > 0 && this.options.maxItemsToShow < filtered.length) {
        filtered.length = this.options.maxItemsToShow;
    }

    return filtered;

};

AutoCompleter.prototype.sortResults = function(results, filter) {
    var self = this;
    var sortFunction = this.options.sortFunction;
    if (!$.isFunction(sortFunction)) {
        sortFunction = function(a, b, f) {
            return self.sortValueAlpha(a, b, f);
        };
    }
    results.sort(function(a, b) {
        return sortFunction(a, b, filter);
    });
    return results;
};

AutoCompleter.prototype.sortValueAlpha = function(a, b, filter) {
    a = String(a.value);
    b = String(b.value);
    if (!this.options.matchCase) {
        a = a.toLowerCase();
        b = b.toLowerCase();
    }
    if (a > b) {
        return 1;
    }
    if (a < b) {
        return -1;
    }
    return 0;
};

AutoCompleter.prototype.showResults = function(results, filter) {
    var self = this;
    var $ul = $('<ul></ul>');
    var i, result, $li, extraWidth, first = false, $first = false;
    var numResults = results.length;
    for (i = 0; i < numResults; i++) {
        result = results[i];
        $li = $('<li>' + this.showResult(result.value, result.data) + '</li>');
        $li.data('value', result.value);
        $li.data('data', result.data);
        $li.click(function() {
            var $this = $(this);
            self.selectItem($this);
        }).mousedown(function() {
            self.finishOnBlur_ = false;
        }).mouseup(function() {
            self.finishOnBlur_ = true;
        });
        $ul.append($li);
        if (first === false) {
            first = String(result.value);
            $first = $li;
            $li.addClass(this.options.firstItemClass);
        }
        if (i == numResults - 1) {
            $li.addClass(this.options.lastItemClass);
        }
    }

    // Alway recalculate position before showing since window size or
    // input element location may have changed. This fixes #14
    this.position();

    this._results.html($ul).show();
    extraWidth = this._results.outerWidth() - this._results.width();
    this._results.width(this._element.outerWidth() - extraWidth);
    $('li', this._results).hover(
        function() { self.focusItem(this); },
        function() { /* void */ }
    );
    if (this.autoFill(first, filter)) {
        this.focusItem($first);
    }
};

AutoCompleter.prototype.showResult = function(value, data) {
    if ($.isFunction(this.options.showResult)) {
        return this.options.showResult(value, data);
    } else {
        return value;
    }
};

AutoCompleter.prototype.autoFill = function(value, filter) {
    var lcValue, lcFilter, valueLength, filterLength;
    if (this.options.autoFill && this.lastKeyPressed_ != 8) {
        lcValue = String(value).toLowerCase();
        lcFilter = String(filter).toLowerCase();
        valueLength = value.length;
        filterLength = filter.length;
        if (lcValue.substr(0, filterLength) === lcFilter) {
            this._element.val(value);
            this.selectRange(filterLength, valueLength);
            return true;
        }
    }
    return false;
};

AutoCompleter.prototype.focusNext = function() {
    this.focusMove(+1);
};

AutoCompleter.prototype.focusPrev = function() {
    this.focusMove(-1);
};

AutoCompleter.prototype.focusMove = function(modifier) {
    var i, $items = $('li', this._results);
    modifier = parseInt(modifier, 10);
    for (var i = 0; i < $items.length; i++) {
        if ($($items[i]).hasClass(this.selectClass_)) {
            this.focusItem(i + modifier);
            return;
        }
    }
    this.focusItem(0);
};

AutoCompleter.prototype.focusItem = function(item) {
    var $item, $items = $('li', this._results);
    if ($items.length) {
        $items.removeClass(this.selectClass_).removeClass(this.options.selectClass);
        if (typeof item === 'number') {
            item = parseInt(item, 10);
            if (item < 0) {
                item = 0;
            } else if (item >= $items.length) {
                item = $items.length - 1;
            }
            $item = $($items[item]);
        } else {
            $item = $(item);
        }
        if ($item) {
            $item.addClass(this.selectClass_).addClass(this.options.selectClass);
        }
    }
};

AutoCompleter.prototype.selectCurrent = function() {
    var $item = $('li.' + this.selectClass_, this._results);
    if ($item.length == 1) {
        this.selectItem($item);
    } else {
        this.finish();
    }
};

AutoCompleter.prototype.selectItem = function($li) {
    var value = $li.data('value');
    var data = $li.data('data');
    var displayValue = this.displayValue(value, data);
    this.lastProcessedValue_ = displayValue;
    this.lastSelectedValue_ = displayValue;

    this.setValue(displayValue);

    this.setCaret(displayValue.length);
    this.callHook('onItemSelect', { value: value, data: data });
    this.finish();
};

/**
 * @return {boolean} true if the symbol matches something that is
 *                   considered content and false otherwise
 * @param {string} symbol - a single char string
 */
AutoCompleter.prototype.isContentChar = function(symbol){
    if (this.options['stopCharRegex'] && symbol.match(this.options['stopCharRegex'])){
        return false;
    } else if (symbol === this.options['multipleSeparator']){
        return false;
    } else {
        return true;
    }
};

/**
 * takes value from the input box
 * and saves _selection_start and _selection_end coordinates
 * respects settings autocompleteMultiple and
 * multipleSeparator
 * @return {string} the current word in the 
 * autocompletable word
 */
AutoCompleter.prototype.getValue = function(){
    if (this._element === undefined) {
        return '';
    }
    var sel = this._element.getSelection();
    var text = this._element.val();
    var pos = sel.start;//estimated start
    //find real start
    var start = pos;
    for (cpos = pos; cpos >= 0; cpos = cpos - 1){
        if (cpos === text.length){
            continue;
        }
        var symbol = text.charAt(cpos);
        if (!this.isContentChar(symbol)){
            break;
        }
        start = cpos;
    }
    //find real end
    var end = pos;
    for (cpos = pos; cpos < text.length; cpos = cpos + 1){
        if (cpos === 0){
            continue;
        }
        var symbol = text.charAt(cpos);
        if (!this.isContentChar(symbol)){
            break;
        }
        end = cpos;
    }
    this._selection_start = start;
    this._selection_end = end;
    return text.substring(start, end);
}

/** 
 * sets value of the input box
 * by replacing the previous selection
 * with the value from the autocompleter
 */
AutoCompleter.prototype.setValue = function(val){
    var prefix = this._element.val().substring(0, this._selection_start);
    var postfix = this._element.val().substring(this._selection_end + 1);
    this._element.val(prefix + val + postfix);
};

AutoCompleter.prototype.displayValue = function(value, data) {
    if ($.isFunction(this.options.displayValue)) {
        return this.options.displayValue(value, data);
    } else {
        return value;
    }
};

AutoCompleter.prototype.clear = function() {
    this._element.val('');
    this._results.hide();
    this.lastKeyPressed_ = null;
    this.lastProcessedValue_ = null;
    if (this._keyTimeout_) {
        clearTimeout(this._keyTimeout);
    }
    this._active = false;
};

AutoCompleter.prototype.finish = function() {
    if (this.keyTimeout_) {
        clearTimeout(this.keyTimeout_);
    }
    if (this._element.val() !== this.lastSelectedValue_) {
        if (this.options.mustMatch) {
            this._element.val('');
        }
        this.callHook('onNoMatch');
    }
    this._results.hide();
    this.lastKeyPressed_ = null;
    this.lastProcessedValue_ = null;
    if (this.active_) {
        this.callHook('onFinish');
    }
    this.active_ = false;
};

AutoCompleter.prototype.selectRange = function(start, end) {
    var input = this._element.get(0);
    if (input.setSelectionRange) {
        input.focus();
        input.setSelectionRange(start, end);
    } else if (this.createTextRange) {
        var range = this.createTextRange();
        range.collapse(true);
        range.moveEnd('character', end);
        range.moveStart('character', start);
        range.select();
    }
};

AutoCompleter.prototype.setCaret = function(pos) {
    this.selectRange(pos, pos);
};

(function($){function isRGBACapable(){var $script=$("script:first"),color=$script.css("color"),result=false;if(/^rgba/.test(color)){result=true}else{try{result=(color!=$script.css("color","rgba(0, 0, 0, 0.5)").css("color"));$script.css("color",color)}catch(e){}}return result}$.extend(true,$,{support:{rgba:isRGBACapable()}});var properties=["color","backgroundColor","borderBottomColor","borderLeftColor","borderRightColor","borderTopColor","outlineColor"];$.each(properties,function(i,property){$.fx.step[property]=function(fx){if(!fx.init){fx.begin=parseColor($(fx.elem).css(property));fx.end=parseColor(fx.end);fx.init=true}fx.elem.style[property]=calculateColor(fx.begin,fx.end,fx.pos)}});$.fx.step.borderColor=function(fx){if(!fx.init){fx.end=parseColor(fx.end)}var borders=properties.slice(2,6);$.each(borders,function(i,property){if(!fx.init){fx[property]={begin:parseColor($(fx.elem).css(property))}}fx.elem.style[property]=calculateColor(fx[property].begin,fx.end,fx.pos)});fx.init=true};function calculateColor(begin,end,pos){var color="rgb"+($.support.rgba?"a":"")+"("+parseInt((begin[0]+pos*(end[0]-begin[0])),10)+","+parseInt((begin[1]+pos*(end[1]-begin[1])),10)+","+parseInt((begin[2]+pos*(end[2]-begin[2])),10);if($.support.rgba){color+=","+(begin&&end?parseFloat(begin[3]+pos*(end[3]-begin[3])):1)}color+=")";return color}function parseColor(color){var match,triplet;if(match=/#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})/.exec(color)){triplet=[parseInt(match[1],16),parseInt(match[2],16),parseInt(match[3],16),1]}else{if(match=/#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])/.exec(color)){triplet=[parseInt(match[1],16)*17,parseInt(match[2],16)*17,parseInt(match[3],16)*17,1]}else{if(match=/rgb\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*\)/.exec(color)){triplet=[parseInt(match[1]),parseInt(match[2]),parseInt(match[3]),1]}else{if(match=/rgba\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9\.]*)\s*\)/.exec(color)){triplet=[parseInt(match[1],10),parseInt(match[2],10),parseInt(match[3],10),parseFloat(match[4])]}else{if(color=="transparent"){triplet=[0,0,0,0]}}}}}return triplet}})(jQuery);

/**
 * Timeago is a jQuery plugin that makes it easy to support automatically
 * updating fuzzy timestamps (e.g. "4 minutes ago" or "about 1 day ago").
 *
 * @name timeago
 * @version 0.11.1
 * @requires jQuery v1.2.3+
 * @author Ryan McGeary
 * @license MIT License - http://www.opensource.org/licenses/mit-license.php
 *
 * For usage and examples, visit:
 * http://timeago.yarp.com/
 *
 * Copyright (c) 2008-2011, Ryan McGeary (ryanonjavascript -[at]- mcgeary [*dot*] org)
 */
(function($) {
  $.timeago = function(timestamp) {
    if (timestamp instanceof Date) {
      return inWords(timestamp);
    } else if (typeof timestamp === "string") {
      return inWords($.timeago.parse(timestamp));
    } else {
      return inWords($.timeago.datetime(timestamp));
    }
  };
  var $t = $.timeago;

  $.extend($.timeago, {
    settings: {
      refreshMillis: 60000,
      allowFuture: false,
      strings: {
        prefixAgo: null,
        prefixFromNow: null,
        suffixAgo: gettext("ago"),
        suffixFromNow: gettext("from now"),
        seconds: gettext("just now"),
        minute: gettext("about a minute"),
        minutes: gettext("%d minutes"),
        hour: gettext("about an hour"),
        hours: gettext("%d hours"),
        day: gettext("yesterday"),
        days: gettext("%d days"),
        month: gettext("about a month"),
        months: gettext("%d months"),
        year: gettext("about a year"),
        years: gettext("%d years"),
        wordSeparator: " ",
        numbers: []
      }
    },
    inWords: function(distanceMillis) {
      var $l = this.settings.strings;
      var prefix = $l.prefixAgo;
      var suffix = $l.suffixAgo;
      if (this.settings.allowFuture) {
        if (distanceMillis < 0) {
          prefix = $l.prefixFromNow;
          suffix = $l.suffixFromNow;
        }
      }

      var seconds = Math.abs(distanceMillis) / 1000;
      var minutes = seconds / 60;
      var hours = minutes / 60;
      var days = hours / 24;
      var years = days / 365;

      function substitute(stringOrFunction, number) {
        var string = $.isFunction(stringOrFunction) ? stringOrFunction(number, distanceMillis) : stringOrFunction;
        var value = ($l.numbers && $l.numbers[number]) || number;
        return string.replace(/%d/i, value);
      }

      var words = seconds < 45 && substitute($l.seconds, Math.round(seconds)) ||
        seconds < 90 && substitute($l.minute, 1) ||
        minutes < 45 && substitute($l.minutes, Math.round(minutes)) ||
        minutes < 90 && substitute($l.hour, 1) ||
        hours < 24 && substitute($l.hours, Math.round(hours)) ||
        hours < 42 && substitute($l.day, 1) ||
        days < 30 && substitute($l.days, Math.round(days)) ||
        days < 45 && substitute($l.month, 1) ||
        days < 365 && substitute($l.months, Math.round(days / 30)) ||
        years < 1.5 && substitute($l.year, 1) ||
        substitute($l.years, Math.round(years));

      var separator = $l.wordSeparator === undefined ?  " " : $l.wordSeparator;
      return $.trim([prefix, words, suffix].join(separator));
    },
    parse: function(iso8601) {
      var s = $.trim(iso8601);
      s = s.replace(/\.\d\d\d+/,""); // remove milliseconds
      s = s.replace(/-/,"/").replace(/-/,"/");
      s = s.replace(/T/," ").replace(/Z/," UTC");
      s = s.replace(/([\+\-]\d\d)\:?(\d\d)/," $1$2"); // -04:00 -> -0400
      return new Date(s);
    },
    datetime: function(elem) {
      // jQuery's `is()` doesn't play well with HTML5 in IE
      var isTime = $(elem).get(0).tagName.toLowerCase() === "time"; // $(elem).is("time");
      var iso8601 = isTime ? $(elem).attr("datetime") : $(elem).attr("title");
      return $t.parse(iso8601);
    }
  });

  $.fn.timeago = function() {
    var self = this;
    self.each(refresh);

    var $s = $t.settings;
    if ($s.refreshMillis > 0) {
      setInterval(function() { self.each(refresh); }, $s.refreshMillis);
    }
    return self;
  };

  function refresh() {
    var data = prepareData(this);
    if (!isNaN(data.datetime)) {
      $(this).text(inWords(data.datetime));
    }
    return this;
  }

  function prepareData(element) {
    element = $(element);
    if (!element.data("timeago")) {
      element.data("timeago", { datetime: $t.datetime(element) });
      var text = $.trim(element.text());
      if (text.length > 0) {
        element.attr("title", text);
      }
    }
    return element.data("timeago");
  }

  function inWords(date) {
    var distanceMillis = distance(date);
    var seconds = Math.abs(distanceMillis) / 1000;
    var minutes = seconds / 60;
    var hours = minutes / 60;
    var days = hours / 24;
    var years = days / 365;
    var months = [
        gettext('Jan'),
        gettext('Feb'),
        gettext('Mar'),
        gettext('Apr'),
        gettext('May'),
        gettext('Jun'),
        gettext('Jul'),
        gettext('Aug'),
        gettext('Sep'),
        gettext('Oct'),
        gettext('Nov'),
        gettext('Dec')
    ];
    //todo: rewrite this in javascript
    if (days > 2){
        var month_date = months[date.getMonth()] + ' ' + date.getDate()
        if (years == 0){
            //how to do this in js???
            return month_date;
        } else {
            return month_date + ' ' + "'" + date.getYear() % 20;
        }
    } else if (days == 2) {
        return gettext('2 days ago')
    } else if (days == 1) {
        return gettext('yesterday')
    } else if (minutes >= 60) {
        var wholeHours = Math.floor(hours);
        return interpolate(
                    ngettext(
                        '%s hour ago',
                        '%s hours ago',
                        wholeHours
                    ),
                    [wholeHours,]
                )
    } else if (seconds > 90){
        var wholeMinutes = Math.floor(minutes);
        return interpolate(
                    ngettext(
                        '%s min ago',
                        '%s mins ago',
                        wholeMinutes
                    ),
                    [wholeMinutes,]
                )
    } else {
        return gettext('just now')
    }
  }

  function distance(date) {
    return (new Date() - date);
  }

  // fix for IE6 suckage
  document.createElement("abbr");
  document.createElement("time");
}(jQuery));
