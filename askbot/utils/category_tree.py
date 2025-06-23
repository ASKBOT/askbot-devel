"""
Parsess the category tree, stored in the settings.
The tree is plain text, with levels of branching
reflected by indentation (2 spaces per level).
example of desired structure, when input is parsed

    cat_tree = [
        ['dummy',
            [
                ['tires', [
                        ['michelin', [
                                ['trucks', []],
                                ['cars', []],
                                ['motorcycles', []]
                            ]
                        ],
                        ['good year', []],
                        ['honda', []],
                    ]
                ],
                ['abandonment', []],
                ['chile', []],
                ['vulcanization', []],
            ]
        ]
    ]
"""
import json
from askbot.conf import settings as askbot_settings
from django.utils.translation import gettext as _

def get_leaf_index(tree, leaf_name):
    children = tree[1]
    for index, child in enumerate(children):
        if child[0] == leaf_name:
            return index
    return None

def _get_subtree(tree, path):
    clevel = tree
    for pace in path:
        clevel = clevel[1][pace]
    return clevel

def get_subtree(tree, path):
    """path always starts with 0,
    and is a list of integers"""
    assert(path[0] == 0)
    if len(path) == 1:#special case
        return tree[0]
    else:
        return _get_subtree(tree[0], path[1:])

def sort_tree(tree):
    """sorts contents of the nodes alphabetically"""
    tree = sorted(tree, key=lambda x: x[0])
    for item in tree:
        item[1] = sort_tree(item[1])
    return tree

def get_data():
    """returns category tree data structure encoded as json
    or None, if category_tree is disabled
    """
    if askbot_settings.TAG_SOURCE == 'category-tree':
        return json.loads(askbot_settings.CATEGORY_TREE)
    else:
        return None

def _get_leaf_names(subtree):
    leaf_names = set()
    for leaf in subtree:
        leaf_names.add(leaf[0])
        leaf_names |= _get_leaf_names(leaf[1])
    return leaf_names

def get_leaf_names(tree = None):
    """returns set of leaf names"""
    data = tree or get_data()
    if data is None:
        return set()
    return _get_leaf_names(data[0][1])

def path_is_valid(tree, path):
    try:
        get_subtree(tree, path)
        return True
    except IndexError:
        return False
    except AssertionError:
        return False

def add_category(tree, category_name, path):
    # check if the new name is already in the tree
    crumbs = get_category_breadcrumbs(tree, category_name)
    if crumbs:
        position = '->'.join(crumbs)
        raise ValueError(_('Category "%s" already exists') % position)
    subtree = get_subtree(tree, path)
    children = subtree[1]
    children.append([category_name, []])
    children = sorted(children, key=lambda x: x[0])
    subtree[1] = children
    new_path = path[:]
    #todo: reformulate all paths in terms of names?
    new_item_index = get_leaf_index(subtree, category_name)
    assert new_item_index != None
    new_path.append(new_item_index)
    return new_path

def get_breadcrumbs(tree, category_name):
    for item in tree:
        if item[0] == category_name:
            return [item[0]]
        relative_crumbs = get_breadcrumbs(item[1], category_name)
        if relative_crumbs:
            return [item[0]] + relative_crumbs
    return []

def get_category_breadcrumbs(tree, category_name):
    """returns list of category names from the root to the category.
    If the category does not exist, returns an empty list.
    """
    return get_breadcrumbs(tree[0][1], category_name)

def has_category(tree, category_name):
    """true if category is in tree"""
    #skip the dummy
    return len(get_category_breadcrumbs(tree, category_name)) > 0

def rename_category(
    tree, from_name = None, to_name = None, path = None
):
    # don't do anything if the names are the same
    if to_name == from_name:
        return

    # check if the new name is already in the tree
    crumbs = get_category_breadcrumbs(tree, to_name)
    if crumbs:
        position = '->'.join(crumbs)
        raise ValueError(_('Category "%s" already exists') % position)

    subtree = get_subtree(tree, path[:-1])
    from_index = get_leaf_index(subtree, from_name)
    #todo possibly merge if to_name exists on the same level
    #to_index = get_leaf_index(subtree, to_name)
    child = subtree[1][from_index]
    child[0] = to_name
    return sort_tree(tree)

def _delete_category(tree, name):
    for item in tree:
        if item[0] == name:
            tree.remove(item)
            return True
        if _delete_category(item[1], name):
            return True
    return False

def delete_category(tree, name, path):
    subtree = get_subtree(tree, path[:-1])
    del_index = get_leaf_index(subtree, name)
    subtree[1].pop(del_index)
    return sort_tree(tree)

def save_data(tree):
    assert(askbot_settings.TAG_SOURCE == 'category-tree')
    tree_json = json.dumps(tree)
    askbot_settings.update('CATEGORY_TREE', tree_json)
