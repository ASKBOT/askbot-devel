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
