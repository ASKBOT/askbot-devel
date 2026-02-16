#This directory contains Jinja2 templates for Askbot.

##Coding conventions.

* Class names in the Jinja2 templates that are used by javascript or svelte must have js- prefix;
  This marks the classes as important for the correct functionality and cannot be deleted/modified
  without corresponding changes in js/svelte code.
