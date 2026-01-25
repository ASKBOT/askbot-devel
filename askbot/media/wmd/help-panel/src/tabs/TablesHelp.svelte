<script>
    // Tables help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Create tables using pipe characters.')}</p>

    <div class="help-section">
        <h4>{gettext('Basic table')}</h4>
        <code class="code-example">
| {interpolate(pgettext('Header <number>', 'Header %s'), [1])} | {interpolate(pgettext('Header <number>', 'Header %s'), [2])} |
|----------|----------|
| {interpolate(pgettext('Cell <number>', 'Cell %s'), [1])} | {interpolate(pgettext('Cell <number>', 'Cell %s'), [2])} |
| {interpolate(pgettext('Cell <number>', 'Cell %s'), [3])} | {interpolate(pgettext('Cell <number>', 'Cell %s'), [4])} |
        </code>
    </div>

    <div class="help-section">
        <h4>{gettext('Column alignment')}</h4>
        <code class="code-example">
| {pgettext('align column to', 'Left')} | {pgettext('align column to', 'Center')} | {pgettext('align column to', 'Right')} |
|:-------|:------:|------:|
| {gettext('text')} | {gettext('text')} | {gettext('text')} |
        </code>
        <p class="help-note">{gettext('Use : to align columns (left, center, right).')}</p>
    </div>
</div>
