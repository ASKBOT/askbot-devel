# Markdown Upgrade Project - Overview

## Executive Summary

Askbot is migrating from markdown2/Showdown to markdown-it for both Python backend and JavaScript frontend. This upgrade provides:

- ✅ **Active maintenance**: markdown-it-py 4.0.0 (Aug 2025) vs markdown2 (last update 2020)
- ✅ **CommonMark compliance**: 100% spec-compliant parser
- ✅ **Cross-platform consistency**: Same rendering on backend and frontend
- ✅ **Modern features**: Better plugin ecosystem, security updates
- ✅ **Google Assured OSS**: Vetted for production use

## Current State

**Backend**: Partially migrated to markdown-it-py 2.2.0 (needs upgrade to 4.0.0)
**Frontend**: Still using old Showdown library (~2011), creating backend/frontend mismatch
**Custom Features Missing**: Video embedding, auto-link patterns, code-friendly mode

## Project Goals

1. Upgrade Python backend to markdown-it-py 4.0.0 with full feature parity
2. Migrate JavaScript frontend from Showdown to markdown-it.js
3. Implement custom plugins for askbot-specific features
4. Ensure existing content renders identically after migration
5. Maintain zero downtime during deployment

## Migration Strategy: Conservative Phased Approach

### Phase 1: Backend Foundation (Weeks 1-2)
**Status**: 🟡 Planning
**Goal**: Stable, fully-featured Python markdown converter

- Upgrade markdown-it-py to 4.0.0
- Write custom Python plugins (video, link-patterns, code-friendly)
- Add Pygments syntax highlighting
- Create comprehensive unit tests
- **Gate**: 100% backend tests passing, custom plugins working

### Phase 2: Frontend Migration (Weeks 3-4)
**Status**: ⚪ Not started
**Goal**: Replace Showdown with markdown-it.js

- Install markdown-it.js and required plugins
- Rewrite askbot_converter.js for markdown-it
- Update templates to load new libraries
- Test live preview pane matches backend
- **Gate**: Frontend renders identical to backend in all test cases

### Phase 3: Testing & Deployment (Week 5)
**Status**: ⚪ Not started
**Goal**: Safe production migration

- Create migration script to test all existing posts
- Run visual regression tests (old vs new HTML)
- Performance testing
- Update user/admin documentation
- Staged rollout with rollback plan
- **Gate**: <1% rendering differences, zero critical bugs

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Existing content renders differently | HIGH | HIGH | Migration script + visual comparison + gradual rollout |
| Custom plugins break edge cases | MEDIUM | MEDIUM | Extensive unit tests + QA on production data copy |
| Frontend/backend output mismatch | MEDIUM | HIGH | Integration tests comparing both renderers |
| Performance regression | LOW | MEDIUM | Benchmark testing + caching strategy |
| User confusion with new preview | LOW | LOW | Documentation + in-app help text |

## Success Criteria

