/* global askbot, ModalDialog, DownvoteCommentPrompt */
/**
 * Downvote Comment Prompt — thin ModalDialog shell.
 * All step management, UI, submission, and animation live in the Svelte component.
 */
var DownvoteComment = (function () {

    var svelteInstance = null;
    var isModalOpen = false;

    function getPostType(button) {
        return button.data('postType') || 'answer';
    }

    function scrollToNewComment(json) {
        if (!json || !json.length) return;
        var userId = askbot.data.userId;
        var newComment = null;
        for (var i = json.length - 1; i >= 0; i--) {
            if (json[i].user_id === userId) {
                newComment = json[i];
                break;
            }
        }
        if (newComment) {
            var el = document.getElementById('js-post-' + newComment.id);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function refreshPostComments(postId) {
        var el = $('.js-post-comments[data-parent-post-id="' + postId + '"]');
        var widget = el.data('commentsWidget');
        if (widget) {
            widget.reloadAllComments(function (json) {
                widget.reRenderComments(json);
                scrollToNewComment(json);
            });
        }
    }

    function cleanup() {
        isModalOpen = false;
        if (svelteInstance) {
            DownvoteCommentPrompt.destroy(svelteInstance);
            svelteInstance = null;
        }
    }

    function showPrompt(button) {
        if (isModalOpen) return;
        isModalOpen = true;
        var postId = button.data('postId');
        var postType = getPostType(button);

        var dialog = new ModalDialog();
        dialog.setClass('dc-modal');
        dialog.createDom();

        var contentEl = dialog._content_element;
        var mountTarget = $('<div>')[0];
        contentEl.html('');
        contentEl.append(mountTarget);

        function closeModal() {
            cleanup();
            dialog.hide();
        }

        svelteInstance = DownvoteCommentPrompt.create({
            target: mountTarget,
            props: {
                postId: postId,
                postType: postType,
                onClose: closeModal,
                onEditorOpen: function () {
                    dialog.setDismissOnOutsideClick(false);
                },
                onSubmitted: function (pid, ptype) {
                    cleanup();
                    dialog.hide();
                    refreshPostComments(pid);
                }
            }
        });

        dialog.show();

        // Override ESC handler to call cleanup
        $(document).off('keydown.modalDialog');
        $(document).on('keydown.modalDialog', function (evt) {
            if (evt.keyCode === 27) {
                closeModal();
            }
        });
    }

    function handleDownvote(evt, button, data) {
        if (data.status === 1) return;
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
