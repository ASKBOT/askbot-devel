/**
 * Per-message DOM atom rendered by notify.show().
 *
 * Mirrors the per-message subtree of the system_messages Jinja
 * component so AJAX and server-rendered banners share the same
 * DOM shape. html is interpreted as HTML (jQuery .html());
 * callers are responsible for sanitization.
 */
var SystemMessage = function (html, id) {
    WrappedElement.call(this);
    this._html = html;
    this._id = id;
};
inherits(SystemMessage, WrappedElement);

SystemMessage.prototype.createDom = function () {
    var inner = this.makeElement('div').addClass('content-wrapper');
    if (this._html) {
        inner.html(this._html);
    }
    this._element = this.makeElement('div')
        .addClass('js-system-message')
        .append(inner);
    if (this._id) {
        this._element.attr('id', this._id);
    }
};
