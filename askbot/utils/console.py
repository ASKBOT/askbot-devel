"""functions that directly handle user input
"""
import sys
import time
import logging
from askbot.utils import path

def start_printing_db_queries():
    """starts logging database queries into console,
    should be used for debugging only"""
    logger = logging.getLogger('django.db.backends')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

def choice_dialog(prompt_phrase, choices = None, invalid_phrase = None):
    """prints a prompt, accepts keyboard input
    and makes sure that user response is one of given
    in the choices argument, which is required
    and must be a list

    invalid_phrase must be a string with %(opt_string)s
    placeholder
    """
    assert(hasattr(choices, '__iter__'))
    assert(not isinstance(choices, basestring))
    while 1:
        response = raw_input(
            '\n%s\ntype %s: ' % (prompt_phrase, '/'.join(choices))
        )
        if response in choices:
            return response
        elif invalid_phrase != None:
            opt_string = ','.join(choices)
            print invalid_phrase % {'opt_string': opt_string}
        time.sleep(1)

def numeric_choice_dialog(prompt_phrase, choices):
    """Prints a list of choices with numeric options and requires the
    user to select a single choice from the list.

    :param prompt_phrase: (str) Prompt to give the user asking them to
    choose from the list.

    :param choices: (list) List of string choices for the user to choose
    from. The numeric value they will use to select from the list is the
    list index of the choice.

    :returns: (int) index number of the choice selected by the user
    """
    assert(hasattr(choices, '__iter__'))
    assert(not isinstance(choices, basestring))
    choice_menu = "\n".join(["%d - %s" % (i,x) for i, x in enumerate(choices)])
    while True:
        response = raw_input('\n%s\n%s> ' % (choice_menu, prompt_phrase))
        try:
            index = int(response)
        except ValueError:
            index = False
        if index is False or index < 0 or index >= len(choices):
            print "\n*** Please enter a number between 0 and %d ***" % (len(choices)-1)
        else:
            return index

def numeric_multiple_choice_dialog(prompt_phrase, choices, all_option=False):
    """Prints a list of choices with numeric options and requires the
    user to select zero or more choices from the list.

    :param prompt_phrase: (str) Prompt to give the user asking them to
    choose from the list.

    :param choices: (list) List of string choices for the user to choose
    from. The numeric value they will use to select from the list is the
    list index of the choice.

    :param all_option: (bool) Optional. If True, the first choice will be a
    fake option to choose all options. This is a convenience to avoid requiring
    the user provide a lot of input when there are a lot of options

    :returns: (list) list of index numbers of the choices selected by
    the user
    """
    assert(hasattr(choices, '__iter__'))
    assert(not isinstance(choices, basestring))
    if all_option:
        choices.insert(0, 'ALL')
    choice_menu = "\n".join(["%d - %s" % (i,x) for i, x in enumerate(choices)])
    choice_indexes = []
    index = False
    while True:
        response = raw_input('\n%s\n%s> ' % (choice_menu, prompt_phrase))
        selections = response.split()
        print "selections: %s" % selections
        for c in selections:
            try:
                index = int(c)
            except ValueError:
                index = False
            if index < 0 or index >= len(choices):
                index = False
                print "\n*** Please enter only numbers between 0 and " +\
                      "%d separated by spaces ***" % (len(choices)-1)
                break
            else:
                choice_indexes.append(index)
        if index:
            if all_option and 0 in choice_indexes and len(choice_indexes) > 1:
                print "\n*** You cannot include other choices with the ALL " +\
                      "option ***"
            else:
                return choice_indexes

def simple_dialog(prompt_phrase, required=False):
    """asks user to enter a string, if `required` is True,
    will repeat question until non-empty input is given
    """
    while 1:

        if required:
            prompt_phrase += ' (required)'

        response = raw_input(prompt_phrase + '\n> ').strip()

        if response or required is False:
            return response

        time.sleep(1)


