<script>
    // Tables help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Create tables using pipe characters.')}</p>

    <div class="help-section">
        <h4>{gettext('Basic table')}</h4>
        <code class="code-example">| {interpolate(pgettext('Header <number>', 'Header %s'), 1)} |
            {interpolate(pgettext('Header <number>', 'Header %s'), 2)} |<br/>|----------|----------|<br/> |
            {interpolate(pgettext('Cell <number>', 'Cell %s'), 1)} | {interpolate(pgettext('Cell <number>', 'Cell %s'),
                2)} |<br/>| {interpolate(pgettext('Cell <number>', 'Cell %s'), 3)} | {interpolate(pgettext('Cell <number>', 'Cell %s'), 4)} |</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Column alignment')}</h4>
        <code class="code-example">| {pgettext('align column to', 'Left')} | {pgettext('align column to', 'Center')} | {pgettext('align column to', 'Right')} |<br/>|:-------|:------:|------:|<br/>| {gettext('text')} | {gettext('text')} | {gettext('text')} |</code>
        <p class="help-note">{gettext('Use : to align columns (left, center, right).')}</p>
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
