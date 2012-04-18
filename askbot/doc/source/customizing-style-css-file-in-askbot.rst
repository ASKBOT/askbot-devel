.. _customizing-style-css-file-in-askbot:

====================================
Customizing style.css file in Askbot
====================================

File `style.css` is produced by the `lesscss compiler <http://lesscss.org>`_ - ``lessc``.
Secondly, `style.css` is used in production mode - with an entry
`ASKBOT_CSS_DEVEL = True` in the `settings.py` file.
When `ASKBOT_CSS_DEVEL` setting is absent or set to ``False``,
the source `style.less` will be loaded and compiled by the browser.
A side-effect of that is a possible momentary flash of unstyled content
and some delay in the page load.

`ASKBOT_CSS_DEVEL = True` is a convenient setting for the designer.

Please find documentation about the lesscss format elsewhere.

Compiling lesscss files
=======================

The following command will compile the lesscss source file,
an option -x will produce compressed css file:

    lessc file.lesscss -x > file.css

Installing lesscss
==================

Make sure you have recent version of `node.js <http://nodejs.org>`_ - latest version preferred.
More recent versions of node come with the tool called `npm <http://npmjs.org>`_,
for earlier versions ``npm`` will need to be installed manually.

To install lesscss, type:

    sudo npm install less
