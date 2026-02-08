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
