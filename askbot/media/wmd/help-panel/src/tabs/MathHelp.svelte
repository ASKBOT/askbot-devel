<script>
    // Math/MathJax help content
</script>

<div class="help-content">
    <p class="help-intro">Write mathematical expressions using LaTeX syntax.</p>

    <div class="help-section">
        <h4>Inline math</h4>
        <code class="code-example">$E = mc^2$</code>
        <p class="help-note">Wrap with single dollar signs for inline formulas.</p>
    </div>

    <div class="help-section">
        <h4>Display math</h4>
        <code class="code-example">$$\sum_&#123;i=1&#125;^&#123;n&#125; i = \frac&#123;n(n+1)&#125;&#123;2&#125;$$</code>
        <p class="help-note">Double dollar signs for centered block formulas.</p>
    </div>

    <div class="help-section">
        <h4>LaTeX display mode</h4>
        <code class="code-example">\[x = \frac&#123;-b \pm \sqrt&#123;b^2-4ac&#125;&#125;&#123;2a&#125;\]</code>
    </div>

    <div class="help-section">
        <h4>Literal dollar signs</h4>
        <code class="code-example">\$100</code>
        <p class="help-note">Use backslash to show actual dollar signs.</p>
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
    }

    .help-note {
        margin: 0;
        color: var(--action-link-color);
    }
</style>
