# Markdown Upgrade - Consolidated Status

This document synthesizes findings from the audit of commits, task files, and uncommitted work
on the `markdown-upgrade` branch. It serves as the single source of truth for understanding
what has been done, what is in progress, and what remains to be done.

**Last Updated:** [DATE]
**Audit Issues:** See individual bd issue references below

---

## 1. Completed Work

### 1.1 Backend Migration (markdown2 → markdown-it-py)
<!-- Findings from commit audits 1-7 -->

| Commit | Description | bd Issue |
|--------|-------------|----------|
| 8105e56de | Initial WIP: markdown2 → markdown-it migration. Added dependencies (markdown-it-py, mdit-py-plugins, linkify-it-py), refactored markup.py to use MarkdownIt singleton. **Policy change: anonymous users can no longer post links.** PostRevision.html switched from `get_parser()` to `markdown_input_converter()`, losing video/code-friendly/link-patterns features. urlize_html removed from `markdown_input_converter()`. Features not yet implemented: video, code-friendly, link patterns, custom markdown class. | askbot-master-u9s |
| d487c1e7a | **Documentation only.** Added CLAUDE.md (AI assistant guidance) and 5 task planning files for markdown upgrade (overview, assessment, phase1-backend, phase2-frontend, phase3-testing). Plans 3-phase migration, identifies gaps (video plugin, link patterns need writing). | askbot-master-6zh |
| 1e01ee226 | **Documentation only.** Added MathJax upgrade plan (v2→v4) and markdown-mathjax integration guide. Updated phase docs with math delimiter protection tasks. Identifies problem: markdown mangles LaTeX in `$...$`. Solution: code-friendly mode + math delimiter plugin. | askbot-master-jrw |
| 4c3ad65bd | **Key milestone: completed backend migration.** RESTORES features lost in commit 1. Removed markdown2 dependency. Upgraded markdown-it-py 2.2.0→4.0.0, mdit-py-plugins 0.3.5→0.5.0. Added pygments for syntax highlighting. New plugins: video_embed.py (YouTube/Vimeo/Dailymotion), link_patterns.py (auto-linking). Refactored markup.py with singleton pattern, Pygments highlighting, integrated footnotes/tasklists. Code-friendly mode implemented but **disables ALL emphasis** (both `*` and `_`) - potential UX regression. **TODOs left:** Math delimiter protection plugin; re-enable asterisk emphasis in code-friendly mode. Added 3 test files (309 lines total). | askbot-master-6nm |
| 1a736db26 | **Test quality improvements + PARTIAL REVERT of linkify.** Converted all test assertions from string matching to BeautifulSoup structural validation (+295 lines). **Functional changes:** switched from `gfm-like` to `commonmark` preset (manually enabled table/strikethrough); **REVERTED** linkify approach - disabled markdown-it linkify, restored `urlize_html(trim_url_limit=40)` from pre-commit-4 era; removed explicit `sanitize_html()` (relies on urlize_html). Typographer disabled. Added task file (848 lines). Deleted the_diff. | askbot-master-n1c |
| 339de84e0 | **Test cleanup.** Removed 3 linkify tests from `test_markup.py` (-49 lines). Tests removed: `test_full_link_converts_to_anchor`, `test_protocol_less_link_converts_to_anchor`, `test_convert_mixed_text`. First two are covered by commit 6's `test_markdown_truncate_links_plugin.py`. **Coverage gaps:** (1) Raw HTML block handling (`<p>`, `<pre>` tags not linkified) - NOT covered by new tests (which test fenced markdown code blocks); (2) Test type shift: removed tests used full `markdown_input_converter()` pipeline (with sanitization), new tests only test markdown rendering directly. | askbot-master-8zl |
| 09a928f28 | **Documentation only.** Added comprehensive MathJax implementation plan (`tasks/markdown-upgrade-mathjax-support.md`, 754 lines). Identifies problems with current crude `md.disable('emphasis')` workaround. Proposes `math_protect.py` plugin to detect `$...$`/`$$...$$` delimiters FIRST, create verbatim tokens, prevent linkify/patterns/emphasis from processing math. Includes: technical design, token structure, plugin ordering, edge cases, 14 unit tests + 3 integration tests outlined, 6 implementation phases, frontend JS guide. Ready for implementation. | askbot-master-2bt |

**Summary:**
Backend migration is substantially complete. From overview document (askbot-master-uga) Phase 1 checklist:

| Criteria | Status | Commit |
|----------|--------|--------|
| markdown-it-py 4.0.0 | ✅ Done | 4c3ad65bd |
| Video embedding plugin | ✅ Done | 4c3ad65bd |
| Link patterns plugin | ✅ Done | 4c3ad65bd |
| Code-friendly mode | ⚠️ Buggy | 4c3ad65bd (disables ALL emphasis) |
| Pygments highlighting | ✅ Done | 4c3ad65bd (markup.py imports verified) |
| 95%+ code coverage | ❌ Unverifiable | No coverage tooling configured |
| All backend tests passing | ✅ Done | All commits (35/35 pass) |
| Manual testing | ❓ Not documented | No records exist |

**Note:** Overview document shows Phase 1 as "🟡 Planning" but commit audits show 80%+ completion. Document is outdated and should be updated.

**Missing from overview:** MathJax/math delimiter protection (major work item), linkify/truncate_links plugin

**Phase 1 Gate Assessment (askbot-master-uga):**

Gate requirement: "100% backend tests passing, custom plugins working"

| Criterion | Status | Verification |
|-----------|--------|--------------|
| Backend tests passing | ✅ PASS | askbot-master-35c: 35/35 tests pass |
| Video plugin `@[youtube](id)` | ✅ PASS | video_embed.py line 5 matches spec |
| Link patterns `#bug123` | ✅ PASS | link_patterns.py line 8 matches spec |
| Code-friendly mode | ⚠️ PARTIAL | Disables ALL emphasis, not just `_` |
| Math delimiter protection | ✅ PASS | math_extract.py commit-ready |

**Gate Status: MOSTLY PASSED** - Only blocker is code-friendly emphasis bug (issue askbot-master-6nm)

