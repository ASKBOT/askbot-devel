# -*- coding: utf-8 -*-
# Miville
# Copyright (C) 2008 Société des arts technologiques (SAT)
# http://www.sat.qc.ca
# All rights reserved.
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Miville is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Miville.  If not, see <http://www.gnu.org/licenses/>.

"""
This script parse a directory tree looking for python modules and packages and
create ReST files appropriately to create code documentation with Sphinx.
It also create a modules index.
"""

import os
import optparse


# automodule options
OPTIONS = ['members',
            'undoc-members',
#            'inherited-members', # disable because there's a bug in sphinx
            'show-inheritance']


def create_file_name(base, opts):
    """Create file name from base name, path and suffix"""
    return os.path.join(opts.destdir, "%s.%s" % (base, opts.suffix))

def write_automodule_directive(module):
    """Create the automodule directive and add the options"""
    directive = '.. automodule:: %s\n' % module
    for option in OPTIONS:
        directive += '    :%s:\n' % option
    directive += '\n'
    return directive

def write_heading(module, kind='Module'):
    """Create the page heading."""
    heading = '.. _%s:\n' % module
    heading += '\n'
    heading += title_line(module, '=')
    return heading

def write_sub(module, kind='Module'):
    """Create the module subtitle"""
    sub = title_line('The :mod:`%s` %s' % (module, kind), '-')
    return sub

def title_line(title, char):
    """ Underline the title with the character pass, with the right length."""
    return ':mod:`%s`\n%s\n\n' % (title, len(title) * char)

def create_module_content(module):
    """Build the text of the module file."""
    text = write_heading(module)
    #text += write_sub(module)
    text += write_automodule_directive(module)
    return text

def is_python_package(path):
    """returns True if directory is Python package
    - that is - contains the __index__.py file
    returns False otherwise
    """
    return os.path.isfile(os.path.join(path, '__init__.py'))

def create_package_content(package, py_files, sub_packages):
    """Build the text of the file"""

    text = write_heading(package, 'Package')
    text += write_automodule_directive(package)

    #if has py_files or sub_packages
    #   output Package summary:
    #   has #modules, #sub-packages, #members

    #create links to sub-module files
    if py_files:
        text += '.. _modules::\n'
        text += '\n'
        text += title_line('Modules', '-')
        text += '\n'
        for py_file in py_files:
            if py_file == '__init__.py':
                #continue, because this file is being created for
                #__init__.py of the current module
                continue
            py_file = os.path.splitext(py_file)[0]
            text += '* :ref:`%s.%s`\n' % (package, py_file)
        text += '\n'

    #create links to sub-packages
    if sub_packages:
        text += '.. _packages::\n'
        text += '\n'
        text += title_line('Subpackages', '-')
        text += '\n'
        for sub in sub_packages:
            #todo - add description here
            text += '* :ref:`%s.%s`\n' % (package, sub)
    return text
    #build toctree for the package page
    #text += '.. toctree::\n\n'
    #for sub in subs:
    #    text += '    %s.%s\n' % (package, sub)

def write_file(module_name, text_content, opts):
    """Saves file for the module uses text_content for content
    and information within options to determine where to save

    respects options "dry run" and "force"
    """
    file_path = create_file_name(module_name, opts)
    if not opts.force and os.path.isfile(file_path):
        print 'File %s already exists.' % file_path
    else:
        print 'Writing file %s' % file_path
        # write the file
        if not opts.dryrun:
            fd = open(file_path, 'w')
            fd.write(text_content)
            fd.close()


def check_for_code(module):
    """
    Check if there's at least one class or one function in the module.
    """
    fd = open(module, 'r')
    for line in fd:
        if line.startswith('def ') or line.startswith('class '):
            fd.close()
            return True
    fd.close()
    return False

def select_public_names(name_list):
    """goes through the list and discards names
    that match pattern for hidden and private directory and file names
    returns the list of those items that pass the "publicity" test
    """
    public_names = []
    for name in name_list:
        if name.startswith('.') or name.startswith('_'):
            continue
        else:
            public_names.append(name)
    return public_names

def select_python_packages(package_path, sub_directory_names):
    """returns list of subdimodule_name directories (only basenames) of package_path
    which are themselves python packages
    """
    python_packages = []
    for sub_name in sub_directory_names:
        sub_path = os.path.join(package_path, sub_name)
        if is_python_package(sub_path):
            python_packages.append(sub_name)
    return python_packages

