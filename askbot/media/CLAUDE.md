#This directory contains client side media for the project

* css - compiled css, DO NOT EDIT files in this directory, instead work on the sass sources
* sass - style sources in scss format - modify these files to style the site and then rebuild
  see SASS coding style in `/Users/devop/askbot/askbot-master/askbot/media/sass/CLAUDE.md`
* js - javascript assets
* jslib - third party libraries that were manually downloaded
* wmd - source code for the Markdown editor, it is heavily modified WMD
* wmd/sanitize_config.js - AUTO-GENERATED DOMPurify config, do not edit (regenerate with `npm run sync:sanitize`)
* svelte/ - Svelte components (help-panel, downvote-comment) with shared package.json and rollup.config.mjs
  see Svelte-specific coding conventions in `askbot/media/svelte/CLAUDE.md`
* bin/sync_sanitize_config.py - generates wmd/sanitize_config.js from askbot/const/sanitizer_config.py

## Build commands

In order to rebuild sass:

```bash
cd askbot/media
npm run sass:build
```

To sync the sanitize config (Python → JS):

```bash
cd askbot/media
npm run sync:sanitize
```

To rebuild the Svelte components (help panel, downvote comment prompt, etc.):

```bash
cd askbot/media
npm run build:svelte
```

To build a single Svelte component:

```bash
cd askbot/media
npm run help-panel:build
```

## Coding conventions:

Any css classes in the Jinja2 templates that are accessed via javascript or svelte, MUST have js- prefix.
Therefore - if js/svelte code is finding elements by class name, which are injected from Jinja2 templates
those classes must be prefixed by js- in Jinja2 templates and must match the corresponding class defined in Jinja2
template against which this js/svelte code is operating.