**Rollback Strategy NOT Implemented:**
- Overview specifies `MARKDOWN_BACKEND` env variable feature flag
- Grep search found 0 implementations in askbot/conf/*.py
- Required before Phase 3 deployment

### 1.2 Linkify Implementation
<!-- Findings from commit audit 6 and task file audit -->

| Commit | Description | bd Issue |
|--------|-------------|----------|
| ea2f58fa4 | **Re-enabled linkify with native plugin solution.** REVERSES commit 5's decision to use `urlize_html`. Key changes: (1) Re-enabled markdown-it linkify (`{'linkify': True}`); (2) NEW `truncate_links.py` plugin (134 lines) - truncates auto-linkified URLs to 40 chars, adds `title` attribute for accessibility, uses Django's truncation algorithm; (3) Removed `urlize_html` post-processing; (4) Added explicit `sanitize_html()` call. Comprehensive tests: 260 lines for truncation plugin, 43 lines integration tests. Task file added (500 lines). | askbot-master-6ts |

**Summary:** Linkify implementation went through two iterations:
1. Commit 5 disabled markdown-it linkify and restored Django's `urlize_html` as post-processing
2. Commit 6 reversed this, implementing a markdown-it-native solution with a custom `truncate_links.py` plugin

The final solution processes URLs at the markdown token level rather than post-processing HTML, providing:
- Better code block protection (URLs in `backticks` and fenced blocks not linkified)
- Fuzzy URL detection (example.com, www.example.com auto-link)
- 40-char truncation with ellipsis matching Django's urlize trim_url_limit
- Accessibility via `title` attribute on truncated links

**Task File Audit (askbot-master-4gc):**

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation (8 items) | ✅ Complete | All items verified done |
| Testing (12 items) | ⚠️ ~90% | 4 gaps identified (see below) |
| Documentation (9 items) | ❌ Outdated | Line counts, success criteria, next steps all stale |
| Task file header | ❌ Outdated | Says "Testing Pending" but 31/31 tests pass |

**Test Results:** 31/31 pass
- 16/16 unit tests (`test_markdown_truncate_links_plugin.py`)
- 12/12 integration tests (`test_markdown_integration.py`) - includes `test_linkify_with_truncation`
- 3/3 markup tests (`test_markup.py`)

**Checklist Item Mapping:**

| Task File Testing Item | Actual Test | Status |
|------------------------|-------------|--------|
| inline code protection | test_inline_code_protection | ✅ |
| code block protection | test_code_block_protection | ✅ |
| URL truncation 40 chars | test_url_truncation_at_40_chars | ✅ |
| title attribute | test_title_attribute_on_truncated_url | ✅ |
| fuzzy link detection | test_fuzzy_link_detection | ✅ |
| www. detection | test_www_detection | ✅ |
| HTML links unchanged | test_anchor_stays_untouched | ✅ |
| markdown links unchanged | test_markdown_links_unchanged | ✅ |
| raw HTML block protection | *(was test_convert_mixed_text)* | ❌ Gap |
| email auto-linking | *(not tested)* | ❌ Gap |
| full pipeline w/sanitization | *(integration uses md.render())* | ❌ Gap |
| javascript: URL rejection | *(not tested)* | ❌ Gap |

**Coverage Gaps (4 identified):**

| Gap | Description | Severity | Notes |
|-----|-------------|----------|-------|
| Raw HTML blocks | URLs in `<p>`, `<pre>` not tested | Low | test_convert_mixed_text removed in 339de84e0 |
| Email auto-linking | `user@example.com` → `mailto:` | Medium | linkify-it-py default, no test |
| Full pipeline | Integration tests use `md.render()` not `markdown_input_converter()` | Low | sanitization not tested |
| javascript: URLs | Security: rejection not tested | Medium | linkify-it-py rejects by default, not verified |

**Task File Documentation Discrepancies:**

| Item | Task File Claims | Actual |
|------|------------------|--------|
| truncate_links.py lines | 119 | 134 |
| Plugin location in markup.py | lines 127-131 | lines 132-134 |
| Success Criteria | 4 items marked ⏳ | All 7 are ✅ |
| Next Steps | 6 TODOs listed | All 6 are DONE |

**STALE CODE COMMENT (test_markup.py:76-80):**
```
Known to fail against:
    example.com    ← STALE: NOW WORKS with linkify!
```
This comment predates the linkify migration and is now misleading.

**Behavioral Changes (Impact on Existing Content):**
- **Fuzzy links:** `example.com` now auto-links → existing posts render differently
- **Email links:** `user@example.com` → `mailto:` → existing posts render differently

**urlize Handling Verified:**
- `urlize_html` from askbot.utils.html: correctly removed from markdown pipeline ✅
- Django's `urlize`: still imported, used only in `plain_text_input_converter()` (correct)

**Connections:** Confirms Open Questions #2 (sanitization), #3 (raw HTML blocks)

**Recommended Actions:**
1. HIGH: Update/remove stale comment in test_markup.py:76-80
2. MEDIUM: Update task file header, success criteria, next steps
3. LOW: Add email auto-linking test
4. LOW: Add javascript: URL rejection test

### 1.3 Other Completed Items
<!-- Any other completed work discovered during audit -->

---

## 2. In Progress (Uncommitted Work)

### 2.1 MathJax v2 Implementation
<!-- Findings from uncommitted audit askbot-master-35c -->

**Files:**
- [x] `askbot/utils/markdown_plugins/math_extract.py` (337 lines)
- [x] `askbot/utils/markdown_plugins/dollar_escape.py` (42 lines)
- [x] `askbot/tests/test_markdown_mathjax.py` (386 lines)
- [x] `askbot/utils/markup.py` (modifications to `markdown_input_converter()`)

**Status: COMMIT-READY**

**Test Results:**
- All 35 tests pass (2 skipped for documented edge cases)
- No regressions in existing `test_markup.py` tests (3/3 pass)

**Architecture (Stack Exchange approach):**

| Phase | Function | Description |
|-------|----------|-------------|
| 1 | `protect_code_dollars()` | Replace `$` with `~D` inside backtick code spans |
| 2 | `extract_math()` | Extract math to `@@N@@` tokens via state machine |
| 3 | `escape_dollars()` | Convert `\$` → `&dollar;` in text regions |
| 4 | `md.render()` | Standard markdown processing |
| 5 | `restore_code_dollars()` | Reverse `~D` → `$` in code spans |
| 6 | `restore_math()` | Replace `@@N@@` tokens with original math |
| 7 | `sanitize_html()` | XSS protection |

**Key Improvements Over v1:**
1. **FOUC solved:** Escaped `\$` renders immediately as `&dollar;` HTML entity (no MathJax JS dependency)
2. **Complete delimiter support:** `$...$`, `$$...$$`, `\[...\]`, `\begin{env}...\end{env}`
3. **LaTeX `\$` preserved in math:** Currency in equations like `$cost = \$50$` works correctly
4. **Code span protection:** `$variable` in backticks not treated as math

**Known Limitations (verified by testing):**

| Issue | Severity | Details |
|-------|----------|---------|
| Math ending with `\\` not extracted | Edge case | `$x^2 \\$` fails - closing `$` seen as escaped |
| `\\$` in text produces wrong output | Edge case | `\\$100` → `&amp;dollar;100` instead of `\$100` |
| `\(` and `\)` delimiters not supported | Missing feature | Common LaTeX inline math syntax |
| Empty `$$` not handled | Edge case | 2 tests skipped, documented |
| `~D` collision | Very rare | User-written `~D` in code becomes `$` |

**What Works Well:**
- ✅ Core delimiters: `$...$`, `$$...$$`, `\[...\]`, `\begin{env}...\end{env}`
- ✅ Single `\$` escape in text → `$` (main use case)
- ✅ LaTeX `\$` inside math preserved (e.g., `$cost = \$50$`)
- ✅ Code spans AND fenced code blocks protected
- ✅ `\\` in middle of math works (e.g., `$a \\ b$`)

**Verdict: COMMIT-READY** - Core functionality works; edge cases are rare and documented.

**bd Issue:** askbot-master-35c

---

## 3. Planned But Not Started

### 3.1 Phase 2: Frontend Migration
<!-- Findings from phase2 task file audit askbot-master-5i7 -->

**From Overview (askbot-master-uga):** Phase 2 involves replacing Showdown.js (~2011) with markdown-it.js for frontend consistency with backend.

**Task File Audit (askbot-master-5i7):**

**Document Status:** NOT STARTED - VALID with CRITICAL GAPS

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 4 | Sanitization missing, MathJax mismatch, truncate_links missing, rollback contradiction |
| HIGH | 2 | Syntax highlighting mismatch, escape_dollars missing |
| MEDIUM | 4 | Preset comment, element ID, settings naming, error handling |
| LOW | 2 | Template reference, CDN SRI hashes |

**Current Files Verified:**
- `askbot/media/wmd/askbot_converter.js` - 67 lines (uses `Markdown.getSanitizingConverter()`)
- `askbot/jinja2/meta/markdown_javascript.html` - 9 lines (loads Markdown.Converter.js)
- `askbot/media/wmd/Markdown.Sanitizer.js` - exists (used by current, NOT by proposal)
- `askbot/utils/markup.py` - backend pipeline with `sanitize_html()` at end

**⚠️ CRITICAL: Sanitization Missing from Proposed Code (SECURITY)**

| Current (askbot_converter.js:14) | Document's Proposal (lines 343-357) |
|----------------------------------|-------------------------------------|
| `new Markdown.getSanitizingConverter()` | `this._md.render(text)` - NO sanitizer! |

Document says keep `Markdown.Sanitizer.js` (line 32) but new `makeHtml()` doesn't call any sanitizer.
Backend calls `sanitize_html()` at end of pipeline (markup.py:347).

**Impact:** XSS vulnerability if implemented as-is.

**⚠️ CRITICAL: MathJax Processing Mismatch (askbot-master-0pk, askbot-master-5i7)**

Backend (markup.py:299-349) uses 7-phase preprocessing:
1. `protect_code_dollars()` → Replace `$` with `~D` in code spans
2. `extract_math()` → Extract math to `@@N@@` tokens
3. `escape_dollars()` → Convert `\$` → `&dollar;`
4. `md.render()` → Markdown processing
5. `restore_code_dollars()` → `~D` → `$` in output
6. `restore_math()` → `@@N@@` → original math
7. `sanitize_html()` → XSS protection

Document's frontend (lines 238-307): Simple inline/block math rules that pass content through to MathJax client-side.

**Impact:** Preview will NOT match saved content.

**Phase 2 Options:**
1. Port math_extract.py logic to JavaScript (complex)
2. Use simplified frontend math handling (may cause preview/save differences)
3. Send preview through backend API (performance cost)

**⚠️ CRITICAL: Missing truncate_links.js Plugin**

- Backend `truncate_links.py` (134 lines) truncates auto-linked URLs to 40 chars with title attribute
- Document lists video.js and link-patterns.js but NOT truncate-links.js
- **Result:** Frontend shows full URLs, backend shows truncated

**⚠️ CRITICAL: Rollback Strategy Contradiction**

| Document | Says |
|----------|------|
| Overview (line 141) | "Showdown files kept as fallback during transition" |
| Phase 2 Task 2.7 (lines 969-990) | DELETE Showdown: `git rm showdown-min.js` |
| Phase 3 (line 1000) | Rollback requires Showdown |

**Impact:** If Phase 2 deletes Showdown and Phase 3 rollback needed, NO frontend fallback exists.

**HIGH: Syntax Highlighting Output Mismatch**

| Backend (Pygments) | Frontend (highlight.js) |
|--------------------|-------------------------|
| `<div class="highlight">...</div>` | `<pre><code class="hljs">...</code></pre>` |
| CSS: `.highlight .k`, `.highlight .n` | CSS: `.hljs-keyword`, `.hljs-name` |

**Impact:** Preview styling won't match saved content.

**HIGH: Escaped Dollar Handling Missing**

- Backend `escape_dollars()` converts `\$` → `&dollar;` HTML entity (instant render)
- Document relies on MathJax client-side `processEscapes`
- **Result:** FOUC - `\$100` shows backslash until MathJax loads

**MEDIUM Issues:**

| Issue | Document | Actual |
|-------|----------|--------|
| Preset comment | 'gfm-like' (line 154) | Backend uses 'commonmark' |
| Element ID | 'wmd-preview' (line 377) | Current uses 'previewer' (line 23) |
| Settings access | `window.askbot.settings.x` | Current uses `askbot['settings']['x']` |
| Error handling | Throws if markdown-it missing | Current silently falls back |

**LOW Issues:**
- Template reference says `showdown-min.js`, actual: `Markdown.Converter.js`
- CDN links (lines 858-862) lack SRI integrity hashes

**Success Criteria (6 checkboxes in overview):**
- [ ] markdown-it.js loaded and configured
- [ ] askbot_converter.js rewritten and tested
- [ ] Live preview matches backend exactly
- [ ] All JavaScript tests passing
- [ ] WMD editor integration working
- [ ] MathJax integration preserved

**Missing Requirements (not in document):**
- MR-1: truncate_links.js plugin
- MR-2: escape_dollars.js (or accept FOUC)
- MR-3: Code span dollar protection
- MR-4: HTML sanitization
- MR-5: Frontend rollback mechanism

**Gate Requirement:** Frontend renders identical to backend in all test cases

**Recommended Actions (Priority Order):**
1. **CRITICAL/SECURITY:** Add sanitization to makeHtml() - call Markdown.Sanitizer or add DOMPurify
2. **CRITICAL:** Add task for MathJax parity - port math_extract.py OR backend preview API
3. **CRITICAL:** Add task "Write truncate_links.js plugin"
4. **CRITICAL:** Resolve rollback contradiction - keep Showdown until Phase 3 validated
5. **HIGH:** Document highlight.js vs Pygments output differences OR implement compatible highlighter
6. **HIGH:** Add escape_dollars.js or document FOUC as acceptable
7. **MEDIUM:** Fix preset comment, element IDs, settings access patterns
8. **SECURITY:** Add SRI hashes to CDN links

**bd Issue:** askbot-master-5i7

### 3.2 Phase 3: Testing & Deployment
<!-- Findings from phase3 task file audit askbot-master-p48 -->

**From Overview (askbot-master-uga):** Final phase for safe production migration with validation.

**Task File Audit (askbot-master-p48):**

**Document Status:** NOT STARTED - VALID with CRITICAL GAPS

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 3 | MathJax tests use wrong function, rollback assumes markdown2, sanitization comparison |
| HIGH | 3 | Wrong directory refs, unrealistic exit criteria, benchmark location |
| MEDIUM | 4 | Time estimates, missing imports, visual tool undecided, docs/ path |
| LOW | 2 | Timeline estimates in deployment, Known Issues incomplete |

**Task Structure (7 tasks):**

| Task | Description | Lines | Status |
|------|-------------|-------|--------|
| 3.1 | Migration Test Script | 49-448 | Valid structure |
| 3.2 | Visual Regression Testing | 452-550 | Tool undecided |
| 3.3 | Performance Benchmarking | 554-642 | Good thresholds |
| 3.4 | Edge Case Testing | 645-826 | **CRITICAL: MathJax tests broken** |
| 3.5 | Update Documentation | 830-954 | Paths may not exist |
| 3.6 | Create Rollback Plan | 958-1018 | **CRITICAL: markdown2 removed** |
| 3.7 | Staged Deployment | 1021-1069 | Valid approach |

**⚠️ CRITICAL: MathJax Edge Case Tests Use Wrong Function (lines 755-812)**

Document's MathJax tests:
```python
md = get_md_converter()
html = md.render(text)  # WRONG - bypasses MathJax preprocessing!
```

Actual MathJax pipeline in `markdown_input_converter()` (markup.py:299-349):
1. `protect_code_dollars()` → Replace `$` with `~D` in code spans
2. `extract_math()` → Extract math to `@@N@@` tokens
3. `escape_dollars()` → Convert `\$` → `&dollar;`
4. `md.render()` → Markdown processing
5. `restore_code_dollars()` → `~D` → `$` in output
6. `restore_math()` → `@@N@@` → original math
7. `sanitize_html()` → XSS protection

**Impact:** All MathJax tests in document will FAIL or produce wrong results.

**Fix:** Replace `md.render(text)` with `markdown_input_converter(text)` in all MathJax tests.

**⚠️ CRITICAL: Rollback Strategy Invalid (lines 969-1004)**

| Document Claims | Actual State |
|-----------------|--------------|
| `MARKDOWN_BACKEND=markdown2` fallback | markdown2 REMOVED from askbot_requirements.txt |
| Feature flag switching | `MARKDOWN_BACKEND` NOT IMPLEMENTED (0 grep matches) |
| Instant rollback | Requires reinstalling markdown2 (not documented) |

**Rollback options:**
1. Implement `MARKDOWN_BACKEND` feature flag AND re-add markdown2 as optional dependency
2. Git revert (documented in Task 3.6 as backup option)
3. Accept no instant rollback; rely on git revert only

**HIGH: Directory References Wrong (lines 27-46)**

| Document Says | Actual |
|---------------|--------|
| `source env/bin/activate` | `env312/` exists (git status) |
| `cd askbot_site/` | Needs verification |

**Migration Test Script (Task 3.1) - Valid Structure:**
- Django management command at `askbot/management/commands/test_markdown_migration.py`
- Uses `PostRevision` to get original markdown
- Uses `difflib.SequenceMatcher` for similarity (default threshold 95%)
- HTML report with diff visualization
- Progress reporting every 100 posts
- Configurable threshold, sample size, specific post ID

**Performance Benchmarks (Task 3.3) - Good Thresholds:**

| Content Type | Threshold |
|--------------|-----------|
| Short text | <5ms |
| Medium text | <50ms |
| Long text | <200ms |
| 95th percentile | <2x median |

**Exit Criteria (lines 1103-1125):**
- [ ] Migration test script shows 99%+ similarity
- [ ] Visual regression tests show <1% differences
- [ ] Performance benchmarks met
- [ ] All edge case tests passing
- [ ] Documentation complete and reviewed
- [ ] Rollback procedure tested
- [ ] Staging environment stable for 1 week
- [ ] Sign-off from: Technical Lead, QA Lead, Product Owner, DevOps Lead

**Dependencies on Unimplemented Infrastructure:**
- Migration script: NOT CREATED (status file Open Question #8)
- Visual regression tools: NOT SET UP (status file Open Question #7)
- `MARKDOWN_BACKEND` feature flag: NOT IMPLEMENTED
- Staging environment: NOT DOCUMENTED

**Success Criteria (6 checkboxes in overview):**
- [ ] Migration script validates all existing posts
- [ ] <1% visual differences detected
- [ ] Performance benchmarks meet targets
- [ ] Documentation updated
- [ ] Stakeholder approval for deployment
- [ ] Rollback procedure tested

**Gate Requirement:** <1% rendering differences, zero critical bugs

**Recommended Actions (Priority Order):**
1. **CRITICAL:** Fix MathJax tests to use `markdown_input_converter()` not `md.render()`
2. **CRITICAL:** Implement `MARKDOWN_BACKEND` feature flag OR document markdown2 reinstall for rollback
3. **HIGH:** Verify/fix directory references (env vs env312, askbot_site existence)
4. **HIGH:** Choose visual regression tool (BackstopJS vs Playwright) and document setup
5. **MEDIUM:** Remove time estimates from document
6. **MEDIUM:** Verify `docs/` directory exists or update documentation paths

**bd Issue:** askbot-master-p48

### 3.3 Other Planned Items
<!-- Any other planned work from task files -->

---

## 4. Reverted/Abandoned Work

### 4.1 MathJax v1 (Plugin-based approach)

**Commits:** d625f5507 (implemented), a40000d1c (reverted)
**bd Issues:** askbot-master-tk7 (implementation audit), askbot-master-mps (revert audit)

**What Was Implemented:**
Commit 9 (d625f5507) introduced a markdown-it-py plugin approach for MathJax delimiter protection:

| File | Lines | Description |
|------|-------|-------------|
| `math_protect.py` | 251 | New plugin with inline/block math rules |
| `test_markdown_math_plugin.py` | 590 | Comprehensive test suite (30+ tests) |
| `markup.py` | +14/-13 | Integration with `get_md_converter()` |
| `markdown-mathjax-implementation-v2.md` | 630 | Plan for alternative approach |

**Technical Approach:**
- `math_inline_rule()` - Inline parser rule for `$...$` detection
- `math_block_rule()` - Block parser rule for `$$...$$` detection
- Registered BEFORE backticks/fence rules to intercept math first
- Creates `math_inline`/`math_block` tokens that other plugins skip
- Handles escaped `\$`, single dollar after space, newline boundaries

**Test Coverage Strengths:**
- URLs inside math NOT linkified (critical)
- Link patterns inside math NOT processed (critical)
- Underscore/asterisk emphasis protection in math
- Escaped dollar handling
- Integration with code blocks

**Critical Limitations (from v2 plan document):**

1. **FOUC Problem Not Solved:** `\$100` stored in HTML shows backslash until MathJax loads (Flash of Unescaped Content). v1 relies on MathJax's `processEscapes: true` client-side, causing flicker, broken display if MathJax blocked, SEO/accessibility issues.

2. **Missing LaTeX Delimiters:** Only supports `$...$` and `$$...$$`. Does NOT support `\[...\]` or `\begin{...}\end{...}` which Stack Exchange handles.

3. **Code-Friendly Mode Regression:** When MathJax enabled, `md.disable('emphasis')` disables BOTH `*` and `_` emphasis. Comment says asterisk could be re-enabled safely with math protection, but TODO never implemented.

4. **Block Math Parsing Edge Cases:** Simple `'$$' in line_content` string search can incorrectly close math on `$$` anywhere in line, not just at start. No escaped `\$$` handling in blocks.

5. **Plugin Ordering Uncertainty:** Comment says "Register inline rule FIRST" but also "after escape" - reveals uncertainty about correct rule ordering.

**Critical Implementation Bugs (from code review):**

1. **CRITICAL: Mid-paragraph `$$` not handled.** Inline rule rejects `$$` (defers to block rule), but block rule ONLY matches `$$` at line start. Result: `text $$math$$ text` is NOT recognized as display math. Docstring falsely claims "Adjacent: $$x$$ → Display math".

2. **Test/Implementation Contradiction:** Tests with `@with_settings(ENABLE_MATHJAX=True)` expect asterisk emphasis (`*y*` → `<em>y</em>`) to work, but `markup.py` does `md.disable('emphasis')` when MathJax enabled. Either tests never passed or singleton/settings caching masks the issue.

3. **Content after closing `$$` is lost.** In multiline mode: `$$ text after` discards "text after" - rule just breaks and advances state.line without processing remainder.

4. **Escape handling oversimplified.** Single-char lookback `state.src[pos - 1] == '\\'` can't distinguish `\\$` (escaped backslash + dollar) from `\$` (escaped dollar).

5. **Missing test coverage:** No tests for mid-paragraph `$$`, content after closing `$$`, multiple backslash scenarios, or `$$` mid-line in multiline mode.

6. **TEST SUITE INVALID:** Multiple tests with `@with_settings(ENABLE_MATHJAX=True)` expect asterisk emphasis (`*y*` → `<em>`) to work. But `md.disable('emphasis')` is called when MathJax enabled, disabling ALL emphasis. Tests include `test_escaped_dollar_not_opening_delimiter`, `test_escaped_dollar_literal_text`, `test_escaped_dollars_both_sides`. These tests CANNOT pass as written - suggests tests were never run successfully or test INTENDED behavior that was never implemented (the TODO to re-enable `*`).

7. **Double-escaped backslash bug:** `$x\\$` (content `x\` with closing `$`) fails - code sees `\` before `$` and thinks it's escaped, but `\\` is an escaped backslash. No test coverage.

8. **Multiple `$$` on same line:** `$$x$$y$$` - second pair `y$$` is consumed but not processed.

9. **Singleton settings invalidation:** Cached converter doesn't refresh when `ENABLE_MATHJAX` changes at runtime.

**UNUSUAL: Commit Documents Its Own Obsolescence**

The commit includes a 630-line v2 plan that explicitly argues AGAINST the plugin approach:

| Aspect | v1 Plugin | v2 Preprocessing | Winner |
|--------|-----------|------------------|--------|
| Complexity | Medium | Low | v2 |
| Edge cases | Many | Few | v2 |
| Proven approach | Novel | Stack Exchange | v2 |
| State tracking | Required | Not needed | v2 |

v2 document concludes: "Decision: New approach is simpler, proven, and more robust despite being less 'pure' in design."

**Why Reverted:** The v1 implementation was essentially a proof-of-concept that demonstrated the limitations of the plugin approach. The v2 preprocessing approach (Stack Exchange style) was planned from the start as the better solution.

**Superseded By:** MathJax v2 implementation (uncommitted work in section 2.1)

---

## 5. Obsolete/Superseded Documentation

<!-- Task files that are no longer relevant -->

| File | Status | Superseded By |
|------|--------|---------------|
| markdown-upgrade-phase1-backend.md | COMPLETED | Actual commits (see 1.1) |
| markdown-upgrade-mathjax-support.md | OBSOLETE | markdown-mathjax-implementation-v2.md + actual uncommitted work |

**Note on markdown-upgrade-phase1-backend.md (askbot-master-d30):**
- **Status:** COMPLETED - Implementation guide that served its purpose
- **Role:** Detailed task breakdown for Phase 1 backend migration
- **Task Completion:**
  - Task 1.1 (Dependencies): ✅ Done - askbot/__init__.py and askbot_requirements.txt both updated, markdown2 removed
  - Task 1.2 (Pygments): ✅ Done (commit 4c3ad65bd)
  - Task 1.3 (Video Plugin): ✅ Done (commit 4c3ad65bd)
  - Task 1.4 (Link Patterns): ✅ Done (commit 4c3ad65bd)
  - Task 1.5 (get_md_converter): ⚠️ Done with deviations (code-friendly bug, math via preprocessing not plugin)
  - Task 1.6 (Integration Testing): ⚠️ Tests pass but coverage tooling not automated
  - Task 1.7 (Update Tests): ✅ Done (35/35 pass)
- **Exit Criteria Assessment:**
  | Criterion | Status | Notes |
  |-----------|--------|-------|
  | Tests passing | ✅ | 35/35 pass |
  | Coverage ≥95% | ❓ | .coveragerc exists, not automated |
  | Manual validation | ❌ | No documentation exists |
  | Performance benchmark | ❌ | No benchmark tests exist |
  | Code review | ❓ | No documentation exists |
  | Documentation | ❌ | README, migration notes missing |
- **Test Implementation Exceeded Document:**
  - Document suggested ~284 lines of tests
  - Actual: 1,212 lines (4.3x more)
  - Improved with BeautifulSoup structural validation
  - Added 2 test files not in document (mathjax, truncate_links)
- **Files Implemented But NOT In Document:**
  | File | Lines | Purpose |
  |------|-------|---------|
  | truncate_links.py | 134 | URL display truncation |
  | math_extract.py | 337 | MathJax preprocessing |
  | dollar_escape.py | 42 | Escaped dollar handling |
  | test_markdown_mathjax.py | 385 | MathJax tests |
  | test_markdown_truncate_links_plugin.py | 260 | Truncation tests |
- **Key Deviations from Plan:**
  1. Linkify/truncate_links (commits 5-6) not anticipated - MAJOR omission
  2. MathJax uses preprocessing approach (math_extract.py) not plugin - different architecture
  3. Preset changed from 'gfm-like' to 'commonmark' with manual table/strikethrough enables
  4. sanitize_html() call added at end of pipeline but not documented
- **Code Example Inaccuracies:**
  1. render_video_embed() signature wrong: doc has `(tokens, idx, options, env, renderer)`, actual has `(self, tokens, idx, options, env)` - doc's version would NOT work
  2. Line references wrong: doc says `markup.py:30-47`, actual get_md_converter() at lines 82-154
  3. Token import differs: doc uses `state.Token`, actual imports from `markdown_it.token`
- **Documentation Deliverables Missing:**
  - README for markdown_plugins module - NOT CREATED
  - Migration notes for developers - NOT CREATED
- **Security Issue (shared with actual code):**
  - highlight_code fallback doesn't HTML-escape `code` or `lang` parameters (markup.py lines 71, 76)
- **Stale Code Comments:**
  - TODO in get_md_converter() (lines 144-151) for math protection - but it's implemented in markdown_input_converter()
  - Docstring says "GFM-like preset" (line 87) but code uses 'commonmark' (line 105)
- **Environment Verified:**
  - env-md/ directory EXISTS (created Oct 5)
  - askbot_site/ directory EXISTS
  - Document's venv instructions were followed
- **Still Valid:**
  - .coveragerc exists; document's coverage commands work
  - Test file structure matches document's suggestions
  - Plugin architecture approach correct (despite signature details)
- **Outdated Elements:** Time estimates throughout, unchecked checkboxes (work is done)
- **Recommendation:** Archive as historical reference; do not use for implementation

**Note on markdown-upgrade-mathjax-support.md (askbot-master-1c0):**
- **Status:** PARTIALLY OBSOLETE - Architecture obsolete, functional requirements still valid
- **Role:** Planning document for MathJax delimiter protection (plugin approach)
- **Document Relationships:**
  | Document | Focus | Approach |
  |----------|-------|----------|
  | background-for-escaped-delimiters-mathjax.md | Dollar escape only | Inline rule |
  | markdown-upgrade-mathjax-support.md (THIS) | Math protection | Plugin inside markdown-it |
  | markdown-mathjax-implementation-v2.md | Both concerns | Preprocessing outside markdown-it |

  Note: v2 says "Supersedes: Background document approach" referring to background document, not this file. However, this file's APPROACH is also superseded by v2.
- **Why Architecture Obsolete:**
  - v1 plugin approach was implemented (commit d625f5507) then reverted (commit a40000d1c)
  - Critical bugs: mid-paragraph `$$`, FOUC, emphasis test failures
  - v2 preprocessing approach chosen as simpler, proven (Stack Exchange style)
- **What's Still Valid:**
  - Problem statement (lines 10-50): correctly identifies protection requirements
  - Design requirement: "NO markdown processing inside delimiters"
  - Testing strategy: identifies critical test cases (see gaps below)
  - Frontend JS parity requirement (Phase 2 deliverable)
- **What's Obsolete:**
  - `math_protect.py` plugin design and code examples
  - Integration examples (actual uses preprocessing, not plugin)
  - 6-phase implementation plan
- **⚠️ CRITICAL: Test Coverage Gaps Identified:**
  Tests proposed in this document that are MISSING from actual test_markdown_mathjax.py:
  | Proposed Test | Purpose | Status |
  |---------------|---------|--------|
  | test_math_with_url | URL inside math not linkified | ❌ NOT TESTED |
  | test_math_with_www | www. inside math not linkified | ❌ NOT TESTED |
  | test_math_with_fuzzy_link | example.com inside math | ❌ NOT TESTED |
  | test_math_with_pattern | link patterns inside math | ❌ NOT TESTED |
  | test_math_with_underscores | underscore emphasis in math | ❌ NOT TESTED |
  | test_math_with_asterisk | asterisk emphasis in math | ❌ NOT TESTED |
  | test_math_linkify_no_interference | Integration test | ❌ NOT TESTED |
  | test_math_patterns_no_interference | Integration test | ❌ NOT TESTED |

  These are marked "⭐ Critical" in document - should be added to test suite.
- **Recommendation:**
  1. Archive as historical reference for v1 approach
  2. Create work issue for missing critical tests (linkify/patterns/emphasis in math)
  3. Keep as reference for frontend JS implementation (Phase 2)

**Note on markdown-upgrade-overview.md (askbot-master-uga):**
- **Status:** OUTDATED but NOT OBSOLETE
- **Role:** Master planning document - still serves as overall roadmap
- **Issues:** "Current State" and Phase 1 status do not reflect actual commit progress
- **Recommendation:** Update document to reflect completed work before Phase 2 begins

**Note on markdown-upgrade-assessment.md (askbot-master-0pk):**
- **Status:** PARTIALLY OUTDATED - Phase 1 sections complete, Phase 2/3 still relevant
- **Role:** Foundational research document - explains WHY decisions were made
- **Value:** Decision rationale, library comparisons, MyST alternative analysis still valid
- **Outdated:** Version numbers (2.2.0→4.0.0), preset (gfm-like→commonmark), "missing implementations" (now done)
- **Key Decisions Documented:**
  1. Use markdown-it over MyST (familiar syntax, lighter)
  2. Conservative phased approach (not aggressive)
  3. Custom plugins for video/link-patterns (no official ports)
  4. Code-friendly via `md.disable('emphasis')`
- **Implementation Progress:**
  - Phase 1 checklist (6 items): 6/6 DONE
  - Phase 2 checklist (4 items): 0/4 (not started)
  - Phase 3 checklist (4 items): 0/4 (not started)
  - Recommended approach (9 items): 3/9 done, 2/9 missing (migration script, content testing)
- **CRITICAL Inaccuracies:**
  1. **MathJax claim WRONG:** Document says "Pass-through (client renders)" but actual implementation does SERVER-SIDE preprocessing via a 7-phase pipeline (protect_code_dollars → extract_math → escape_dollars → md.render → restore_code_dollars → restore_math → sanitize_html)
  2. **Plugin count underestimated:** Anticipated 2 plugins, actually needed 5 (math_extract.py alone is 11,774 bytes - larger than video+link_patterns combined)
  3. **Preset changed:** Document uses 'gfm-like' everywhere but actual code uses 'commonmark'
  4. **linkify-it-py:** Listed as explicit dependency but it's transitive via markdown-it-py
  5. **Code-friendly mode misleading:** Document says "disable underscore emphasis" but `md.disable('emphasis')` disables BOTH `*` AND `_`. Document describes intention but not actual effect.
  6. **truncate_links.py not anticipated:** URL display truncation entirely missing from assessment
  7. **XSS in code examples:** highlight_code fallback doesn't HTML-escape `code` or `lang` parameters
- **Testing Strategy Gaps:** 3 of 5 testing types NOT implemented (migration script, visual comparison, UAT)
- **Architecture Split Not Documented:** MathJax handling happens in markdown_input_converter() preprocessing, NOT as markdown-it plugin - differs from document's unified approach
- **Line Reference Errors:** Document cites `markup.py:30-47` but actual get_md_converter() is at lines 82-154; settings locations also wrong
- **Phase Structure Backwards:** Document puts plugins in Phase 3, but they must be Phase 1 (needed before backend testing)
- **Steps 4-5 Incomplete:** "Test with existing content" and "Create migration script" are Phase 1 completion criteria, not Phase 2 - both UNDONE
- **Plugin Code 5.3x Larger:** Assessment examples total 163 lines; actual implementation is 869 lines (+433%)
- **CDN Security Risk:** Template example uses `@latest` unpinned versions
- **Preprocessing Order Undocumented:** dollar_escape.py must run AFTER extract_math, BEFORE md.render - no plugin, strict ordering required

**Note on background-for-escaped-delimiters-mathjax.md (askbot-master-8lq):**
- **Status:** BACKGROUND DOCUMENT - PARTIALLY OBSOLETE with CRITICAL DESIGN GAP
- **Role:** Requirements analysis and design rationale for escaped dollar handling
- **Document Relationships:**
  - This is the foundational analysis explaining WHY `\$` escaping is problematic
  - Superseded by: markdown-mathjax-implementation-v2.md (which uses preprocessing approach)
  - Still useful as: Requirements reference and problem explanation
- **What's Still Valid:**
  - Problem statement (lines 1-28): correctly identifies core issue - `$` not in CommonMark escape list
  - Multi-layer escaping analysis (lines 30-57): accurate technical breakdown
  - Design decisions: `&dollar;` entity, preserve `\$` in math, no auto-convert
- **What's Obsolete:**
  - **Architecture (lines 149-179):** Proposed inline rule approach NOT used
    - Document proposes: `dollar_escape` inline rule running AFTER math rules
    - Actual: `escape_dollars()` preprocessing runs AFTER `extract_math()` (different order semantics)
  - **Next Steps (lines 258-266):** Items 2-4 done differently; items 5-6 (user docs) NOT DONE
- **⚠️ CRITICAL: Edge Case Verification (lines 171-179):**
  | Case | Input | Doc Expects | Actual | Match |
  |------|-------|-------------|--------|-------|
  | 1 | `\$` | `&dollar;` | `&dollar;` | ✅ |
  | 2 | `\$$` | `&dollar;&dollar;` | `&dollar;$` | ❌ |
  | 3 | `\$\$` | `&dollar;&dollar;` | `&dollar;&dollar;` | ✅ |
  | 4 | `\\$` | `\$` | `\&dollar;` | ❌ (known) |
  | 5 | `$\$100$` | preserve `\$` | ✅ works | ✅ |
  | 6 | `$$\$100$$` | preserve `\$` | ✅ works | ✅ |

  Case 2 note: Implementation treats `\$` atomically, so `\$$` = `\$` + `$` = `&dollar;$`
- **⚠️ CRITICAL: Test Requirement #2 CANNOT PASS (lines 189-192):**
  - Document expects: `\$x = *y*$` → `&dollar;x = <em>y</em>$`
  - **Actual behavior verified:** `extract_math()` runs FIRST and does NOT respect `\$` escaping
  - Result: `$x = *y*$` is extracted as MATH (backslash left outside as `\@@0@@`)
  - The `*y*` is INSIDE math block - markdown won't process emphasis
  - **This is a DESIGN GAP:** Document assumes `\$` prevents math mode, but `extract_math` doesn't check for preceding backslash
- **Mixed escaped/real math BUG:**
  - Input: `Text \$50 and $math$ here`
  - Expected: `$math$` extracted as math, `\$50` escaped
  - Actual: `$50 and $` extracted as math (WRONG - includes literal text!)
- **Open Questions Resolution:**
  - `\\\$` handling (Q1): NOT IMPLEMENTED - behavior undefined
  - Performance (Q2): Mitigated by conditional MathJax check ✅
  - Code blocks (Q3): Correctly handled ✅
  - Plugin interaction (Q4): N/A (preprocessing approach)
- **Recommendations:**
  1. **HIGH:** Create issue for `extract_math` to respect `\$` escaping OR document current behavior as intentional
  2. **MEDIUM:** Update document edge cases to reflect actual behavior
  3. **LOW:** Implement user documentation (Next Steps items 5-6)

**Note on markdown-mathjax-implementation-v2.md (askbot-master-0ae):**
- **Status:** IMPLEMENTED - Planning document that guided the v2 MathJax implementation
- **Role:** Design specification for Stack Exchange-style preprocessing approach
- **Document Header Outdated:** Says "Status: Proposed" but implementation is COMPLETE
- **Architecture Prediction Accuracy:**
  | Aspect | Document Prediction | Actual | Match |
  |--------|---------------------|--------|-------|
  | Token extraction | extract_math() | ✅ Implemented | ✅ |
  | Dollar escape | escape_dollars() | ✅ Implemented | ✅ |
  | restore_math() | Exact impl shown | ✅ Identical | ✅ |
  | MATH_SPLIT regex | Pattern specified | ✅ Identical | ✅ |
  | Code span protection | protect_code_dollars() | ✅ Implemented | ✅ |
- **Phase Structure Analysis:**
  - Document has TWO phase descriptions:
    - Lines 139-173: Conceptual "4-Phase" overview (simplified)
    - Lines 303-334: Code example with 6 phases
  - Actual implementation has 7 phases:
    1. protect_code_dollars() - in doc code example ✅
    2. extract_math() - in doc code example ✅
    3. escape_dollars() - in doc code example ✅
    4. md.render() - in doc code example ✅
    5. **restore_code_dollars() - MISSING from doc code example** ❌
    6. restore_math() - in doc code example ✅
    7. sanitize_html() - in doc code example ✅
  - **Bug in document:** Code example lines 303-334 omits `restore_code_dollars()` step
- **Test Coverage Analysis:**
  | Document | Actual | Ratio |
  |----------|--------|-------|
  | 7 test functions | 31 test functions | 4.4x |
  | ~75 lines | 386 lines | 5.1x |

  All 6 proposed tests implemented + 24 additional tests (utility, extraction, edge cases, MathJax disabled)
- **Test File Location:** Document suggests `test_markdown_dollar_escape.py`, actual is `test_markdown_mathjax.py`
- **Edge Case Coverage:**
  | Document Edge Case | Status |
  |--------------------|--------|
  | Double backslash `\\$100` | ❌ NOT TESTED (doc says "undefined behavior") |
  | Triple backslash `\\\$100` | ❌ NOT TESTED |
  | Math in code spans | ✅ TESTED |
  | URL with dollar | ✅ TESTED |
  | Escaped dollar in math | ✅ TESTED |
- **Document Typo (line 45):** Shows `@@0@@` in output after replaceMath - should show restored `$x = 5$`
- **User Documentation (lines 538-561):** Help text for editor NOT IMPLEMENTED
- **JavaScript Section:** Still valid as Phase 2 frontend migration spec (not yet implemented)
- **Recommendation:**
  1. Update document header from "Proposed" to "Implemented"
  2. Fix code example to add `restore_code_dollars()` step
  3. Add double/triple backslash test cases
  4. Create issue for editor help text (Phase 2 or separate)

**Note on improve-markdown-it-plugin-tests.md (askbot-master-8nq):**
- **Status:** SUBSTANTIALLY COMPLETE - Test improvements implemented with minor gaps
- **Role:** Task file describing BeautifulSoup test improvements needed
- **Test Results:** All 26 tests PASS
- **What Was Improved:**
  - All 17 tests identified in task file converted from weak text assertions to BeautifulSoup structural validation
  - Tests now use `soup = BeautifulSoup(html, 'html5lib')` pattern
  - Tests find actual elements and verify attributes/structure
- **Gaps Identified:**
  Video embed tests don't verify complete structure:
  | Test | Missing Checks |
  |------|----------------|
  | test_youtube_embed | wrapper div class, allowfullscreen attr |
  | test_vimeo_embed | wrapper div class, allowfullscreen attr |
  | test_dailymotion_embed | wrapper div class |
  | test_video_embedding | wrapper div class, allowfullscreen attr |
  | test_multiple_videos | wrapper div classes |
- **Task File Inaccuracy:** Recommended checking `iframe.get('class', [])` for 'video-embed-*' but class is actually on wrapper DIV, not iframe
- **Pending Work (LOW priority):**
  1. Add wrapper div class checks to video embed tests
  2. Add `allowfullscreen` attribute checks to iframe assertions
- **Recommendation:** Mark task file as COMPLETE; create follow-up issue for video embed test completeness if desired

**Note on MD-summary.md (askbot-master-e9i):**
- **Status:** HISTORICAL NOTES - Can be archived
- **Role:** Developer notes listing implemented features and open questions
- **Feature List (lines 4-15):** All features verified working per this status document
- **Open Questions Resolution:**
  | Question | Status | Notes |
  |----------|--------|-------|
  | MathJax TODO/ordering (Q1) | ⚠️ Partial | Implementation complete in `markdown_input_converter()`, but STALE TODO at markup.py:150 causes confusion |
  | Pygments vs frontend (Q2) | ⚠️ Open | Phase 2 issue - output mismatch HIGH severity |
  | Code blocks protected? (Q3) | ✅ Resolved | Verified working |
- **Issues Found:**
  1. **STALE TODO:** markup.py:150 says "Implement math delimiter protection plugin" but it's implemented via preprocessing, not plugin
  2. **Test Architecture:** test_markdown_integration.py MathJax tests (lines 162-215) use `md.render()` which bypasses the actual MathJax preprocessing pipeline
  3. **Missing Tests:** Leading/trailing underscores for code-friendly mode not tested (only middle underscores tested)
  4. **@mentions/video interference:** Analysis shows NO conflict (video converts to iframe before mentionize runs), but no explicit test exists
- **Recommendation:** Archive as historical reference; create follow-up issues for stale TODO removal and test gaps

---

## 6. Open Questions

<!-- Unresolved questions discovered during audit -->

1. **Code-friendly mode behavior:** Should it disable only `_` emphasis (preserving `*` for italic/bold) or all emphasis? Current implementation disables both. (askbot-master-6nm)
2. **Sanitization security:** Is `urlize_html`'s built-in sanitization equivalent to the explicit `sanitize_html()` call that was removed? Should verify no XSS vectors introduced. (askbot-master-n1c)
3. **Raw HTML block test coverage:** Should we add explicit tests for URLs inside raw HTML blocks (`<p>`, `<pre>` tags) not being linkified? Currently relies on markdown-it core behavior without explicit testing. Low risk but a coverage gap. (askbot-master-8zl)
4. **Performance regression:** Overview claims markdown-it is 10-20% slower than markdown2 - has this been benchmarked? No performance tests exist. (askbot-master-uga)
5. **HTML output differences:** Overview warns markdown-it may wrap code blocks differently than markdown2 - has this been verified with existing content? (askbot-master-uga)
6. **Feature flag for rollback:** Overview specifies `MARKDOWN_BACKEND` env variable for rollback strategy - not yet implemented. Required before Phase 3? (askbot-master-uga)
7. **Infrastructure readiness:** Test database with production data copy, staging environment, visual comparison tools (Percy/BackstopJS) - not yet set up per overview requirements. (askbot-master-uga)
8. **Goal 4 verification:** "Ensure existing content renders identically after migration" has ZERO verification - no migration script, no comparison tests, no visual regression tests. This is the HIGH/HIGH risk with NO mitigations implemented. (askbot-master-uga)
9. **Rollback plan accuracy:** Overview says "markdown2 still available as fallback" but markdown2 is NO LONGER a dependency (removed from askbot_requirements.txt). Rollback requires reinstalling markdown2. (askbot-master-uga)
10. **Coverage tooling:** "95%+ code coverage" success criterion cannot be verified - no pytest-cov or coverage.py configured. (askbot-master-uga)
11. **Phase 2 MathJax architecture mismatch:** Backend uses server-side math preprocessing (math_extract.py), frontend uses client-side MathJax only. Preview will NOT match saved content. Assessment's Phase 2 code example doesn't address this. Options: port math_extract to JS, simplified frontend handling, or backend preview API. (askbot-master-0pk)

---

## 7. Recommended Work Issues

Based on this audit, the following work issues should be created:

### High Priority
1. **Fix code-friendly mode emphasis handling:** Modify `get_md_converter()` in `markup.py` to only disable underscore emphasis (`_`) while preserving asterisk emphasis (`*`). Currently `md.disable('emphasis')` disables both, breaking `*italic*` and `**bold**` when MathJax or code-friendly mode is enabled. (askbot-master-6nm)
2. **Implement feature flag for rollback:** Add `MARKDOWN_BACKEND` environment variable (values: `markdown_it` or `markdown2`) per overview spec. Required for Phase 3 deployment rollback strategy. (askbot-master-uga)
3. **Create content comparison tests:** Goal 4 "ensure existing content renders identically" has NO verification. Need tests comparing markdown2 vs markdown-it output for representative content samples. HIGH/HIGH risk with no mitigations. (askbot-master-uga)
4. **Set up coverage tooling:** Configure pytest-cov to measure and enforce 95%+ coverage for new plugins (video_embed.py, link_patterns.py, truncate_links.py, math_extract.py, dollar_escape.py). Currently unverifiable. (askbot-master-uga)
5. **Add math protection integration tests:** test_markdown_mathjax.py is missing critical tests that verify math is protected from other markdown rules. Required tests: URL inside math not linkified, link patterns inside math ignored, emphasis inside math not processed. See test gaps in markdown-upgrade-mathjax-support.md audit (askbot-master-1c0).

### Medium Priority
1. **Add test for asterisk emphasis in code-friendly mode:** Current tests only verify underscore behavior. Need test that `*italic*` and `**bold**` work when `MARKUP_CODE_FRIENDLY=True`. (askbot-master-6nm)

### Low Priority
1. **Update overview document:** markdown-upgrade-overview.md has outdated "Current State" and Phase 1 status. Should reflect actual completed work before Phase 2 begins. (askbot-master-uga)
2. **Add linkify to overview Phase 1 checklist:** Linkify/truncate_links plugin (commits 5-6) is a major deliverable not mentioned in overview. (askbot-master-uga)
3. **Add math delimiter protection to overview Phase 1:** Backend math protection work is Phase 1 deliverable missing from overview checklist. (askbot-master-uga)
4. **Performance benchmarking:** Run benchmarks comparing markdown-it vs markdown2 to verify 10-20% slowdown claim and establish baseline. (askbot-master-uga)
5. **Implement feature flag:** Add `MARKDOWN_BACKEND` environment variable for rollback capability per overview spec. (askbot-master-uga)

---

## Audit Trail

### Commit Audits
| # | Commit | bd Issue | Status |
|---|--------|----------|--------|
| 1 | 8105e56de | askbot-master-u9s | done |
| 2 | d487c1e7a | askbot-master-6zh | done |
| 3 | 1e01ee226 | askbot-master-jrw | done |
| 4 | 4c3ad65bd | askbot-master-6nm | done |
| 5 | 1a736db26 | askbot-master-n1c | done |
| 6 | ea2f58fa4 | askbot-master-6ts | done |
| 7 | 339de84e0 | askbot-master-8zl | done |
| 8 | 09a928f28 | askbot-master-2bt | done |
| 9 | d625f5507 | askbot-master-tk7 | done |
| 10 | a40000d1c | askbot-master-mps | done |

### Task File Audits
| File | bd Issue | Status |
|------|----------|--------|
| markdown-upgrade-overview.md | askbot-master-uga | done |
| markdown-upgrade-assessment.md | askbot-master-0pk | done |
| markdown-upgrade-phase1-backend.md | askbot-master-d30 | done |
| markdown-upgrade-linkify.md | askbot-master-4gc | done |
| markdown-upgrade-mathjax-support.md | askbot-master-1c0 | done |
| markdown-mathjax-implementation-v2.md | askbot-master-0ae | done |
| background-for-escaped-delimiters-mathjax.md | askbot-master-8lq | done |
| markdown-upgrade-phase2-frontend.md | askbot-master-5i7 | done |
| markdown-upgrade-phase3-testing.md | askbot-master-p48 | done |
| improve-markdown-it-plugin-tests.md | askbot-master-8nq | done |
| MD-summary.md | askbot-master-e9i | done |

### Uncommitted Work Audit
| Description | bd Issue | Status |
|-------------|----------|--------|
| MathJax v2 implementation | askbot-master-35c | done |
