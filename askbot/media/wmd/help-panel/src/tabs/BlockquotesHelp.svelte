<script>
    // Blockquotes help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Quote text from other sources.')}</p>

    <div class="help-section">
        <h4>{gettext('Basic quote')}</h4>
        <code class="code-example">&gt; {gettext('This is a quoted text.')}</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Multi-line quote')}</h4>
        <code class="code-example">&gt; {gettext('First line of quote.')}<br/>&gt; {gettext('Second line of quote.')}</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Nested quotes')}</h4>
        <code class="code-example">&gt; {gettext('Outer quote')}<br/>&gt; &gt; {gettext('Nested quote')}</code>
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
        white-space: pre;
    }

    .help-note {
        margin: 0;
        color: var(--action-link-color);
    }
</style>
