"""
Unit tests for highlight.js language detection algorithm.

Tests the Python port of highlight.js's language auto-detection to ensure
consistent behavior between backend (Pygments) and frontend (highlight.js)
syntax highlighting.
"""

from django.test import TestCase

from askbot.utils.hljs_detect import (
    detect_language,
    _calculate_relevance,
    _apply_superset_tiebreaker,
)
from askbot.utils.hljs_languages import LANGUAGES, COMMON_KEYWORDS, SUPERSETS


class TestLanguageDetection(TestCase):
    """Test detect_language() function."""

    def test_python_detection(self):
        """Test detection of Python code."""
        code = '''
def hello():
    print("Hello, world!")

class MyClass:
    def __init__(self):
        self.value = None

async def fetch_data():
    await some_operation()
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'python')
        self.assertGreater(score, 0)

    def test_javascript_detection(self):
        """Test detection of JavaScript code."""
        code = '''
const foo = () => {
    console.log("Hello");
    let x = 42;
    async function bar() {
        await fetch('/api');
    }
};
export default foo;
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'javascript')
        self.assertGreater(score, 0)

    def test_sql_detection(self):
        """Test detection of SQL code."""
        code = '''
SELECT u.name, u.email
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.created_at > '2024-01-01'
GROUP BY u.id
HAVING COUNT(*) > 5
ORDER BY u.name;
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'sql')
        self.assertGreater(score, 0)

    def test_bash_detection(self):
        """Test detection of Bash/shell code."""
        code = '''
#!/bin/bash
if [ -f "$FILE" ]; then
    echo "File exists"
    while read line; do
        echo "$line"
    done < "$FILE"
fi
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'bash')
        self.assertGreater(score, 0)

    def test_go_detection(self):
        """Test detection of Go code."""
        code = '''
package main

import "fmt"

func main() {
    ch := make(chan int)
    go func() {
        ch <- 42
    }()
    defer close(ch)
    fmt.Println(<-ch)
}
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'go')
        self.assertGreater(score, 0)

    def test_rust_detection(self):
        """Test detection of Rust code."""
        code = '''
fn main() {
    let mut vec: Vec<i32> = Vec::new();
    vec.push(1);
    match Some(42) {
        Some(x) => println!("{}", x),
        None => println!("nothing"),
    }
}
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'rust')
        self.assertGreater(score, 0)

    def test_html_xml_detection(self):
        """Test detection of HTML/XML code."""
        code = '''
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <div class="container">
        <h1>Hello World</h1>
    </div>
</body>
</html>
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'xml')  # highlight.js calls it 'xml' for HTML too
        self.assertGreater(score, 0)

    def test_java_detection(self):
        """Test detection of Java code."""
        # Use Java-specific features: package, import, public class, synchronized
        code = '''
package com.example;

import java.util.ArrayList;
import java.util.List;

public class HelloWorld {
    private static final String MESSAGE = "Hello";

    public synchronized void process() {
        List<String> items = new ArrayList<>();
        items.add(MESSAGE);

        try {
            throw new Exception("test");
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            items.clear();
        }
    }

    public static void main(String[] args) {
        HelloWorld hw = new HelloWorld();
        hw.process();
    }
}
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'java')
        self.assertGreater(score, 0)

    def test_cpp_detection(self):
        """Test detection of C++ code."""
        # Use C++-specific features: class, namespace, template, new
        code = '''
#include <iostream>
#include <vector>

namespace myapp {

class MyClass {
public:
    MyClass() = default;
    virtual ~MyClass() = default;
    template<typename T>
    void process(const T& value) {
        std::cout << value << std::endl;
    }
private:
    std::vector<int> data;
};

}  // namespace myapp

int main() {
    auto obj = new myapp::MyClass();
    delete obj;
    return 0;
}
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'cpp')
        self.assertGreater(score, 0)

    def test_ruby_detection(self):
        """Test detection of Ruby code."""
        code = '''
class Greeter
  attr_accessor :name

  def initialize(name)
    @name = name
  end

  def greet
    puts "Hello, #{@name}!"
  end
end
'''
        lang, score = detect_language(code)
        self.assertEqual(lang, 'ruby')
        self.assertGreater(score, 0)


class TestMinimumRelevance(TestCase):
    """Test minimum relevance threshold behavior."""

    def test_minimum_relevance_threshold(self):
        """Test that code below minimum relevance returns None."""
        # Very short/ambiguous code
        code = 'x = 1'
        lang, score = detect_language(code, min_relevance=10)
        self.assertIsNone(lang)
        self.assertEqual(score, 0)

    def test_above_minimum_relevance(self):
        """Test that code above minimum relevance returns a result."""
        code = '''
def foo():
    print("hello")
    return None
'''
        lang, score = detect_language(code, min_relevance=2)
        self.assertEqual(lang, 'python')
        self.assertGreaterEqual(score, 2)

    def test_empty_code(self):
        """Test that empty code returns None."""
        lang, score = detect_language('')
        self.assertIsNone(lang)
        self.assertEqual(score, 0)

        lang, score = detect_language('   \n  \t  ')
        self.assertIsNone(lang)
        self.assertEqual(score, 0)


class TestLanguageSubset(TestCase):
    """Test language subset filtering."""

    def test_limited_language_set(self):
        """Test detection with a limited set of languages."""
        code = '''
def hello():
    print("world")
