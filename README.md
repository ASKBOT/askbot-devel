## Askbot - a Django Q&A forum platform

This is Askbot project - open source Q&A system, like StackOverflow, Yahoo Answers and some others.
Askbot is based on code of CNPROG, originally created by Mike Chen
and Sailing Cai and some code written for OSQA.

Demos and hosting are available at http://askbot.com.

Branch `master` - released as versions 0.12.x - supports Django 4.2, Python up to 3.11

Branch `0.11.x` - released as versions 0.11.x - supports Django 3.2/Python 3.7 - 3.10

Branch `0.10.x` - supports Django 1.8 - the last version series to support Python 2.7

Branch `0.9.x` supports Django 1.7

Branch `0.8.x` - transitional version for the upgrade of the database to Django 1.7

Branch `0.7.x` - is the latest version supporting Django 1.5


## Installation

Install as follows:

```
pip install --upgrade pip
pip install setuptools-rust
python -m pip install .
askbot-setup # answer the questions or use parameters to askbot-setup
cd <root_dir> # substitute <root_dir> with the actual directory, default is `askbot_site`
python manage.py migrate # assumes that the database specified by askbot-setup is available
```

The last command above will create a working Django project in the project root
directory that you specify with the `askbot-setup` script.

For the deployment, follow the general Django deployment documentation.

## How to contribute

Your pull requests are very welcome, **but please read the few paragraphs below**, it might save our combined efforts.

**Obvious bug fixes will be merged quickly**, however less obvious cases should include a clear description of how to reproduce the bug. Complex cases must be accompanied with the new unit tests.

**Before suggesting PR's for new features - please first discuss those features in the "Issues section"**. We really appreciate your efforts, but PR's may not be accepted and it might be disappointing - so please communicate. The bandwidth for the testing is valuable and limited and we would like to avoid "easter eggs" and the feature overload.

**Please always use feature branches for the PR's**, multiple feature/bugfix PR's are harder to understand and less likely to be accepted.

**Translators: please translate at the Transifex, not via github!!!** https://www.transifex.com/projects/p/askbot/.

All documentation is in the directory askbot/doc

Follow https://help.github.com/articles/fork-a-repo to to learn how to use
`fetch` and `push` as well as other help on using git.

pre-commit
==========

This repository uses [pre-commit](https://pre-commit.com/) to check
some code rules, so please install it:

```
$ pre-commit install
```

It will then check the rules upon `git commit`.


License, copyright and trademarks
=================================
Askbot software is licensed under GPL, version 3.

Copyright Askbot S.p.A and the project contributors, 2010-2023.

"Askbot" is a trademark and service mark registered in the United States, number 4323777.
