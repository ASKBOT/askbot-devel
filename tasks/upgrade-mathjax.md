# MathJax Upgrade Plan: v2 → v4

## Overview

Upgrade Askbot's MathJax implementation from the outdated v2 (circa 2012) to modern MathJax v4 (2024), with CDN delivery option to eliminate deployment complexity.

## Current State

- **Version**: MathJax v2 (using Hub API)
- **Deployment**: Self-hosted only (admin must install MathJax separately)
- **Configuration**: `ENABLE_MATHJAX` + `MATHJAX_BASE_URL` settings
- **Delimiters**: `$...$` and `\(...\)` for inline, display mode via `$$...$$`
- **Integration**: Editor preview with 500ms delayed rendering
- **Files affected**:
  - `askbot/conf/markup.py` - Settings
  - `askbot/jinja2/meta/bottom_scripts.html` - Loading script
  - `askbot/media/wmd/askbot_converter.js` - Editor preview
  - `askbot/media/js/utils/post_expander.js` - Dynamic content
  - `askbot/doc/source/mathjax.rst` - Documentation

## Goals

1. ✅ Modernize to MathJax v4 (better performance, maintained)
2. ✅ Add CDN option (eliminate self-hosting barrier)
3. ✅ Maintain backward compatibility for self-hosted deployments
4. ✅ Update to v4 API (deprecate Hub API)
5. ✅ Improve accessibility (v4 enhancements)
6. ✅ Better font options (v4 supports 11 fonts)

## Research Summary