def get_yes_or_no(prompt_phrase, default=None):
    """Prompts user for a yes or no response with an optional default
    value which will be inferred if the user just hits enter

    :param prompt_phrase: (str) Question to prompt the user with

    :param default: (str) Either 'yes' or 'no'. If a valid option is
    provided, the user can simply press enter to accept the default.
    If an invalid option is passed in, a `ValueError` is raised.

    :returns: (str) 'yes' or 'no'
    """
    while True:
        prompt_phrase += ' (yes/no)'
        if default:
            prompt_phrase += '\n[%s] >' % default
        else:
            prompt_phrase += '\n >'
        response = raw_input(prompt_phrase).strip()
        if not response and default:
            return default
        if response in ('yes', 'no'):
            return response


def open_new_file(prompt_phrase, extension = '', hint = None):
    """will ask for a file name to be typed
    by user into the console path to the file can be
    either relative or absolute. Extension will be appended
    to the given file name.
    Return value is the file object.
    """
    if extension != '':
        if extension[0] != '.':
            extension = '.' + extension
    else:
        extension = ''

    file_object = None
    if hint:
        file_path = path.extend_file_name(hint, extension)
        file_object = path.create_file_if_does_not_exist(file_path, print_warning = True)

    while file_object == None:
        file_path = raw_input(prompt_phrase)
        file_path = path.extend_file_name(file_path, extension)
        file_object = path.create_file_if_does_not_exist(file_path, print_warning = True)

    return file_object

def print_action(action_text, nowipe = False):
    """print the string to the standard output
    then wipe it out to clear space
    """
    #for some reason sys.stdout.write does not work here
    #when action text is unicode
    print action_text,
    sys.stdout.flush()
    if nowipe == False:
        #return to the beginning of the word
        sys.stdout.write('\b' * len(action_text))
        #white out the printed text
        sys.stdout.write(' ' * len(action_text))
        #return again
        sys.stdout.write('\b' * len(action_text))
    else:
        sys.stdout.write('\n')

def print_progress(elapsed, total, nowipe = False):
    """print dynamic output of progress of some
    operation, in percent, to the console and clear the output with
    a backspace character to have the number increment
    in-place"""
    output = '%6.2f%%' % (100 * float(elapsed)/float(total))
    print_action(output, nowipe)

class ProgressBar(object):
    """A wrapper for an iterator, that prints
    a progress bar along the way of iteration
    """
    def __init__(self, iterable, length, message = ''):
        self.iterable = iterable
        self.length = length
        self.counter = float(0)
        self.max_barlen = 60
        self.curr_barlen = 0
        self.progress = ''
        if message and length > 0:
            print message


    def __iter__(self):
        return self

    def print_progress_bar(self):
        """prints the progress bar"""

        self.backspace_progress_percent()

        tics_to_write = 0
        if self.length < self.max_barlen:
            tics_to_write = self.max_barlen/self.length
        elif int(self.counter) % (self.length/self.max_barlen) == 0:
            tics_to_write = 1

        if self.curr_barlen + tics_to_write <= self.max_barlen:
            sys.stdout.write('-' * tics_to_write)
            self.curr_barlen += tics_to_write

        self.print_progress_percent()

    def backspace_progress_percent(self):
        sys.stdout.write('\b'*len(self.progress))

    def print_progress_percent(self):
        """prints percent of achieved progress"""
        self.progress = ' %.2f%%' % (100 * (self.counter/self.length))
        sys.stdout.write(self.progress)
        sys.stdout.flush()

    def finish_progress_bar(self):
        """brint the last bars, to make all bars equal length"""
        self.backspace_progress_percent()
        sys.stdout.write('-' * (self.max_barlen - self.curr_barlen))

    def next(self):

        try:
            result = self.iterable.next()
        except StopIteration:
            if self.length > 0:
                self.finish_progress_bar()
                self.print_progress_percent()
                sys.stdout.write('\n')
            raise

        self.print_progress_bar()
        self.counter += 1
        return result
