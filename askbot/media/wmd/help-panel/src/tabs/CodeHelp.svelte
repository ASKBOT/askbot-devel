<script>
    // Code help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Display code with syntax highlighting.')}</p>

    <div class="help-section">
        <h4>{gettext('Inline code')}</h4>
        <code class="code-example">`{gettext('inline code')}`</code>
        <p class="help-note">{gettext('Wrap with single backticks.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Code block')}</h4>
        <code class="code-example">```<br/>{gettext('code block')}<br/>```</code>
        <p class="help-note">{gettext('Wrap with triple backticks on separate lines.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Syntax highlighting')}</h4>
        <code class="code-example">```python<br/>def hello():<br/>    print("Hello")<br/>```</code>
        <p class="help-note">{gettext('Add language name after opening backticks.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Toolbar shortcut')}</h4>
        <p class="help-note">{gettext('Select code and click the code button to format it.')}</p>
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
