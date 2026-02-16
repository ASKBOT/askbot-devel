<script>
    import YourComment from './tabs/YourComment.svelte';
    import ExistingComments from './tabs/ExistingComments.svelte';
    import { commentText } from './stores.js';
    import { onMount, tick } from 'svelte';

    let { postId, postType = 'answer', onClose = null, onSubmitted = null, onEditorOpen = null } = $props();

    let step = $state('prompt');
    let prefetchedComments = $state(null);
    let hasComments = $state(false);
    let submitting = $state(false);
    let errorMessage = $state(null);
    let contentEl;

    let minLength = askbot.settings.minCommentBodyLength || 10;
    let maxLength = askbot.data.maxCommentLength;

    let canSubmit = $derived(!submitting && $commentText.length >= minLength);

    // Reset comment text on mount
    commentText.set('');

    onMount(function () {
        // Pre-fetch comments during step 1 so they're ready for step 2
        jQuery.ajax({
            type: 'GET',
            url: askbot.urls.postComments,
            data: {
                post_id: postId,
                post_type: postType,
                avatar_size: askbot.settings.commentAvatarSize || 48
            },
            dataType: 'json',
            success: function (json) {
                prefetchedComments = json;
                hasComments = json && json.length > 0;
            }
        });
    });

    function transitionToStep(nextStep) {
        if (!contentEl) {
            step = nextStep;
            return;
        }
        var currentHeight = contentEl.offsetHeight;
        contentEl.style.height = currentHeight + 'px';
        contentEl.style.overflow = 'hidden';

        step = nextStep;

        tick().then(function () {
            requestAnimationFrame(function () {
                contentEl.style.height = 'auto';
                var newHeight = contentEl.offsetHeight;
                contentEl.style.height = currentHeight + 'px';
                // Force reflow
                contentEl.offsetHeight; // eslint-disable-line no-unused-expressions
                contentEl.style.transition = 'height 300ms ease';
                contentEl.style.height = newHeight + 'px';

                function onEnd() {
                    contentEl.removeEventListener('transitionend', onEnd);
                    contentEl.style.height = '';
                    contentEl.style.overflow = '';
                    contentEl.style.transition = '';
                }
                contentEl.addEventListener('transitionend', onEnd);
            });
        });
    }

    function handleLeaveComment() {
        if (onEditorOpen) onEditorOpen();
        transitionToStep('editor');
    }

    function handleSkip() {
        if (onClose) onClose();
    }

    function handleCancel() {
        if (onClose) onClose();
    }

    function handleSubmit() {
        if (!canSubmit) return;
        submitting = true;
        errorMessage = null;

        jQuery.ajax({
            type: 'POST',
            url: askbot.urls.postComments,
            dataType: 'json',
            data: {
                comment: $commentText,
                post_type: postType,
                post_id: postId,
                avatar_size: askbot.settings.commentAvatarSize || 48
            },
            success: function () {
                submitting = false;
                if (onSubmitted) onSubmitted(postId, postType);
            },
            error: function (xhr) {
                submitting = false;
                errorMessage = xhr.responseText || gettext('Failed to post comment');
            }
        });
    }
</script>

<div class="dc-prompt" bind:this={contentEl}>
    {#if step === 'prompt'}
        <h3 class="dc-heading">{gettext('Thank you for your vote!')}</h3>
        <p class="dc-body-text">{gettext("We'd love to hear a bit more detailed feedback.")}</p>
        <div class="dc-actions">
            <button class="btn" onclick={handleLeaveComment}>
                {gettext('Leave a comment')}
            </button>
            <button class="btn btn-muted" onclick={handleSkip}>
                {gettext('Skip')}
            </button>
        </div>
    {:else}
        <h3 class="dc-heading">
            {gettext('Leave a comment')}
            {#if hasComments}
                <span class="dc-heading-hint">
                    ({gettext('previous comments shown below')})
                </span>
            {/if}
        </h3>

        {#if errorMessage}
            <div class="dc-error-banner">{errorMessage}</div>
        {/if}

        <ExistingComments {postId} {postType} {prefetchedComments} />
        <YourComment {minLength} {maxLength} />

        <div class="dc-actions">
            <button
                class="btn"
                disabled={!canSubmit}
                onclick={handleSubmit}
            >
                {gettext('Add Comment')}
            </button>
            <button class="btn btn-muted" onclick={handleCancel}>
                {gettext('Cancel')}
            </button>
        </div>
    {/if}
</div>
