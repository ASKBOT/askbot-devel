<script>
    // Lists help content
</script>

<div class="help-content">
    <p class="help-intro">Create ordered, unordered, and task lists.</p>

    <div class="help-section">
        <h4>Unordered list</h4>
        <code class="code-example">- First item<br/>- Second item<br/>- Third item</code>
        <p class="help-note">Also works with <code>*</code> or <code>+</code></p>
    </div>

    <div class="help-section">
        <h4>Ordered list</h4>
        <code class="code-example">1. First item<br/>2. Second item<br/>3. Third item</code>
    </div>

    <div class="help-section">
        <h4>Task list</h4>
        <code class="code-example">- [ ] Unchecked task<br/>- [x] Completed task</code>
        <p class="help-note">Creates interactive checkboxes.</p>
    </div>

    <div class="help-section">
        <h4>Nested lists</h4>
        <code class="code-example">- Item<br/>  - Nested item<br/>  - Another nested</code>
        <p class="help-note">Indent with 2 spaces for nesting.</p>
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
