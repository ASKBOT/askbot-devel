"""This is temporary code to parse category
tree, stored in the settings.
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
from askbot.conf import settings as askbot_settings
try:
    from django.utils import simplejson
except ImportError:
    import json as simplejson

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
    tree = sorted(tree, lambda x,y: cmp(x[0], y[0]))
    for item in tree:
        item[1] = sort_tree(item[1])
    return tree

def get_data():
    """returns category tree data structure encoded as json
    or None, if category_tree is disabled
    """
    if askbot_settings.TAG_SOURCE == 'category-tree':
        return simplejson.loads(askbot_settings.CATEGORY_TREE)
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
    subtree = get_subtree(tree, path)
    children = subtree[1]
    children.append([category_name, []])
    children = sorted(children, lambda x,y: cmp(x[0], y[0]))
    subtree[1] = children
    new_path = path[:]
    #todo: reformulate all paths in terms of names?
    new_item_index = get_leaf_index(subtree, category_name)
    assert new_item_index != None
    new_path.append(new_item_index)
    return new_path

def _has_category(tree, category_name):
    for item in tree:
        if item[0] == category_name:
            return True
        if _has_category(item[1], category_name):
            return True
    return False

def has_category(tree, category_name):
    """true if category is in tree"""
    #skip the dummy
    return _has_category(tree[0][1], category_name)

def rename_category(
    tree, from_name = None, to_name = None, path = None
):
    if to_name == from_name:
        return
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
    tree_json = simplejson.dumps(tree)
    askbot_settings.update('CATEGORY_TREE', tree_json)