**Phase 1 Complete When:**
- [ ] markdown-it-py upgraded to 4.0.0
- [ ] Video embedding plugin working (@[youtube](id) syntax)
- [ ] Link patterns plugin working (#bug123 → links)
- [ ] Code-friendly mode disables underscore emphasis
- [ ] Pygments syntax highlighting integrated
- [ ] 95%+ code coverage for new plugins
- [ ] All existing backend tests passing
- [ ] Manual testing shows correct rendering

**Phase 2 Complete When:**
- [ ] markdown-it.js loaded and configured
- [ ] askbot_converter.js rewritten and tested
- [ ] Live preview matches backend exactly
- [ ] All JavaScript tests passing
- [ ] WMD editor integration working
- [ ] MathJax integration preserved

**Phase 3 Complete When:**
- [ ] Migration script validates all existing posts
- [ ] <1% visual differences detected
- [ ] Performance benchmarks meet targets
- [ ] Documentation updated
- [ ] Stakeholder approval for deployment
- [ ] Rollback procedure tested

## Phase Dependencies

```
Phase 1 (Backend)
      ↓
   [GATE: Backend tests pass]
      ↓
Phase 2 (Frontend)
      ↓
   [GATE: Frontend matches backend]
      ↓
Phase 3 (Testing & Deployment)
      ↓
   [GATE: Production approval]
      ↓
   Deployment
```

**Important**: Cannot proceed to next phase without completing gate criteria.

## Resource Requirements

**Development Time**: 5 weeks estimated
- Phase 1: 2 weeks (complex plugin development)
- Phase 2: 2 weeks (frontend rewrite + integration)
- Phase 3: 1 week (testing + documentation)

**Skills Needed**:
- Python markdown-it plugin development
- JavaScript module integration
- Regex pattern matching
- Django testing frameworks
- Visual regression testing

**Infrastructure**:
- Test database with production data copy
- Staging environment for phase 2 testing
- Visual comparison tools (e.g., Percy, BackstopJS)

## Rollback Plan

**Phase 1**: Simple - revert commits, markdown2 still available as fallback
**Phase 2**: Keep Showdown files, feature flag for new converter
**Phase 3**: Database migration is read-only, instant rollback possible

**Feature Flag Strategy**:
```python
# settings.py
MARKDOWN_BACKEND = env('MARKDOWN_BACKEND', default='markdown_it')  # or 'markdown2'
```

## Known Limitations

1. **Video plugin**: No official Python port exists, must write custom implementation
2. **Link patterns**: Complex regex handling, needs careful testing
3. **HTML differences**: markdown-it may wrap code blocks differently than markdown2
4. **Performance**: markdown-it is ~10-20% slower than markdown2 (acceptable tradeoff)

## Alternative Considered: MyST Markdown

**Pros**: Built on markdown-it-py, has video directives, Python+JS support
**Cons**: Different syntax ({iframe}), may confuse users, heavier
**Decision**: Stay with plain markdown-it for familiarity, write custom plugins

## Communication Plan

**Before Phase 1**: Internal team notification
**After Phase 1**: Backend deployed to staging for internal testing
**After Phase 2**: Beta testers invited to test live preview
**Before Phase 3**: User notification about upcoming changes
**After Deployment**: Release notes, help documentation update

## Detailed Phase Plans

See individual phase plan documents:
- [Phase 1: Backend Implementation](markdown-upgrade-phase1-backend.md)
- [Phase 2: Frontend Migration](markdown-upgrade-phase2-frontend.md)
- [Phase 3: Testing & Deployment](markdown-upgrade-phase3-testing.md)

## References

- [Initial Assessment](markdown-upgrade-assessment.md)
- [markdown-it-py Documentation](https://github.com/executablebooks/markdown-it-py)
- [markdown-it.js Documentation](https://github.com/markdown-it/markdown-it)
- [CommonMark Spec](https://spec.commonmark.org/)
- [mdit-py-plugins](https://github.com/executablebooks/mdit-py-plugins)

## Project Timeline

```
Week 1-2: Phase 1 (Backend)
  ├─ Day 1-2: Dependency upgrades + setup
  ├─ Day 3-5: Video embedding plugin
  ├─ Day 6-7: Link patterns plugin
  ├─ Day 8-9: Code-friendly mode + Pygments
  └─ Day 10: Testing + gate review

Week 3-4: Phase 2 (Frontend)
  ├─ Day 11-12: Install JS libraries
  ├─ Day 13-15: Rewrite askbot_converter.js
  ├─ Day 16-17: Template updates
  ├─ Day 18-19: Integration testing
  └─ Day 20: Gate review

Week 5: Phase 3 (Testing)
  ├─ Day 21-22: Migration script + regression tests
  ├─ Day 23: Performance testing
  ├─ Day 24: Documentation
  └─ Day 25: Final approval + deployment
```

## Monitoring & Validation

**Post-Deployment Monitoring**:
- Error rates for markdown conversion
- Performance metrics (avg. render time)
- User feedback on preview accuracy
- Bug reports related to markdown rendering

**Success Metrics**:
- Zero critical bugs in first week
- <5% increase in conversion time
- <10 user complaints about rendering changes
- Zero data loss incidents

## Sign-off

**Technical Lead**: _________________  Date: ________
**QA Lead**: _________________  Date: ________
**Product Owner**: _________________  Date: ________