def recurse_tree(path, excludes, opts):
    """
    Look for every file in the directory tree and create the corresponding
    ReST files.
    """
    print path
    base_package_name = None
    # check if the base directory is a package and get is name
    if '__init__.py' in os.listdir(path):
        base_package_name = os.path.basename(path)

    toc = []
    excludes = format_excludes(path, excludes)
    tree = os.walk(path, False)
    for directory, subs, files in tree:

        py_files = select_py_files(files)
        if len(py_files) < 1:
            continue

        if is_directory_excluded(directory, excludes):
            continue

        # TODO: could add check for windows hidden files
        subs = select_public_names(subs)
        subs = select_python_packages(directory, subs)

        #calculate dotted python package name - like proj.pack.subpackage
        package_name = directory.replace(os.path.sep, '.')

        if is_python_package(directory):
            text = create_package_content(package_name, py_files, subs)
            write_file(package_name, text, opts)
            toc.append(os.path.basename(directory))

        for py_file in py_files:
            if py_file == '__init__.py':
                continue
            module_name = os.path.splitext(py_file)[0]
            module_package_name = package_name + '.' + module_name
            text = create_module_content(module_package_name)
            write_file(module_package_name, text, opts)
            toc.append(module_package_name)

    # create the module's index
    if not opts.notoc:
        modules_toc(toc, opts)

def modules_toc(modules, opts, name='modules'):
    """
    Create the module's index.
    """
    fname = create_file_name(name, opts)
    if not opts.force and os.path.exists(fname):
        print "File %s already exists." % name
        return

    print "Creating module's index modules.txt."
    text = write_heading(opts.header, 'Modules')
    text += title_line('Modules:', '-')
    text += '.. toctree::\n'
    text += '   :maxdepth: %s\n\n' % opts.maxdepth

    modules.sort()
    prev_module = ''
    for module in modules:
        # look if the module is a subpackage and, if yes, ignore it
        if module.startswith(prev_module + '.'):
            continue
        prev_module = module
        text += '   %s\n' % module

    # write the file
    if not opts.dryrun:
        fd = open(fname, 'w')
        fd.write(text)
        fd.close()

def format_excludes(path, excludes):
    """
    Format the excluded directory list.
    (verify that the path is not from the root of the volume or the root of the
    package)
    """
    f_excludes = []
    for exclude in excludes:
        #not sure about the "not startswith" part
        if not os.path.isabs(exclude) and not exclude.startswith(path):
            exclude = os.path.join(path, exclude)
        # remove trailing slash
        f_excludes.append(exclude.rstrip(os.path.sep))
    return f_excludes

def is_directory_excluded(directory, excludes):
    """Returns true if directory is in the exclude list
    otherwise returns false
    """
    for exclude in excludes:
        if directory.startswith(exclude):
            return True
    return False

def select_py_files(files):
    """
    Return a list with only the python scripts (remove all other files).
    """
    py_files = [fich for fich in files if os.path.splitext(fich)[1] == '.py']
    return py_files


def main():
    """
    Parse and check the command line arguments
    """
    parser = optparse.OptionParser(usage="""usage: %prog [options] <package path> [exclude paths, ...]

Note: By default this script will not overwrite already created files.""")
    parser.add_option("-n", "--doc-header", action="store", dest="header", help="Documentation Header (default=Project)", default="Project")
    parser.add_option("-d", "--dest-dir", action="store", dest="destdir", help="Output destination directory", default="")
    parser.add_option("-s", "--suffix", action="store", dest="suffix", help="module suffix (default=txt)", default="txt")
    parser.add_option("-m", "--maxdepth", action="store", dest="maxdepth", help="Maximum depth of submodules to show in the TOC (default=4)", type="int", default=4)
    parser.add_option("-r", "--dry-run", action="store_true", dest="dryrun", help="Run the script without creating the files")
    parser.add_option("-f", "--force", action="store_true", dest="force", help="Overwrite all the files")
    parser.add_option("-t", "--no-toc", action="store_true", dest="notoc", help="Don't create the table of content file")
    (opts, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("package path is required.")
    else:
        if os.path.isdir(args[0]):
            # check if the output destination is a valid directory
            if opts.destdir and os.path.isdir(opts.destdir):
                # if there's some exclude arguments, build the list of excludes
                excludes = args[1:]
                recurse_tree(args[0], excludes, opts)
            else:
                print '%s is not a valid output destination directory.' % opts.destdir
        else:
            print '%s is not a valid directory.' % args




if __name__ == '__main__':
    main()
