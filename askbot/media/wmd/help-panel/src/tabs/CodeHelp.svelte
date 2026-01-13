<script>
    // Code help content
</script>

<div class="help-content">
    <p class="help-intro">Display code with syntax highlighting.</p>

    <div class="help-section">
        <h4>Inline code</h4>
        <code class="code-example">`inline code`</code>
        <p class="help-note">Wrap with single backticks.</p>
    </div>

    <div class="help-section">
        <h4>Code block</h4>
        <code class="code-example">```<br/>code block<br/>```</code>
        <p class="help-note">Wrap with triple backticks on separate lines.</p>
    </div>

    <div class="help-section">
        <h4>Syntax highlighting</h4>
        <code class="code-example">```python<br/>def hello():<br/>    print("Hello")<br/>```</code>
        <p class="help-note">Add language name after opening backticks.</p>
    </div>

    <div class="help-section">
        <h4>Toolbar shortcut</h4>
        <p class="help-note">Select code and click <span class="wmd-code-button"></span> to format it.</p>
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
