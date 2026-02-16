#This directory contains svelte code for Askbot

##Coding conventions

* all presentational styling into svelte components - all styling MUST be in `askbot/media/sass/components`
* as a corollary of above ^ DO NOT USE <style/> blocks in the .svelte files
* if Svelte components look for DOM elements by class name provided by Jinja2 templates, they must use js- prefixed
classes
