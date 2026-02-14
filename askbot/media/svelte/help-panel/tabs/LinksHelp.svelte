<script>
    import { parsedAutoLinks } from '../settings.js';
    $: showAutoLinks = $parsedAutoLinks.length > 0;
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Create clickable links in your text.')}</p>

    <div class="help-section">
        <h4>{gettext('Inline link')}</h4>
        <code class="code-example">[{gettext('link text')}](https://example.com)</code>
        <p class="help-note">{gettext('The text in brackets becomes the clickable link.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Link with title')}</h4>
        <code class="code-example">[{gettext('link text')}](https://example.com "{gettext('Title')}")</code>
        <p class="help-note">{gettext('The title appears when hovering over the link.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Auto-linked URLs')}</h4>
        <p class="help-note">{gettext('URLs like https://example.com are automatically converted to links.')}</p>
    </div>

    {#if showAutoLinks}
        <div class="help-section">
            <h4>{gettext('Pattern shortcuts')}</h4>
            <p class="help-note">{gettext('These patterns are automatically converted to links:')}</p>
            {#each $parsedAutoLinks as link}
                <div class="autolink-item">
                    <code class="code-example">{link.example}</code>
                    <span class="help-note">→ {link.exampleUrl}</span>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .autolink-item {
        display: flex;
        align-items: baseline;
        gap: 0.5em;
        margin: 0.25em 0;
    }

    .autolink-item .code-example {
        flex-shrink: 0;
    }
</style>