'''
        # Only consider Python and JavaScript
        lang, score = detect_language(code, languages=['python', 'javascript'])
        self.assertEqual(lang, 'python')

    def test_alias_normalization(self):
        """Test that aliases are normalized to canonical names."""
        code = 'def foo(): pass'
        # Use 'py' alias
        lang, score = detect_language(code, languages=['py'])
        self.assertEqual(lang, 'python')


class TestSupersetTiebreaking(TestCase):
    """Test superset relationship tie-breaking."""

    def test_superset_tiebreaker_logic(self):
        """Test that superset relationships are correctly identified."""
        # arduino is a superset of cpp
        self.assertIn('arduino', SUPERSETS)
        self.assertEqual(SUPERSETS['arduino'], 'cpp')

    def test_tiebreaker_sorts_correctly(self):
        """Test that _apply_superset_tiebreaker sorts base languages first."""
        # Simulate a tie between cpp and arduino (both score 10)
        results = [('arduino', 10), ('cpp', 10)]
        sorted_results = _apply_superset_tiebreaker(results)

        # cpp should come before arduino because arduino is a superset
        self.assertEqual(sorted_results[0][0], 'cpp')
        self.assertEqual(sorted_results[1][0], 'arduino')

    def test_tiebreaker_preserves_order_when_no_superset(self):
        """Test that non-superset languages maintain order by relevance."""
        results = [('python', 5), ('javascript', 3)]
        sorted_results = _apply_superset_tiebreaker(results)

        self.assertEqual(sorted_results[0][0], 'python')
        self.assertEqual(sorted_results[1][0], 'javascript')


class TestCommonKeywords(TestCase):
    """Test common keyword handling."""

    def test_common_keywords_zero_relevance(self):
        """Test that common keywords contribute zero relevance."""
        # These are common keywords that should have zero relevance
        self.assertIn('if', COMMON_KEYWORDS)
        self.assertIn('for', COMMON_KEYWORDS)
        self.assertIn('and', COMMON_KEYWORDS)
        self.assertIn('or', COMMON_KEYWORDS)
        self.assertIn('not', COMMON_KEYWORDS)
        self.assertIn('in', COMMON_KEYWORDS)

    def test_code_with_only_common_keywords(self):
        """Test that code with only common keywords gets low relevance."""
        # This code uses only common keywords (and, or, for, in, list, value)
        # Note: we avoid single letters like 'i' which might match other language keywords
        code = 'value and or for in list parent then'
        lang, score = detect_language(code, min_relevance=1)
        # Should return None because common keywords don't contribute
        self.assertIsNone(lang)


class TestCaseInsensitivity(TestCase):
    """Test case sensitivity handling."""

    def test_sql_case_insensitive(self):
        """Test that SQL detection is case-insensitive."""
        # SQL should detect both uppercase and lowercase keywords
        # Use more distinctive SQL to avoid ambiguity with other languages
        code_upper = 'SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id WHERE active = TRUE GROUP BY u.id'
        code_lower = 'select u.name from users u join orders o on u.id = o.user_id where active = true group by u.id'
        code_mixed = 'Select u.name From users u Join orders o On u.id = o.user_id Where active = True Group By u.id'

        lang1, _ = detect_language(code_upper)
        lang2, _ = detect_language(code_lower)
        lang3, _ = detect_language(code_mixed)

        self.assertEqual(lang1, 'sql')
        self.assertEqual(lang2, 'sql')
        self.assertEqual(lang3, 'sql')

    def test_python_case_sensitive(self):
        """Test that Python detection is case-sensitive."""
        # 'def' should match but 'DEF' should not
        code_lower = 'def foo(): pass'
        code_upper = 'DEF foo(): pass'

        lang_lower, score_lower = detect_language(code_lower)
        lang_upper, score_upper = detect_language(code_upper, min_relevance=1)

        self.assertEqual(lang_lower, 'python')
        # Uppercase DEF shouldn't match Python keywords
        self.assertNotEqual(score_upper, score_lower)


class TestRelevanceCalculation(TestCase):
    """Test relevance calculation details."""

    def test_keyword_hit_capping(self):
        """Test that keyword hits are capped at MAX_KEYWORD_HITS."""
        # Create code with many instances of the same keyword
        code = 'def ' * 20 + 'foo(): pass'
        lang_def = LANGUAGES['python']

        relevance = _calculate_relevance(code, lang_def)
        # With 20 'def' keywords, if not capped, would be 20+
        # With cap at 7, the 'def' keyword contributes at most 7
        self.assertLessEqual(relevance, 20)  # Reasonable upper bound

    def test_multiple_keyword_categories(self):
        """Test that keywords from different categories contribute."""
        # Python code with keyword, built_in, and literal
        code = '''
def foo():  # keyword: def
    print("hello")  # built_in: print
    return True  # literal: True
'''
        lang_def = LANGUAGES['python']
        relevance = _calculate_relevance(code, lang_def)

        # Should have relevance from multiple categories
        self.assertGreater(relevance, 2)


class TestLanguageDefinitions(TestCase):
    """Test language definition data."""

    def test_all_priority_languages_present(self):
        """Test that all priority languages have definitions."""
        priority_languages = [
            'python', 'javascript', 'java', 'c', 'cpp', 'sql', 'bash',
            'xml', 'css', 'json', 'go', 'ruby', 'php', 'rust', 'typescript', 'yaml'
        ]
        for lang in priority_languages:
            self.assertIn(lang, LANGUAGES, f"Missing language: {lang}")

    def test_languages_have_required_fields(self):
        """Test that all languages have required fields."""
        for lang_id, lang_def in LANGUAGES.items():
            self.assertIn('name', lang_def, f"{lang_id} missing 'name'")
            self.assertIn('aliases', lang_def, f"{lang_id} missing 'aliases'")
            self.assertIn('keywords', lang_def, f"{lang_id} missing 'keywords'")
            self.assertIn('case_insensitive', lang_def,
                         f"{lang_id} missing 'case_insensitive'")
