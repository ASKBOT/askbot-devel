<script>
    // Links help content
</script>

<div class="help-content">
    <p class="help-intro">Create clickable links in your text.</p>

    <div class="help-section">
        <h4>Inline link</h4>
        <code class="code-example">[link text](https://example.com)</code>
        <p class="help-note">The text in brackets becomes the clickable link.</p>
    </div>

    <div class="help-section">
        <h4>Link with title</h4>
        <code class="code-example">[link text](https://example.com "Title")</code>
        <p class="help-note">The title appears when hovering over the link.</p>
    </div>

    <div class="help-section">
        <h4>Auto-linked URLs</h4>
        <p class="help-note">URLs like <code>https://example.com</code> are automatically converted to links.</p>
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
</style>
