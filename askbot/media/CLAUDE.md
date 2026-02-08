This directory contains client side media for the project:

* css - compiled css, DO NOT EDIT files in this directory, instead work on the sass sources
* sass - style sources in scss format - modify these files to style the site and then rebuild
* js - javascript assets
* jslib - third party libraries that were manually downloaded
* wmd - source code for the Markdown editor, it is heavily modified WMD
* wmd/sanitize_config.js - AUTO-GENERATED DOMPurify config, do not edit (regenerate with `npm run sync:sanitize`)
* wmd/help-panel/src - help panel for the wmd editor implemented in Svelte - it has a dedicated package.json
* bin/sync_sanitize_config.py - generates wmd/sanitize_config.js from askbot/const/sanitizer_config.py

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

To rebuild the svelte help panel:

```bash
cd askbot/media
npm run help-panel:build
```
