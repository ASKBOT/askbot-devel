<script>
    // Images help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Embed images in your post.')}</p>

    <div class="help-section">
        <h4>{gettext('Uploading images')}</h4>
        <p class="help-note">{gettext('Click the image button in the toolbar to upload an image from your computer. The markdown link will be inserted automatically.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('External images')}</h4>
        <code class="code-example">![alt text](https://example.com/image.jpg)</code>
        <p class="help-note">{gettext('You can also link to external images using markdown syntax. Alt text describes the image for accessibility.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Image with title')}</h4>
        <code class="code-example">![alt text](url {gettext('"Title text"')})</code>
        <p class="help-note">{gettext('Title appears when hovering over the image.')}</p>
    </div>
</div>
