<script>
    // Styling help content
</script>

<div class="help-content">
    <p class="help-intro">Format text with bold, italic, and strikethrough.</p>

    <div class="help-section">
        <h4>Bold</h4>
        <code class="code-example">**bold text**</code>
        <p class="help-note">Or use <code>__bold text__</code></p>
    </div>

    <div class="help-section">
        <h4>Italic</h4>
        <code class="code-example">*italic text*</code>
        <p class="help-note">Or use <code>_italic text_</code></p>
    </div>

    <div class="help-section">
        <h4>Bold and italic</h4>
        <code class="code-example">***bold and italic***</code>
    </div>

    <div class="help-section">
        <h4>Strikethrough</h4>
        <code class="code-example">~~strikethrough~~</code>
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
