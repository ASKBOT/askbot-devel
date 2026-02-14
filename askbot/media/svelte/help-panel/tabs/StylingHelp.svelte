<script>
    import { settings } from '../settings.js';
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Format text with bold, italic, and strikethrough.')}</p>

    <div class="help-section">
        <h4>{gettext('Bold')}</h4>
        <code class="code-example">**{gettext('bold text')}**</code>
        {#if !$settings.codeFriendlyEnabled}
            <p class="help-note">{gettext('Or use __bold text__')}</p>
        {/if}
    </div>

    <div class="help-section">
        <h4>{gettext('Italic')}</h4>
        <code class="code-example">*{gettext('italic text')}*</code>
        {#if !$settings.codeFriendlyEnabled}
            <p class="help-note">{gettext('Or use _italic text_')}</p>
        {/if}
    </div>

    <div class="help-section">
        <h4>{gettext('Bold and italic')}</h4>
        <code class="code-example">***{gettext('bold and italic')}***</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Strikethrough')}</h4>
        <code class="code-example">~~{gettext('strikethrough')}~~</code>
    </div>
</div>
