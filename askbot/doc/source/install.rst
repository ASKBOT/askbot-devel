.. _install:

=================
Installing Askbot
=================

The latest stable version of askbot can be installed from the official `Python Package Index (PyPI) <http://pypi.python.org/pypi/askbot/>`_

There are several methods to install Askbot. The recommended choice of the method depends on whether you are planning to modify the source code and/or templates or not.

Askbot 0.14.x requires Python 3.11.5+. Install it with the following commands:

    pip install --upgrade pip
    pip install setuptools-rust
    python setup.py install
    askbot-setup # answer the questions or use parameters to askbot-setup
    cd <root_dir> # substitute <root_dir> with the actual directory, default is `askbot_site`
    python manage.py migrate # assumes that the database specified by askbot-setup is available

The last command above will create a working Django project in the project root
directory that you specify with the `askbot-setup` script.

Would like to use the package as is?
====================================

If so - then the best tool for that is `pip`, the second best choice is `easy_install`::

 pip install askbot
 easy_install askbot #if you prefer easy_install

Both commands automatically install Askbot and the dependency packages. `Pip` is a significant improvement upon `easy_install` and is strongly recommended.

If you do not have either of those tools - download the `askbot archive from PyPI <http://pypi.python.org/pypi/askbot/>`_, unzip and untar it, then run::

 python setup.py install #this is actually equivalent to running easy_install

Intend to customize the forum?
==============================

In this case the best option is to clone the code from the development repository::

 git clone git://github.com/ASKBOT/askbot-devel.git <project_name>

where `<project_name>` should be some very distinct name.

Then jump into the new directory and run::

 python setup.py develop #the develop option will not install askbot into the python site packages directory

.. note::

    `setup.py` installs the Python modules required by Askbot into the proper directory (e.g.
    `/usr/bin/python3.6/site-packages`).

How to install into custom directories
======================================

On the shared hosts and in some other cases it is better to install python packages in some place other than the system package directory. If that's your situation - use the `virtualenv` tool::

 virtualenv /path/to/some/directory

Virtualenv will provide a dedicated `python` interpreter and `pip` just for that isolated environment. Both will be available within directory `/path/to/some/dir/bin`. Please, use them to run operations shown above.

Under windows, please install 
`mysql-python windows binary package <http://www.codegood.com/archives/4>`_ manually.

Most likely, by this time you will have askbot software installed. However, in some cases
one of the dependency packages might fail to install. :ref:`This document <dependencies>` will help you find those components.

When you have all packages installed, 
please proceed to the :ref:`initial configuration <compile-time-configuration>` section. 

.. _Python: http://www.python.org/download/
.. _askbot: http://pypi.python.org/pypi/askbot
.. _`easy_install`: http://pypi.python.org/pypi/setuptools
.. _pypi: http://pypi.python.org/

.. _django.wsgi: http://github.com/ASKBOT/askbot-devel/blob/master/askbot/setup_templates/django.wsgi
