<script>
    // Auto-link patterns help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Special patterns are automatically converted to links.')}</p>

    <div class="help-section">
        <h4>{gettext('How it works')}</h4>
        <p class="help-note">{gettext('Your administrator has configured patterns that automatically become clickable links.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Example patterns')}</h4>
        <p class="help-note">{gettext('Issue references like #123 or BUG-456 may link to your issue tracker.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Note')}</h4>
        <p class="help-note">{gettext("The specific patterns available depend on your site's configuration. Contact your administrator for details.")}</p>
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
