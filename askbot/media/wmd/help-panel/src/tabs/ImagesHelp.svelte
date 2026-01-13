<script>
    // Images help content
</script>

<div class="help-content">
    <p class="help-intro">Embed images in your post.</p>

    <div class="help-section">
        <h4>Image syntax</h4>
        <code class="code-example">![alt text](https://example.com/image.jpg)</code>
        <p class="help-note">Alt text describes the image for accessibility.</p>
    </div>

    <div class="help-section">
        <h4>Image with title</h4>
        <code class="code-example">![alt text](url "Title text")</code>
        <p class="help-note">Title appears when hovering over the image.</p>
    </div>

    <div class="help-section">
        <h4>Uploading images</h4>
        <p class="help-note">Click the <span class="wmd-image-button"></span> button in the toolbar to upload an image from your computer.</p>
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
</style>
