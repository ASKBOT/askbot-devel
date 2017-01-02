import unittest
from askbot.utils import category_tree as ct
import simplejson

class CategoryTreeTests(unittest.TestCase):
    def setUp(self):
        self.tree = [
            [
                u'dummy', [#dummy is a sentinel node
                    [
                        u'cars', [
                            [u'volkswagen', []],
                            [u'zhiguli', []]
                        ]
                    ],
                    [
                        u'cats', [
                            [u'meow', []],
                            [u'tigers', [
                                        [u'rrrr', []]
                                    ]
                            ]
                        ]
                    ],
                    [
                        u'music', [
                            [u'play', [
                                [u'loud', []]]
                            ],
                            [u'listen', []],
                            [u'buy', []],
                            [u'download', []]
                        ]
                    ]
                ]
            ]
        ]

    def test_dummy_is_absent(self):
        self.assertEqual(
            ct.has_category(self.tree, 'dummy'),
            False
        )

    def test_first_level_subcat_is_there(self):
        self.assertEqual(
            ct.has_category(self.tree, 'cars'),
            True
        )

    def test_deep_level_subcat_is_there(self):
        self.assertEqual(
            ct.has_category(self.tree, 'download'),
            True
        )

    def test_get_subtree_dummy(self):
        dummy = ct.get_subtree(self.tree, [0])
        self.assertEqual(dummy[0], 'dummy')

    def test_get_subtree_cars(self):
        cars = ct.get_subtree(self.tree, [0,0])
        self.assertEqual(cars[0], 'cars')

    def test_get_subtree_listen_music(self):
        listen_music = ct.get_subtree(self.tree, [0,2,1])
        self.assertEqual(listen_music[0], 'listen')

    def test_path_is_valid_dummy(self):
        self.assertEqual(
            ct.path_is_valid(self.tree, [0]), True
        )

    def test_path_is_valid_deep(self):
        self.assertEqual(
            ct.path_is_valid(self.tree, [0,2,0,0]), True
        )
    def test_path_is_nvalid_too_deep(self):
        self.assertEqual(
            ct.path_is_valid(self.tree, [0,2,0,0,0]), False
        )

    def test_add_category(self):
        ct.add_category(self.tree, 'appreciate', [0, 2])
        appreciate = ct.get_subtree(self.tree, [0, 2, 0])
        self.assertEqual(appreciate[0] , 'appreciate')

    def test_sort_data(self):
        unsorted_data = [
            [
                'dummy',
                [
                    [
                        'cars',
                        []
                    ],
                    [
                        'audio',
                        [
                            [
                                'mp3', []
                            ],
                            [
                                'amadeus', []
                            ]
                        ]
                    ]
                ]
            ]
        ]
        sorted_data = ct.sort_tree(unsorted_data)
        sorted_dump = simplejson.dumps(sorted_data)
        self.assertEqual(
            sorted_dump,
            '[["dummy", [["audio", [["amadeus", []], ["mp3", []]]], ["cars", []]]]]'
        )

    def test_get_leaf_names(self):
        leaf_names = ct.get_leaf_names(self.tree)
        self.assertEqual(
            leaf_names,
            set([
                'cars', 'volkswagen', 'zhiguli',
                'cats', 'meow', 'tigers', 'rrrr',
                'music', 'play', 'listen', 'loud',
                'buy', 'download'
            ])
        )

    def test_get_leaf_names_empty(self):
        self.assertEqual(
            set([]),
            ct.get_leaf_names(None)
        )
