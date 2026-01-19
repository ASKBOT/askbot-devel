<script>
    // Video embedding help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Embed videos from supported platforms.')}</p>

    <div class="help-section">
        <h4>{gettext('YouTube')}</h4>
        <code class="code-example">@[youtube](dQw4w9WgXcQ)</code>
        <p class="help-note">{gettext('Use the video ID from the YouTube URL.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Vimeo')}</h4>
        <code class="code-example">@[vimeo](123456789)</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Dailymotion')}</h4>
        <code class="code-example">@[dailymotion](x8abcdef)</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Finding the video ID')}</h4>
        <p class="help-note">YouTube: <code>youtube.com/watch?v=<strong>VIDEO_ID</strong></code></p>
        <p class="help-note">Vimeo: <code>vimeo.com/<strong>VIDEO_ID</strong></code></p>
    </div>
</div>

<style>
    .help-content {
        font-size: var(--small-font-size);
    }

    .help-intro {
        margin: 0 0 0.5rem;
        color: var(--fg-color);
    }

    .help-section {
        margin: 0 0 0.5rem;
    }

    .help-section:last-child {
        margin-bottom: 0;
    }

    .help-section h4 {
        font-size: var(--small-font-size);
        font-weight: var(--font-weight-bold);
        margin: 0 0 0.125rem;
    }

    .code-example {
        display: block;
        font-family: monospace;
        background: var(--clr-neutral-95);
        padding: 0.25rem 0.5rem;
        margin: 0 0 0.125rem;
        font-size: var(--small-font-size);
    }

    .help-note {
        margin: 0;
        color: var(--action-link-color);
    }

    code {
        font-family: monospace;
        background: var(--clr-neutral-95);
        padding: 0.125rem 0.25rem;
    }

    code strong {
        color: var(--link-color);
        font-weight: var(--font-weight-bold);
    }
</style>
