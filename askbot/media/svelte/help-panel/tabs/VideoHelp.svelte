<script>
    // Video embedding help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Embed videos from supported platforms. Videos appear as clickable links that open in a player.')}</p>

    <div class="help-section">
        <h4>{gettext('Basic syntax')}</h4>
        <code class="code-example">@[youtube](VIDEO_ID)</code>
        <p class="help-note">{gettext('Creates a video link. Click to open the player.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('With title')}</h4>
        <code class="code-example">@[youtube](VIDEO_ID "Video Title")</code>
        <p class="help-note">{gettext('Add an optional title that displays in the link and player header.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Supported platforms')}</h4>
        <p class="help-note"><strong>YouTube:</strong> <code>@[youtube](dQw4w9WgXcQ)</code></p>
        <p class="help-note"><strong>Vimeo:</strong> <code>@[vimeo](123456789)</code></p>
        <p class="help-note"><strong>Dailymotion:</strong> <code>@[dailymotion](x8abcdef)</code></p>
    </div>

    <div class="help-section">
        <h4>{gettext('Finding the video ID')}</h4>
        <p class="help-note">YouTube: <code>youtube.com/watch?v=<strong>VIDEO_ID</strong></code></p>
        <p class="help-note">Vimeo: <code>vimeo.com/<strong>VIDEO_ID</strong></code></p>
    </div>
</div>
