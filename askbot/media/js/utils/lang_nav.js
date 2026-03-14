/**
 * Switches the UI language while keeping user on the same
 * page
 */
var LangNav = function() {
    WrappedElement.call(this);
};
inherits(LangNav, WrappedElement);

LangNav.prototype.translateUrl = function(url, lang) {
    var result;
    $.ajax({
        type: 'GET',
        url: askbot['urls']['translateUrl'],
        data: {'url': url, 'language': lang },
        async: false, //important!
        cache: false,
        dataType: 'json',
        success: function(data) {
            if (data['url']) {
                result = data['url'];
            }
        }
    });
    return result;
};

LangNav.prototype.handleUrl = function(url) {
    window.location.href = url;
};

LangNav.prototype.getNavHandler = function(link) {
    var me = this;
    return function() {
        var lang = link.data('lang');
        var url = window.location.pathname;
        //resolve url in current language
        url = me.translateUrl(url, lang) || link.attr('href');
        me.handleUrl(url, lang);
        //if resolution is successful, redirect to that url
        return false;
    };
};

LangNav.prototype.decorate = function(element) {
    this._element = element;
    var links = element.find('li>a');
    var len = links.length;
    for (var i=0; i<len; i++) {
        var link = $(links[i]);
        setupButtonEventHandlers(link, this.getNavHandler(link));
    }
};