### Why MathJax v4?
- **Industry standard**: Used by Stack Exchange, GitHub, MathOverflow
- **Comprehensive LaTeX**: Near-complete support (vs KaTeX's limited subset)
- **Accessibility**: Built-in screen reader, braille, speech generation
- **Performance**: Faster than v2, acceptable for Q&A forums
- **Mature**: Backed by NumFOCUS, active development

### Why not KaTeX?
- Incomplete LaTeX support (missing `align`, arrays, etc.)
- No accessibility features
- Would frustrate academic users
- Not used by major Q&A platforms

### Why not Server-Side Rendering?
- High server load and security risks
- Complex infrastructure (Texoid microservice)
- Only beneficial if SEO is critical for math content
- Client-side rendering is proven for Q&A forums

## Implementation Plan

### Phase 1: Configuration Updates

**File**: `askbot/conf/markup.py`

**Changes**:
1. Add new setting: `MATHJAX_VERSION` (choices: 'v2', 'v4', default: 'v4')
2. Add new setting: `MATHJAX_USE_CDN` (boolean, default: True)
3. Add new setting: `MATHJAX_CDN_URL` (default: jsdelivr CDN for v4)
4. Keep `MATHJAX_BASE_URL` for backward compatibility (self-hosted)
5. Update help text to recommend CDN option

**Backward Compatibility**:
- If `MATHJAX_BASE_URL` is set (existing installations): use self-hosted
- If `MATHJAX_USE_CDN` is True (new installations): use CDN
- Settings validation to prevent misconfiguration

### Phase 2: Frontend Loading

**File**: `askbot/jinja2/meta/bottom_scripts.html`

**Current (MathJax v2)**:
```javascript
<script src="{{settings.MATHJAX_BASE_URL}}/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
  MathJax.Hub.Config({
    extensions: ["tex2jax.js"],
    jax: ["input/TeX","output/HTML-CSS"],
    tex2jax: {inlineMath: [["$","$"],["\\(","\\)"]]}
  });
</script>
```

**New (MathJax v4)**:
```javascript
<script>
  MathJax = {
    tex: {
      inlineMath: [['$', '$'], ['\\(', '\\)']],
      displayMath: [['$$', '$$'], ['\\[', '\\]']],
      processEscapes: true,
      processEnvironments: true
    },
    options: {
      skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
      ignoreHtmlClass: 'no-mathjax'
    },
    startup: {
      pageReady: () => {
        return MathJax.startup.defaultPageReady().then(() => {
          console.log('MathJax loaded successfully');
        });
      }
    }
  };
</script>
<script src="{{mathjax_url}}/tex-mml-chtml.js" async></script>
```

**Implementation**:
1. Determine `mathjax_url` based on settings (CDN vs self-hosted)
2. Use conditional template logic for v2 vs v4
3. Add async loading for better performance
4. Add error handling for CDN failures

### Phase 3: Editor Preview Updates

**File**: `askbot/media/wmd/askbot_converter.js`

**Current (v2 Hub API)**:
```javascript
MathJax.Hub.Queue(['Typeset', MathJax.Hub, 'previewer']);
```

**New (v4 Promise API)**:
```javascript
if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
  MathJax.typesetPromise(['previewer']).catch((err) => {
    console.error('MathJax typeset error:', err);
  });
}
```

**Changes**:
1. Replace `scheduleMathJaxRendering()` to use v4 API
2. Update `makeHtml()` to work with Promises
3. Maintain 500ms debounce for performance
4. Add version detection to support both v2 and v4 during migration

### Phase 4: Dynamic Content Updates

**File**: `askbot/media/js/utils/post_expander.js`

**Current**:
```javascript
if (askbot.settings.mathjaxEnabled === true) {
    runMathJax();
}
```

**New**:
```javascript
if (askbot.settings.mathjaxEnabled === true) {
    if (typeof MathJax !== 'undefined') {
        if (MathJax.typesetPromise) {
            // v4 API
            MathJax.typesetPromise([snippet[0]]).catch((err) => {
                console.error('MathJax typeset error:', err);
            });
        } else if (MathJax.Hub) {
            // v2 API fallback
            MathJax.Hub.Queue(['Typeset', MathJax.Hub, snippet[0]]);
        }
    }
}
```

**Implementation**:
1. Find all `runMathJax()` calls
2. Replace with version-aware typeset calls
3. Scope to specific elements (better performance)
4. Add error handling

### Phase 5: Markdown-it Integration

**File**: `askbot/utils/markup.py`

**Current Issue**:
- markdown-it may process text inside `$...$` delimiters
- Could break LaTeX syntax (e.g., `_` becoming `<em>`)

**Solution**:
1. Add markdown-it plugin or custom rule to skip math blocks
2. Option 1: Use existing plugin (if available for markdown-it-py)
3. Option 2: Custom inline/block rule to protect math delimiters
4. Ensure math blocks are preserved in HTML output

**Research needed**:
- Check if `mdit-py-plugins` has texmath support
- Test interaction between markdown parsing and MathJax rendering
- Verify `MARKUP_CODE_FRIENDLY` setting still works

### Phase 6: Documentation Updates

**File**: `askbot/doc/source/mathjax.rst`

**Updates**:
1. Add "Recommended: CDN Option" section (quick setup)
2. Update self-hosting instructions for v4
3. Remove outdated same-origin policy warnings (v4 handles this)
4. Add configuration examples
5. Add troubleshooting section
6. Link to MathJax v4 documentation

**New structure**:
```
1. Overview (what MathJax does)
2. Quick Start: CDN Option (recommended)
3. Self-Hosted Installation (advanced)
4. Configuration Options
5. LaTeX Syntax Guide
6. Troubleshooting
7. Migration from v2 to v4
```

## Testing Plan

### Unit Tests
- [ ] Settings configuration validation
- [ ] CDN vs self-hosted URL generation
- [ ] Version detection logic

### Integration Tests
- [ ] Editor preview with inline math (`$x^2$`)
- [ ] Editor preview with display math (`$$\int_0^1 x dx$$`)
- [ ] Post display with math content
- [ ] Dynamic content loading (post expander)
- [ ] Comment rendering with math

### Manual Testing Checklist
- [ ] Fresh installation with CDN (default)
- [ ] Upgrade from v2 self-hosted (backward compatibility)
- [ ] Switch between CDN and self-hosted
- [ ] Test with common LaTeX: fractions, matrices, integrals, align environments
- [ ] Test editor live preview responsiveness
- [ ] Test on multiple browsers (Chrome, Firefox, Safari, Edge)
- [ ] Test accessibility features (screen reader)
- [ ] Test with `MARKUP_CODE_FRIENDLY` enabled/disabled
- [ ] Verify no conflicts with markdown-it processing

### Performance Testing
- [ ] Page load time comparison (v2 vs v4)
- [ ] Editor preview responsiveness
- [ ] Large document with many equations
- [ ] CDN availability and fallback

## Migration Strategy

### For Existing Installations

**Automatic (Recommended)**:
1. Update Askbot package
2. Run migrations (if needed)
3. Keep existing `MATHJAX_BASE_URL` → continues using self-hosted v2
4. Admin can opt-in to v4 CDN via settings panel

**Manual Upgrade**:
1. Backup site
2. Update Askbot
3. In settings: Set `MATHJAX_USE_CDN = True`
4. Clear `MATHJAX_BASE_URL` (or set to empty)
5. Clear browser cache
6. Test math rendering

### For New Installations

**Default behavior**:
1. `ENABLE_MATHJAX = False` (disabled by default)
2. When admin enables: `MATHJAX_USE_CDN = True` (v4 CDN)
3. Zero configuration needed
4. Works immediately

## Rollout Plan

### Stage 1: Development
- [ ] Implement configuration changes
- [ ] Implement frontend loading with v4
- [ ] Update editor preview code
- [ ] Update dynamic content code

### Stage 2: Testing
- [ ] Run automated tests
- [ ] Manual testing with test content
- [ ] Performance benchmarking
- [ ] Cross-browser testing

### Stage 3: Documentation
- [ ] Update RST documentation
- [ ] Add migration guide
- [ ] Update release notes
- [ ] Create upgrade tutorial (blog post?)

### Stage 4: Beta Release
- [ ] Release as beta feature flag
- [ ] Gather feedback from community
- [ ] Fix issues found in production

### Stage 5: Production Release
- [ ] Make v4 CDN the default
- [ ] Announce in release notes
- [ ] Deprecation notice for v2 (keep support for 2 releases)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing v2 sites | High | Maintain backward compatibility, automatic detection |
| CDN unavailable | Medium | Provide self-hosted option, add fallback |
| LaTeX syntax changes | Low | v4 is mostly compatible, test extensively |
| Performance regression | Medium | Benchmark before/after, v4 is faster than v2 |
| Browser compatibility | Low | v4 supports modern browsers, graceful degradation |
| Migration complexity | Medium | Clear documentation, automated where possible |

## Success Metrics

- [ ] Zero breaking changes for existing installations
- [ ] New installations work with CDN out-of-box
- [ ] Page load time improved or equal to v2
- [ ] Editor preview latency < 500ms
- [ ] All automated tests passing
- [ ] No user-reported rendering issues within 30 days
- [ ] Positive community feedback
- [ ] Adoption rate: 50%+ of sites using v4 within 6 months

## Future Enhancements (Not in Scope)

- Server-side rendering for SEO (if requested by community)
- KaTeX option for performance-critical sites
- Custom MathJax extensions
- Math equation editor UI
- LaTeX syntax validation in editor
- Math formula search/indexing

## References

- [MathJax v4 Documentation](https://docs.mathjax.org/en/latest/)
- [MathJax v2 to v3 Migration](https://docs.mathjax.org/en/latest/upgrading/v2.html)
- [MathJax Configuration Options](https://docs.mathjax.org/en/latest/options/index.html)
- [Stack Exchange MathJax Usage](https://math.meta.stackexchange.com/questions/5020/mathjax-basic-tutorial-and-quick-reference)
- [markdown-it Documentation](https://markdown-it.github.io/)

## Timeline Estimate

- **Phase 1-2** (Config + Frontend): 2-3 days
- **Phase 3-4** (Editor + Dynamic): 2-3 days
- **Phase 5** (Markdown-it): 1-2 days
- **Phase 6** (Documentation): 1 day
- **Testing**: 3-4 days
- **Buffer**: 2 days

**Total**: ~12-15 days of development work

## Related Tasks

- Markdown upgrade (markdown2 → markdown-it): Already in progress
- Editor modernization: Future task
- Accessibility improvements: Synergizes with MathJax v4 features
