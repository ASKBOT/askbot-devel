<script>
    import { onMount, tick } from 'svelte';
    import { commentText } from '../stores.js';

    let { minLength = 10, maxLength = 600, onCommentChange = null } = $props();

    let textareaEl;

    onMount(async () => {
        await tick();
        if (textareaEl) textareaEl.focus();
    });

    function handleInput(event) {
        commentText.set(event.target.value);
        if (onCommentChange) {
            onCommentChange(event.target.value);
        }
    }

    let charCount = $derived($commentText.length);
    let remaining = $derived(maxLength - charCount);
    let counterClass = $derived(remaining < 20 ? 'warning' : '');
    let tooShort = $derived(charCount > 0 && charCount < minLength);
</script>

<div class="dc-your-comment">
    <textarea
        bind:this={textareaEl}
        class="dc-textarea"
        placeholder={gettext('Leave a comment to explain your downvote')}
        value={$commentText}
        oninput={handleInput}
        maxlength={maxLength}
        rows="4"
    ></textarea>
    <div class="dc-char-info">
        {#if tooShort}
            <span class="dc-min-length-hint">
                {gettext('Minimum') + ' ' + minLength + ' ' + gettext('characters')}
            </span>
        {/if}
        <span class="dc-char-counter {counterClass}">
            {remaining}
        </span>
    </div>
</div>
