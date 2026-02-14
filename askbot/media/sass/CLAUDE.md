#This directory contains SASS styles for Askbot

##Coding conventions

* scss format must be used
* do not use hardcoded color values; always use CSS variables from `colors.scss`
* css variables other than colors must be defined in `variables.scss`
* css parameters in the styles must use variables defined in `variables.scss`
* css variables must be reused whenever possible
* new css variables may be invented only after careful consideration and approval by the developer
* color css variables in `colors.scss`
* size units must be in `rem`
* `em` units may be used for font sizes if the parent container has size set in `rem`
* `px` may be used for base font size and 1px borders
* classes used as JS/Svelte selectors must use `js-` prefix; avoid renaming `js-` prefixed classes and ids as they are coupled across SASS, Jinja2 templates, and JS/Svelte code
* component styles go in `components/` — one file per component or feature
