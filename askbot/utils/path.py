import os
import errno

def mkdir_p(path):
    """same as action of the unix command
    mkdir -p
    """
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise e

def extend_file_name(file_path, extension):
    """append file extension to a string that
    represents file name, if the string does not
    already have that same extension"""
    if not file_path.endswith(extension):
        file_path += extension
    return file_path

def create_file_if_does_not_exist(file_path, print_warning = True):
    """if file at file_path does not exist, create it and return
    the file object, otherwise return None"""
    if not os.path.exists(file_path):
        return open(file_path, 'w+')
    else:
        if print_warning:
            print "File %s exists" % file_path
        return None
