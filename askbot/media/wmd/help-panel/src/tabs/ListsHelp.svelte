<script>
    // Lists help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Create ordered, unordered, and task lists.')}</p>

    <div class="help-section">
        <h4>{gettext('Unordered list')}</h4>
        <code class="code-example">- {gettext('First item')}<br/>- {gettext('Second item')}<br/>- {gettext('Third item')}</code>
        <p class="help-note">{gettext('Also works with * or +')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Ordered list')}</h4>
        <code class="code-example">1. {gettext('First item')}<br/>2. {gettext('Second item')}<br/>3. {gettext('Third item')}</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Task list')}</h4>
        <code class="code-example">- [ ] {gettext('Unchecked task')}<br/>- [x] {gettext('Completed task')}</code>
        <p class="help-note">{gettext('Creates interactive checkboxes.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Nested lists')}</h4>
        <code class="code-example">- {gettext('Item')}<br/>  - {gettext('Nested item')}<br/>  - {gettext('Another nested')}</code>
        <p class="help-note">{gettext('Indent with 2 spaces for nesting.')}</p>
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

    code {
        font-family: monospace;
        background: var(--clr-neutral-95);
        padding: 0.125rem 0.25rem;
    }
</style>
