Upgrade of Markdown support.
Below are the markdown features covered by the backend tests.

* tables
* footnotes
* task lists
* fenced code blocks with syntax highlighting (see how highlighting is working)
* impolemented custom plugin video_embed, for embedding of videos as below
* video embedding @[youtube](<videoid>) - this might interfere with @mentions
  supports: youtube, vimeo, dailymotion
* implemented custom markdown plugin "link_patterns" - to support the Askbot link patterns feature
* link patters (Askbot feature) - might interfere with @mentions;
  link patterns feature is tricky to configure, becuase one must format the settings exactly
* code-friendly (allows underscores in words (test leading and trailing underscores)
* mathjax can be used with $ sign delimiters, no markdown processing is done within mathjax block

Questions I have left:
* 
In the markdown converter, there is a TODO to implement something to
allow ignoring mathjax - do we still need to do that; I saw that the
tests are covering mathjax; is the ordering of mathjax processing correct
with respect to the remaining plugins?

* is code highlighting on the backend with pygments the best option?
  how would this be matched by the fronend implementation?

* are code blocks protected from the markdown processing? I don't want md to mangle my code.
