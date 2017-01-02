/**
 * attention - this function needs to be retired
 * as it cannot accurately give url to the media file
 */
var mediaUrl = function (resource) {
    return askbot.settings.static_url + 'default' + '/' + resource;
};

/** todo: look up available alternatives
 * this makes assumption that url is path?param1=value1&param2=value2...
 * no other forms are parsed
 * returns an array with two elements:
 * (1) - path, (2) - dictionary of params
 */
var parseUrl = function (url) {
    var urlParts = url.split('?');
    if (urlParts.length == 1) {
        return [url, undefined];
    } else {
        var paramsString = urlParts[1];
        var paramsParts = paramsString.split('&');
        var numParts = paramsParts.length;
        var params = {};
        for (var i=0; i<numParts; i++) {
            var pair = paramsParts[i].split('=');
            params[pair[0]] = pair[1];
        }
        return [urlParts[0], params];
    }
};

var getObjectByPath = function (path) {
    var bits = path.split('.');
    var obj = window;
    var numBits = bits.length;
    for (var i=0; i<numBits; i++) {
        obj = obj[bits[i]];
    }
    return obj;
};

var getCookie = function (name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = $.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
    }
    return cookieValue;
};

var getFontProps =  function (elm) {
    return {
        'line-height': elm.css('lineHeight'),
        'font-size': elm.css('fontSize'),
        'font-style': elm.css('fontStyle'),
        'font-variant': elm.css('fontVariant'),
        'font-family': elm.css('fontFamily'),
        'font-weight': elm.css('fontWeight')
    }
};

var csrfSafeMethod = function(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
};

var sameOrigin = function(url) {
    var host = document.location.host;
    var protocol = document.location.protocol;
    var sr_origin = '//' + host;
    var origin = protocol + sr_origin;
    return (
        (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
        (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
        !(/^(\/\/|http:|https:).*/.test(url))

    );
};

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
            // Send the token to same-origin, relative URLs only.
            // Send the token only if the method warrants CSRF protection
            // Using the CSRFToken value acquired earlier
            var csrfCookieName = askbot['settings']['csrfCookieName'];
            xhr.setRequestHeader("X-CSRFToken", getCookie(csrfCookieName));
        }
    }
});


/**
 * Selects template by class
 * template selector must be a simple class selector
 * e.g. .comment
 */
var getTemplate = function (templateSelector) {
    var templates = $('.js-templates');
    return templates.find(templateSelector).clone(false);
};

var cleanUrl = function (url) {
    var re = new RegExp('//', 'g');
    return url.replace(re, '/');
};

var copyAltToTitle = function (sel) {
    sel.attr('title', sel.attr('alt'));
};

var runMathJax = function () {
    if (typeof MathJax != 'undefined') {
        MathJax.Hub.Queue(['Typeset', MathJax.Hub]);
    } else {
        console.log('Could not load mathjax');
    }
};

/**
 * @returns jQuery with same content and classes,
 * but different tag name (DOM node name)
 */
var setHtmlTag = function (fromElement, toTagName) {
    if (fromElement.attr('tagName') === toTagName.toUpperCase()) {
        return fromElement;
    }
    var newElement = $('<' + toTagName + '></' + toTagName + '>');
    //copy classes
    newElement.attr('class', fromElement.attr('class'));
    //move contents
    fromElement.children().detach().appendTo(newElement);
    //@todo: maybe copy event handlers
    //if element is in dom, insert new element and detach old element
    if ($(document).find(fromElement)) {
        fromElement.after(newElement);
        fromElement.remove();
    }
    return newElement;
};

var stripTags = function(html) {
    var div = $('<div style="margin-left: -999em; position: absolute;"></div>');
    $(document.body).append(div);
    div.html(html);
    var text = div.text();
    div.remove();
    return text
};

var animateHashes = function () {
    var id_value = window.location.hash;
    if (id_value !== '') {
        var previous_color = $(id_value).css('background-color');
        $(id_value).css('backgroundColor', '#FFF8C6');
        $(id_value)
            .animate({backgroundColor: '#ff7f2a'}, 500)
            .animate({backgroundColor: '#FFF8C6'}, 500, function () {
                $(id_value).css('backgroundColor', previous_color);
            });
    }
};

var addExtraCssClasses = function (element, setting) {
    if (askbot.css && askbot.css[setting]) {
        element.addClass(askbot.css[setting]);
    }
};

/**
 * @param {string} id_token - any token
 * @param {string} unique_seed - the unique part
 * @returns {string} unique id that can be used in DOM
 */
var askbotMakeId = function (id_token, unique_seed) {
    if (unique_seed) {
        return id_token + '-' + unique_seed;
    }
    return id_token;
};

var getNewUniqueInt = function () {
    var num = askbot.data.uniqueInt || 0;
    num = num + 1;
    askbot.data.uniqueInt = num;
    return num;
};

/**
 * generic tag cleaning function, settings
 * are from askbot live settings and askbot.const
 */
var cleanTag = function (tag_name, settings) {
    var firstChar = tag_name.substring(0, 1);
    if (settings.tag_forbidden_first_chars.indexOf(firstChar) > -1) {
        throw settings.messages.wrong_first_char;
    }

    var max_length = settings.max_tag_length;
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
    if (settings.force_lowercase_tags) {
        return tag_name.toLowerCase();
    } else {
        return tag_name;
    }
};


