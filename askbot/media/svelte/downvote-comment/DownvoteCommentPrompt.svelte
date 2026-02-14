<script>
    import YourComment from './tabs/YourComment.svelte';
    import ExistingComments from './tabs/ExistingComments.svelte';
    import { commentText } from './stores.js';

    export let postId;
    export let postType = 'answer';
    export let prefetchedComments = null;
    export let onCommentChange = null;

    // Reset state on mount
    commentText.set('');

    let minLength = askbot.settings.minCommentBodyLength;
    let maxLength = askbot.data.maxCommentLength;
</script>

<div class="dc-prompt">
    <ExistingComments {postId} {postType} {prefetchedComments} />
    <YourComment
        {minLength}
        {maxLength}
        {onCommentChange}
    />
</div>
