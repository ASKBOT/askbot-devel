/* global askbot, AutoCompleter, gettext, Tag, WrappedElement, getUniqueWords, inherits, notify, showMessage */
(function () {
  var RetagForm = function () {
    WrappedElement.call(this);
    this._onCompleted = null;
    this._onCanceled = null;
  }
  inherits(RetagForm, WrappedElement);

  RetagForm.prototype.setOnCompleted = function (callback) {
    this._onCompleted = callback;
  };

  RetagForm.prototype.setOnCanceled = function (callback) {
    this._onCanceled = callback;
  };

  RetagForm.prototype.getInputElement = function () {
    return this._element.find('input');
  };

  RetagForm.prototype.initAutoCompleter = function () {
    var tagAc = new AutoCompleter({
      url: askbot.urls.get_tag_list,
      minChars: 1,
      useCache: true,
      matchInside: true,
      maxCacheLength: 100,
      delay: 10
    });
    tagAc.decorate($(this._element).find('input'));
    tagAc._results.on('click', function (evt) {
      evt.stopPropagation();
    });
  };

  RetagForm.prototype.setupCancelInputEventHandlers = function () {
    var me = this;
    this.getInputElement().keydown(function (evt) {
      if (evt.which === 27 || evt.keyCode === 27) {
        me._onCanceled();
      }
    });
    // close editor on click outside of the editor
    $(document).unbind('click', this._onCanceled).click(this._onCanceled);
    // capture click on form
    this._element.click(function (evt) { evt.stopPropagation(); });
  };

  RetagForm.prototype.showAndFocus = function (tagsList) {
    this._element.show();
    var input = this.getInputElement();
    input.val(tagsList.join(' '));
    input.focus();
    this.initAutoCompleter();
    this.setupCancelInputEventHandlers();
  }

  RetagForm.prototype.clearAndHide = function () {
    var input = this.getInputElement();
    input.val('');
    this._element.hide();
  };

  RetagForm.prototype.retag = function () {
    var me = this;
    var tagsList = getUniqueWords(me.getInputElement().val())
    $.ajax({
      type: 'POST',
      url: askbot.urls.retag,
      dataType: 'json',
      data: { tags: tagsList.join(' ') },
      success: function (json) {
        if (json.success) {
          if (json.new_tags) {
            var newTags = getUniqueWords(json.new_tags);
            me._onCompleted(newTags);
          } else {
            me._onCompleted([]);
          }
          if (json.message) {
            notify.show(json.message);
          }
        } else {
          me.showAndFocus(tagsList);
          showMessage(me.getInputElement(), json.message);
        }
      },
      error: function () {
        showMessage(tagsList, gettext('sorry, something is not right here'));
        me._onCanceled();
      }
    });
    return false;
  }

  RetagForm.prototype.createDom = function () {
    var form = $('<form method="post"></form>');
    var tagInput = $('<input class="js-tags-input" type="text" autocomplete="off" name="tags" size="30"/>');
    form.append(tagInput);
    this._element = form;
    var me = this;
    form.validate({
      rules: {
        tags: {
          required: askbot.settings.tagsAreRequired,
          maxlength: askbot.settings.maxTagsPerPost * askbot.settings.maxTagLength,
          limit_tag_count: true,
          limit_tag_length: true
        }
      },
      messages: {
        tags: {
          required: gettext('tags cannot be empty'),
          maxlength: askbot.messages.tagLimits,
          limit_tag_count: askbot.messages.maxTagsPerPost,
          limit_tag_length: askbot.messages.maxTagLength
        }
      },
      submitHandler: function () {
        me.retag()
      },
      errorClass: 'js-retag-error'
    });
  }

  var QuestionTags = function() {
    WrappedElement.call(this);
    this._retagForm = undefined;
  }
  inherits(QuestionTags, WrappedElement);

  QuestionTags.prototype.addTag = function (tagName) {
    var tag = new Tag();
    tag.setName(tagName);
    tag.setLinkable(true);
    var li = this.makeElement('li');
    li.append(tag.getElement());
    var retagBtnCtr = $('.js-retag-btn-ctr');
    retagBtnCtr.before(li);
  };

  QuestionTags.prototype.setTags = function (tagsList) {
    var tagLiElements = this._element.find('> :not(.js-retag-btn-ctr)');
    tagLiElements.remove();
    if (tagsList.length === 0) {
      $('.js-retag-btn.with-tags-icon').removeClass('js-hidden');
      $('.js-retag-btn:not(.with-tags-icon)').addClass('js-hidden');
      return;
    } else {
      $('.js-retag-btn.with-tags-icon').addClass('js-hidden');
      $('.js-retag-btn:not(.with-tags-icon)').removeClass('js-hidden');
    }
    var me = this;
    $.each(tagsList, function (_, tagName) {
      me.addTag(tagName);
    });
  };

  QuestionTags.prototype.initRetagForm = function () {
    var me = this;
    var retagForm = new RetagForm()
    this._retagForm = retagForm;
    retagForm.setOnCompleted(function (newTagsList) {
      me.setTags(newTagsList)
      retagForm.clearAndHide();
      me.show();
    });
    retagForm.setOnCanceled(function () {
      retagForm.clearAndHide();
      me.show();
    });
    var retagFormElement = retagForm.getElement();
    $(this._element).after(retagFormElement);
  };

  QuestionTags.prototype.getTagsList = function () {
    var tags = this._element.find('.js-tag-name');
    var tagsList = [];
    tags.each(function (_, item) {
      tagsList.push($(item).html());
    });
    return tagsList;
  }

  QuestionTags.prototype.startRetagging = function () {
    if (!this._retagForm) this.initRetagForm();
    this._retagForm.showAndFocus(this.getTagsList());
    this.hide();
  };

  QuestionTags.prototype.show = function () { 
    this._element.show()
  };

  QuestionTags.prototype.hide = function () {
    this._element.hide();
  };

  QuestionTags.prototype.decorate = function(element) {
    this._element = element;
    var retagBtn = element.find('.js-retag-btn');
    var me = this;
    retagBtn.unbind('click').click(function(evt) {
      me.startRetagging();
      evt.stopPropagation();
    });
    retagBtn.unbind('keypress').keypress(function (e) {
      if ((e.which && e.which === 13) || (e.keyCode && e.keyCode === 13)) {
        me.startRetagging();
      }
    });
  };

  if (askbot.settings.tagSource === 'user-input') {
    var qTags = new QuestionTags();
    qTags.decorate($('.js-question-tags'));
  }

})();