var getSingletonController = function (ControllerClass, name) {
    askbot.controllers = askbot.controllers || {};
    var controller = askbot.controllers[name];
    if (controller === undefined) {
        controller = new ControllerClass();
        askbot.controllers[name] = controller;
    }
    return controller;
};

var setController = function (controller, name) {
    askbot.controllers = askbot.controllers || {};
    askbot.controllers[name] = controller;
};

var sortChildNodes = function (node, cmpFunc) {
    var items = node.children().sort(cmpFunc);
    node.append(items);
};

var getUniqueValues = function (values) {
    var uniques = {};
    var out = [];
    $.each(values, function (idx, value) {
        if (!(value in uniques)) {
            uniques[value] = 1;
            out.push(value);
        }
    });
    return out;
};

var getUniqueWords = function (value) {
    var words = $.trim(value).split(/\s+/);
    return getUniqueValues(words);
};

/**
 * comma-joins items and uses "and'
 * between the last and penultimate items
 * @param {Array<string>} values
 * @return {string}
 */
var joinAsPhrase = function (values) {
    var count = values.length;
    if (count === 0) {
        return '';
    } else if (count === 1) {
        return values[0];
    } else {
        var last = values.pop();
        var prev = values.pop();
        return values.join(', ') + prev + ' ' + gettext('and') + ' ' + last;
    }
};

/**
 * @return {boolean}
 */
var inArray = function (item, itemsList) {
    for (var i = 0; i < itemsList.length; i++) {
        if (item === itemsList[i]) {
            return true;
        }
    }
    return false;
};

var showMessage = function (element, msg, where) {
    var div = $('<div class="vote-notification"><h3>' + msg + '</h3>(' +
    gettext('click to close') + ')</div>');
    where = where || 'parent';

    div.click(function (event) {
        if (event.target.nodeName === 'A') {
            return true;
        }
        $('.vote-notification').fadeOut('fast', function () { $(this).remove(); });
        return false;
    });

    if (where === 'parent') {
        element.parent().append(div);
    } else {
        element.after(div);
    }

    div.fadeIn('fast');
};

//outer html hack - https://github.com/brandonaaron/jquery-outerhtml/
(function ($) {
    var div;
    $.fn.outerHTML = function () {
        var elem = this[0],
        tmp;
        return !elem ? null
        : typeof (tmp = elem.outerHTML) === 'string' ? tmp
        : (div = div || $('<div/>')).html(this.eq(0).clone()).html();
    };
})(jQuery);

/**
 * @return {number} key code of the event or `undefined`
 */
var getKeyCode = function (e) {
    if (e.which) {
        return e.which;
    } else if (e.keyCode) {
        return e.keyCode;
    }
    return undefined;
};

var makeKeyHandler = function (key, callback) {
    return function (e) {
        if ((e.which && e.which === key) || (e.keyCode && e.keyCode === key)) {
            if (!e.shiftKey) {
                callback(e);
                return false;
            }
        }
    };
};


var setupButtonEventHandlers = function (button, callback) {
    button.keydown(makeKeyHandler(13, callback));
    button.click(callback);
};

var removeButtonEventHandlers = function (button) {
    button.unbind('click');
    button.unbind('keydown');
};

var decodeHtml = function (encodedText) {
    return $('<div/>').html(encodedText).text();
};

var putCursorAtEnd = function (element) {
    var el = $(element).get()[0];
    var jEl = $(el);
    if (el.setSelectionRange) {
        var len = jEl.val().length * 2;
        el.setSelectionRange(len, len);
    } else {
        jEl.val(jEl.val());
    }
    jEl.scrollTop(999999);
};

var setCheckBoxesIn = function (selector, value) {
    return $(selector + '> input[type=checkbox]').attr('checked', value);
};

/*
 * Old style notify handler
 */
var notify = (function () {
    var visible = false;
    return {
        show: function (html, autohide) {
            if (html) {
                $('body').addClass('user-messages');
                var par = $('<p class="notification"></p>');
                par.html(html);
                $('.notify').prepend(par);
            }
            $('.notify').fadeIn('slow');
            visible = true;
            if (autohide) {
                setTimeout(
                    function () {
                        notify.close(false);
                        notify.clear();
                    },
                    3000
                );
            }
        },
        clear: function () {
            $('.notify').empty();
        },
        close: function (doPostback) {
            if (doPostback) {
                $.post(
                    askbot.urls.mark_read_message,
                    { formdata: 'required' }
                );
            }
            $('.notify').fadeOut('fast');
            $('body').removeClass('user-messages');
            visible = false;
        },
        isVisible: function () { return visible; }
    };
})();

/* **************************************************** */

/* some google closure-like code for the ui elements */
var inherits = function (ChildCtor, ParentCtor) {
    /** @constructor taken from google closure */
    function TempCtor() {}

    TempCtor.prototype = ParentCtor.prototype;
    ChildCtor.superClass_ = ParentCtor.prototype;
    ChildCtor.prototype = new TempCtor();
    ChildCtor.prototype.constructor = ChildCtor;
};

var getSuperClass = function (cls) {
    return cls.superClass_;
};

