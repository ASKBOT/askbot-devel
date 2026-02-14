/* global askbot, gettext, ModalDialog, setupButtonEventHandlers, removeButtonEventHandlers, DownvoteCommentPrompt */
/**
 * Downvote Comment Prompt — 2-step flow
 * Step 1: Ask user if they want to leave a comment
 * Step 2: Show the comment editor (Svelte) with smooth height animation
 */
var DownvoteComment = (function () {

    var svelteInstance = null;
    var isModalOpen = false;

    function getPostType(button) {
        return button.data('postType') || 'answer';
    }

    function refreshComments(postId, postType) {
        var commentsWidget = $('#js-post-comments-' + postId);
        if (commentsWidget.length) {
            $.ajax({
                type: 'GET',
                url: askbot.urls.postComments,
                data: {
                    post_id: postId,
                    post_type: postType,
                    avatar_size: askbot.settings.commentAvatarSize || 48
                },
                dataType: 'json',
                success: function (json) {
                    commentsWidget.trigger('askbot.afterReRenderComments', [null, json]);
                    var loadBtn = commentsWidget.find('.js-load-comments-btn');
                    if (loadBtn.length) {
                        loadBtn.trigger('click');
                    }
                }
            });
        }
    }

    /**
     * Smoothly transition modal content from old to new by:
     * 1. Locking to current height
     * 2. Swapping content (via callback)
     * 3. Animating to new measured height
     */
    function animateContentSwap(modalEl, swapFn, callback) {
        var currentHeight = modalEl.outerHeight();
        modalEl.css({ height: currentHeight, overflow: 'hidden' });

        swapFn();

        requestAnimationFrame(function () {
            modalEl.css('height', 'auto');
            var newHeight = modalEl.outerHeight();
            modalEl.css('height', currentHeight);
            modalEl.animate({ height: newHeight }, 300, function () {
                modalEl.css({ height: '', overflow: '' });
                if (callback) callback();
            });
        });
    }

    function showPrompt(button) {
        if (isModalOpen) return;
        isModalOpen = true;
        var postId = button.data('postId');
        var postType = getPostType(button);

        // Pre-fetch existing comments so they're ready by step 2
        var commentsData = { comments: null, loaded: false };
        $.ajax({
            type: 'GET',
            url: askbot.urls.postComments,
            data: {
                post_id: postId,
                post_type: postType,
                avatar_size: askbot.settings.commentAvatarSize || 48
            },
            dataType: 'json',
            success: function (json) {
                commentsData.comments = json;
                commentsData.loaded = true;
            }
        });

        var dialog = new ModalDialog();
        dialog.setHeadingText(gettext('Thank you for your vote!'));
        dialog.setAcceptButtonText(gettext('Leave a comment'));
        dialog.setRejectButtonText(gettext('Skip'));
        dialog.setClass('dc-modal');
        dialog.createDom();

        // Step 1 body: simple prompt (plain HTML, no Svelte)
        var contentEl = dialog._content_element;
        contentEl.html('<p>' + gettext("We'd love to hear a bit more detailed feedback.") + '</p>');

        // Accept handler for step 1: transition to step 2
        var acceptBtn = dialog._acceptBtn;
        removeButtonEventHandlers(acceptBtn);
        setupButtonEventHandlers(acceptBtn, function () {
            transitionToEditor(dialog, postId, postType, commentsData);
        });

        // Reject handler for step 1: close
        var rejectBtn = dialog._rejectBtn;
        removeButtonEventHandlers(rejectBtn);
        setupButtonEventHandlers(rejectBtn, function () {
            cleanup();
            dialog.hide();
        });

        dialog.show();

        // Override ESC handler to call cleanup
        $(document).off('keydown.modalDialog');
        $(document).on('keydown.modalDialog', function (evt) {
            if (evt.keyCode === 27) {
                cleanup();
                dialog.hide();
            }
        });
    }

    function transitionToEditor(dialog, postId, postType, commentsData) {
        var modalEl = dialog._element;

        animateContentSwap(modalEl, function () {
            // Update heading
            var hasComments = commentsData && commentsData.loaded && commentsData.comments && commentsData.comments.length > 0;
            dialog.setHeadingText(gettext('Leave a comment'));
            if (hasComments) {
                dialog._title.append(
                    $('<span>').addClass('dc-heading-hint').text(
                        ' (' + gettext('previous comments shown below') + ')'
                    )
                );
            }

            // Mount Svelte component
            var contentEl = dialog._content_element;
            var mountTarget = $('<div>')[0];
            contentEl.html('');
            contentEl.append(mountTarget);

            svelteInstance = new DownvoteCommentPrompt({
                target: mountTarget,
                props: {
                    postId: postId,
                    postType: postType,
                    prefetchedComments: commentsData && commentsData.loaded ? commentsData.comments : null,
                    onCommentChange: function (text) {
                        var minLength = askbot.settings.minCommentBodyLength || 10;
                        if (text.length >= minLength) {
                            dialog.enableAcceptButton();
                        } else {
                            dialog.disableAcceptButton();
                        }
                    }
                }
            });

            // Update buttons for step 2
            var acceptBtn = dialog._acceptBtn;
            removeButtonEventHandlers(acceptBtn);
            acceptBtn.html(gettext('Add Comment'));
            dialog.disableAcceptButton();
            setupButtonEventHandlers(acceptBtn, function () {
                submitComment(dialog, mountTarget, postId, postType);
            });

            var rejectBtn = dialog._rejectBtn;
            removeButtonEventHandlers(rejectBtn);
            rejectBtn.html(gettext('Cancel'));
            setupButtonEventHandlers(rejectBtn, function () {
                cleanup();
                dialog.hide();
            });
        });
    }

    function submitComment(dialog, mountTarget, postId, postType) {
        var textarea = mountTarget.querySelector('.dc-textarea');
        var commentText = textarea ? textarea.value : '';
        var minLength = askbot.settings.minCommentBodyLength || 10;
        if (commentText.length < minLength) return;

        dialog.disableAcceptButton();

        $.ajax({
            type: 'POST',
            url: askbot.urls.postComments,
            dataType: 'json',
            data: {
                comment: commentText,
                post_type: postType,
                post_id: postId,
                avatar_size: askbot.settings.commentAvatarSize || 48
            },
            success: function () {
                cleanup();
                dialog.hide();
                refreshComments(postId, postType);
            },
            error: function (xhr) {
                dialog.enableAcceptButton();
                dialog.clearMessages();
                dialog.setMessage(
                    xhr.responseText || gettext('Failed to post comment'),
                    'error'
                );
            }
        });
    }

    function cleanup() {
        isModalOpen = false;
        if (svelteInstance) {
            svelteInstance.$destroy();
            svelteInstance = null;
        }
    }

    function handleDownvote(evt, button, data) {
        // Only show on new downvotes, not undo
        if (data.status === 1) return;
        // Only show if user is authenticated
        if (!askbot.data.userIsAuthenticated) return;
        showPrompt(button);
    }

    return {
        init: function () {
            $(document).on('askbot.voteDown', '.js-post-vote-btn', function (evt, button, data) {
                handleDownvote(evt, button, data);
            });
        }
    };
})();
