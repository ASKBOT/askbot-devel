<script>
    // Styling help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Format text with bold, italic, and strikethrough.')}</p>

    <div class="help-section">
        <h4>{gettext('Bold')}</h4>
        <code class="code-example">**{gettext('bold text')}**</code>
        <p class="help-note">{gettext('Or use __bold text__')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Italic')}</h4>
        <code class="code-example">*{gettext('italic text')}*</code>
        <p class="help-note">{gettext('Or use _italic text_')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Bold and italic')}</h4>
        <code class="code-example">***{gettext('bold and italic')}***</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Strikethrough')}</h4>
        <code class="code-example">~~{gettext('strikethrough')}~~</code>
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
