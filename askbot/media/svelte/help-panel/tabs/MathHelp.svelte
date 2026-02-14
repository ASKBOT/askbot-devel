<script>
    // Math/MathJax help content
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Write mathematical expressions using LaTeX syntax.')}</p>

    <div class="help-section">
        <h4>{gettext('Inline math')}</h4>
        <code class="code-example">$E = mc^2$</code>
        <p class="help-note">{gettext('Wrap with single dollar signs for inline formulas.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('Display math')}</h4>
        <code class="code-example">$$\sum_&#123;i=1&#125;^&#123;n&#125; i = \frac&#123;n(n+1)&#125;&#123;2&#125;$$</code>
        <p class="help-note">{gettext('Double dollar signs for centered block formulas.')}</p>
    </div>

    <div class="help-section">
        <h4>{gettext('LaTeX display mode')}</h4>
        <code class="code-example">\[x = \frac&#123;-b \pm \sqrt&#123;b^2-4ac&#125;&#125;&#123;2a&#125;\]</code>
    </div>

    <div class="help-section">
        <h4>{gettext('Literal dollar signs')}</h4>
        <code class="code-example">\$100</code>
        <p class="help-note">{gettext('Use backslash to show actual dollar signs.')}</p>
    </div>
</div>
