/* global askbot, gettext, getTemplate, inherits, showMessage, WrappedElement, setupButtonEventHandlers */
(function () {
  var PostCommentsWidget = function () {
    WrappedElement.call(this);
    this._denied = false;
  };
  inherits(PostCommentsWidget, WrappedElement);

  PostCommentsWidget.prototype.decorate = function (element) {
    this._element = element;
    this._post_id = element.data('parentPostId');
    this._post_type = element.data('parentPostType');
    //var widget_id = element.attr('id');
    //this._userCanPost = askbot['data'][widget_id]['can_post'];
    this._commentsReversed = askbot.settings.commentsReversed;

    //see if user can comment here
    this._loadCommentsButton = element.find('.js-load-comments-btn');

    if (this._loadCommentsButton.length) {
      if (this._commentsReversed/* || this._userCanPost */) {
        setupButtonEventHandlers(
          this._loadCommentsButton,
          this.getLoadCommentsHandler()
        );
      } else {
        setupButtonEventHandlers(
          this._loadCommentsButton,
          this.getAllowEditHandler()
        );
      }
    }

    this._openEditorButton = element.find('.js-add-comment-btn');
    if (askbot.data.userCanPostComments) {
      if (this._openEditorButton.length) {
        setupButtonEventHandlers(
          this._openEditorButton,
          this.getOpenEditorHandler(this._openEditorButton)
        );
      }
    }

    this._isTruncated = this._openEditorButton.hasClass('js-hidden');

    this._cbox = element.find('.js-comments-list');
    var comments = [];
    var me = this;
    this._cbox.children('.js-comment').each(function (index, element) {
      var comment = new Comment(me);
      comments.push(comment);
      comment.decorate(element);
    });
    this._comments = comments;

    if (!askbot.data.userCanPostComments) {
      this.hideOpenEditorButton();
    }

    this._commentsTitle = element.find('.js-comments-list-title');
    $(document).on('askbot.afterEditCommentFormCancel', this.getCloseEditorHandler());
    element.data('commentsWidget', this);
  };

  PostCommentsWidget.prototype.getCloseEditorHandler = function () {
    var me = this;
    return function () {
      if (me._comments.length === 0) {
        me._element.addClass('js-empty');
        me._commentsTitle.addClass('js-hidden');
      }
    }
  };

  PostCommentsWidget.prototype.handleDeletedComment = function () {
    /* if the widget does not have any comments, set
    the 'js-empty' class on the widget element */
    if (this._cbox.children('.js-comment').length === 0) {
      if (this._commentsReversed === false) {
        this._commentsTitle.addClass('js-hidden');
      }
      this._element.addClass('js-empty');
    }
  };

  PostCommentsWidget.prototype.getPostType = function () {
    return this._post_type;
  };

  PostCommentsWidget.prototype.getPostId = function () {
    return this._post_id;
  };

  PostCommentsWidget.prototype.getLoadCommentsButton = function () {
    return this._loadCommentsButton;
  };

  PostCommentsWidget.prototype.getOpenEditorButton = function () {
    return this._openEditorButton;
  };

  PostCommentsWidget.prototype.hideOpenEditorButton = function () {
    this._openEditorButton.addClass('js-hidden');
  };

  PostCommentsWidget.prototype.showOpenEditorButton = function () {
    this._openEditorButton.removeClass('js-hidden');
  };

  PostCommentsWidget.prototype.startNewComment = function () {
    this._commentsTitle.removeClass('js-hidden');
    //find comment template, clone it's dom
    var comment = new Comment(this);
    var commentElem = getTemplate('.js-comment');
    if (this._commentsReversed) {
      this._cbox.prepend(commentElem);
    } else {
      this._cbox.append(commentElem);
    }
    comment.decorate(commentElem);
    this._element.removeClass('js-empty');
    this._element.trigger('askbot.beforeCommentStart');
    comment.startEditing();
  };

  PostCommentsWidget.prototype.canAddComment = function () {
    return this._commentsReversed || this._isTruncated === false;
  };

  PostCommentsWidget.prototype.userCanPost = function () {
    var data = askbot.data;
    if (data.userIsAuthenticated) {
      //true if admin, post owner or high rep user
      if (data.userIsAdminOrMod) return true;
      if (this.getPostId() in data.user_posts) return true;
    }
    return false;
  };

  PostCommentsWidget.prototype.getAllowEditHandler = function () {
    var me = this;
    return function () {
      me.reloadAllComments(function (json) {
        me.reRenderComments(json);
        //2) change button text to "post a comment"
        me.getLoadCommentsButton().remove();
        if (askbot.data.userCanPostComments) {
          me.showOpenEditorButton();
        }
      });
    };
  };

  PostCommentsWidget.prototype.userHasModeratedComment = function () {
    if (!askbot.data.userIsAuthenticated) return false;
    // below works under assumption that moderated comments are shown only to the authors
    return this._element.find('.js-post-moderation-message').length > 0;
  };

  PostCommentsWidget.prototype.getOpenEditorHandler = function (button) {
    var me = this;
    return function () {
      //if user can't post, we tell him something and refuse
      var message;
      if (askbot.settings.readOnlyModeEnabled === true) {
        message = askbot.messages.readOnlyMessage;
        showMessage(button, message, 'after');
      } else if (me.userHasModeratedComment()) {
        message = gettext('Sorry, only one moderated comment per post is allowed');
        showMessage(button, message, 'after');
      } else if (askbot.data.userIsAuthenticated) {
        me.startNewComment();
      } else {
        message = gettext('please sign in or register to post comments');
        showMessage(button, message, 'after');
      }
    };
  };

  PostCommentsWidget.prototype.getLoadCommentsHandler = function () {
    var me = this;
    return function () {
      me.reloadAllComments(function (json) {
        me.reRenderComments(json);
        me.getLoadCommentsButton().remove();
      });
    };
  };


  PostCommentsWidget.prototype.reloadAllComments = function (callback) {
    var post_data = {
      post_id: this._post_id,
      post_type: this._post_type,
      avatar_size: askbot.settings.commentAvatarSize
    };
    var me = this;
    $.ajax({
      type: 'GET',
      url: askbot.urls.postComments,
      data: post_data,
      success: function (json) {
        callback(json);
        me._isTruncated = false;
      },
      dataType: 'json'
    });
  };

  PostCommentsWidget.prototype.reRenderComments = function (json) {
    var me = this;
    me._cbox.trigger('askbot.beforeReRenderComments', [this, json]);
    $.each(this._comments, function (i, item) {
      item.dispose();
    });
    this._comments = [];
    $.each(json, function (i, item) {
      var comment = new Comment(me);
      var commentElem = getTemplate('.js-comment');
      me._cbox.append(commentElem);
      comment.decorate(commentElem);
      comment.setContent(item);
      me._comments.push(comment);
    });
    me._cbox.trigger('askbot.afterReRenderComments', [this, json]);
  };

  $('.js-post-comments').each(function (index, element) {
      var comments = new PostCommentsWidget();
      comments.decorate($(element));
  });
})();
