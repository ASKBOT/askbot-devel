<script>
    export let postId;
    export let postType;
    export let prefetchedComments = null;

    let comments = [];
    let loading = true;
    let error = null;

    let scrollContainer;
    let aboveCount = 0;
    let belowCount = 0;
    let observer;

    import { onMount, onDestroy, tick } from 'svelte';

    onMount(() => {
        if (prefetchedComments !== null) {
            comments = prefetchedComments;
            loading = false;
            tick().then(setupObserver);
        } else {
            loadComments();
        }
    });

    onDestroy(() => {
        if (observer) observer.disconnect();
    });

    function loadComments() {
        loading = true;
        error = null;
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
                comments = json;
                loading = false;
                tick().then(setupObserver);
            },
            error: function () {
                error = gettext('Failed to load comments');
                loading = false;
            }
        });
    }

    function setupObserver() {
        if (!scrollContainer || comments.length === 0) return;

        var commentEls = scrollContainer.querySelectorAll('.dc-comment');
        if (commentEls.length === 0) return;

        var visibleSet = new Set();

        observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    var idx = Array.prototype.indexOf.call(commentEls, entry.target);
                    if (idx === -1) return;
                    if (entry.isIntersecting) {
                        visibleSet.add(idx);
                    } else {
                        visibleSet.delete(idx);
                    }
                });

                if (visibleSet.size === 0) {
                    aboveCount = 0;
                    belowCount = 0;
                    return;
                }

                var minVisible = Math.min.apply(null, Array.from(visibleSet));
                var maxVisible = Math.max.apply(null, Array.from(visibleSet));
                aboveCount = minVisible;
                belowCount = commentEls.length - maxVisible - 1;
            },
            { root: scrollContainer, threshold: 0 }
        );

        commentEls.forEach(function (el) { observer.observe(el); });
    }
</script>

{#if loading}
    <div class="dc-existing-comments">
        <p class="dc-loading">{gettext('Loading...')}</p>
    </div>
{:else if error}
    <div class="dc-existing-comments">
        <p class="dc-error">{error}</p>
    </div>
{:else if comments.length > 0}
    <div class="dc-existing-comments" bind:this={scrollContainer}>
        <div class="dc-pill-row dc-pill-row-above">
            <span class="dc-pill" class:visible={aboveCount > 0}>
                {aboveCount} {gettext('above')}
            </span>
        </div>
        <div class="dc-comments-list">
            {#each comments as comment (comment.id)}
                <div class="dc-comment">
                    <div class="dc-comment-header">
                        <span class="dc-comment-author">{comment.user_display_name}</span>
                        <span class="dc-comment-date">{comment.comment_added_at}</span>
                    </div>
                    <div class="dc-comment-body">{@html comment.html}</div>
                </div>
            {/each}
        </div>
        <div class="dc-pill-row dc-pill-row-below">
            <span class="dc-pill" class:visible={belowCount > 0}>
                {belowCount} {gettext('below')}
            </span>
        </div>
    </div>
{/if}
