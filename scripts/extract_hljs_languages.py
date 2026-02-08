#!/usr/bin/env python3
"""
Extract language definitions from highlight.js clean source files.

This script parses highlight.js v11.11.1 language definitions from the
clean (non-minified) source files and generates a Python module with
keyword data for language auto-detection.

Usage:
    python scripts/extract_hljs_languages.py

Source:
    ~/other-prog/highlightjs/src/languages/*.js

Output:
    askbot/utils/hljs_languages.py
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any


# Priority languages to extract (most commonly used)
PRIORITY_LANGUAGES = [
    'python',
    'javascript',
    'java',
    'c',
    'cpp',
    'sql',
    'bash',
    'xml',
    'css',
    'json',
    'go',
    'ruby',
    'php',
    'rust',
    'typescript',
    'yaml',
]

# Common keywords with zero relevance (from highlight.js core.js line 876-888)
COMMON_KEYWORDS = {
    'of', 'and', 'for', 'in', 'not', 'or', 'if', 'then',
    'parent', 'list', 'value'
}

# Superset relationships (manually extracted from language files)
# Format: {'superset_lang': 'base_lang'}
# Meaning: superset_lang is a superset of base_lang (base wins on tie)
SUPERSETS = {
    'arduino': 'cpp',
    'pgsql': 'sql',
    'typescript': 'javascript',
}

# ECMAScript keywords (from lib/ecmascript.js) - used by javascript/typescript
ECMASCRIPT_KEYWORDS = [
    "as", "in", "of", "if", "for", "while", "finally", "var", "new",
    "function", "do", "return", "void", "else", "break", "catch",
    "instanceof", "with", "throw", "case", "default", "try", "switch",
    "continue", "typeof", "delete", "let", "yield", "const", "class",
    "debugger", "async", "await", "static", "import", "from", "export",
    "extends", "using"
]

ECMASCRIPT_LITERALS = [
    "true", "false", "null", "undefined", "NaN", "Infinity"
]

ECMASCRIPT_TYPES = [
    "Object", "Function", "Boolean", "Symbol", "Math", "Date", "Number",
    "BigInt", "String", "RegExp", "Array", "Float32Array", "Float64Array",
    "Int8Array", "Uint8Array", "Uint8ClampedArray", "Int16Array", "Int32Array",
    "Uint16Array", "Uint32Array", "BigInt64Array", "BigUint64Array", "Set",
    "Map", "WeakSet", "WeakMap", "ArrayBuffer", "SharedArrayBuffer", "Atomics",
    "DataView", "JSON", "Promise", "Generator", "GeneratorFunction",
    "AsyncFunction", "Reflect", "Proxy", "Intl", "WebAssembly"
]

ECMASCRIPT_ERROR_TYPES = [
    "Error", "EvalError", "InternalError", "RangeError", "ReferenceError",
    "SyntaxError", "TypeError", "URIError"
]

ECMASCRIPT_BUILT_IN_GLOBALS = [
    "setInterval", "setTimeout", "clearInterval", "clearTimeout", "require",
    "exports", "eval", "isFinite", "isNaN", "parseFloat", "parseInt",
    "decodeURI", "decodeURIComponent", "encodeURI", "encodeURIComponent",
    "escape", "unescape"
]

ECMASCRIPT_BUILT_IN_VARIABLES = [
    "arguments", "this", "super", "console", "window", "document",
    "localStorage", "sessionStorage", "module", "global"
]


def extract_js_array(content: str, var_name: str) -> List[str]:
    """Extract a JavaScript const/let/var array definition."""
    # Match: const VAR_NAME = [...] with multiline support
    pattern = rf'(?:const|let|var)\s+{var_name}\s*=\s*\[(.*?)\];'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    array_str = match.group(1)
    items = []

    # Match quoted strings (single or double) with optional |N relevance suffix
    for m in re.finditer(r'["\']([^"\']+)["\']', array_str):
        item = m.group(1).split('|')[0]  # Remove relevance suffix like "nonlocal|10"
        items.append(item)

    return items


def extract_space_separated_keywords(content: str, var_name: str) -> List[str]:
    """Extract space-separated keyword string like: const LITERALS = 'true false yes no null'"""
    pattern = rf"(?:const|let|var)\s+{var_name}\s*=\s*['\"]([^'\"]+)['\"]"
    match = re.search(pattern, content)
    if match:
        return match.group(1).split()
    return []


def extract_name(content: str) -> Optional[str]:
    """Extract the language display name from the return object."""
    # Match: name: 'Python' or name: "Python"
    match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else None


def extract_aliases(content: str) -> List[str]:
    """Extract language aliases from the return object."""
    # Match: aliases: ['py', 'gyp', 'ipython']
    pattern = r"aliases:\s*\[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    array_str = match.group(1)
    aliases = []
    for m in re.finditer(r'["\']([^"\']+)["\']', array_str):
        aliases.append(m.group(1))
    return aliases


def extract_case_insensitive(content: str) -> bool:
    """Check if language is case insensitive."""
    # Match: case_insensitive: true
    return bool(re.search(r'case_insensitive:\s*true', content))


def parse_python_lang(content: str) -> Dict[str, Any]:
    """Parse Python language definition."""
    return {
        'name': extract_name(content) or 'Python',
        'aliases': extract_aliases(content),
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': extract_js_array(content, 'RESERVED_WORDS'),
            'built_in': extract_js_array(content, 'BUILT_INS'),
            'literal': extract_js_array(content, 'LITERALS'),
            'type': extract_js_array(content, 'TYPES'),
        },
    }


def parse_javascript_lang(content: str) -> Dict[str, Any]:
    """Parse JavaScript language definition (uses ECMAScript lib)."""
    built_ins = ECMASCRIPT_BUILT_IN_GLOBALS + ECMASCRIPT_TYPES + ECMASCRIPT_ERROR_TYPES
    return {
        'name': extract_name(content) or 'JavaScript',
        'aliases': extract_aliases(content),
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': ECMASCRIPT_KEYWORDS,
            'built_in': built_ins,
            'literal': ECMASCRIPT_LITERALS,
        },
    }


def parse_typescript_lang(content: str) -> Dict[str, Any]:
    """Parse TypeScript language definition (extends JavaScript)."""
    # TypeScript adds extra keywords to JavaScript
    ts_keywords = ECMASCRIPT_KEYWORDS + [
        "type", "interface", "namespace", "declare", "enum", "keyof",
        "readonly", "abstract", "implements", "infer", "is", "override",
        "private", "protected", "public", "satisfies"
    ]
    built_ins = ECMASCRIPT_BUILT_IN_GLOBALS + ECMASCRIPT_TYPES + ECMASCRIPT_ERROR_TYPES
    return {
        'name': extract_name(content) or 'TypeScript',
        'aliases': extract_aliases(content),
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': ts_keywords,
            'built_in': built_ins,
            'literal': ECMASCRIPT_LITERALS,
        },
    }


def parse_java_lang(content: str) -> Dict[str, Any]:
    """Parse Java language definition."""
    # Extract keywords from the Java source
    keywords = extract_js_array(content, 'KEYWORDS')

    # If not found in array, try extracting from keywords object
    if not keywords:
        # Pattern for: keyword: [...] inside KEYWORDS object
        kw_match = re.search(r"keyword:\s*\[(.*?)\]", content, re.DOTALL)
        if kw_match:
            for m in re.finditer(r'["\']([^"\']+)["\']', kw_match.group(1)):
                keywords.append(m.group(1).split('|')[0])

    # Java keywords from highlight.js java.js
    if not keywords:
        keywords = [
            'abstract', 'assert', 'break', 'case', 'catch', 'class', 'const',
            'continue', 'default', 'do', 'else', 'enum', 'exports', 'extends',
            'final', 'finally', 'for', 'goto', 'if', 'implements', 'import',
            'instanceof', 'interface', 'module', 'native', 'new', 'non-sealed',
            'open', 'opens', 'package', 'permits', 'private', 'protected',
            'provides', 'public', 'record', 'requires', 'return', 'sealed',
            'static', 'strictfp', 'super', 'switch', 'synchronized', 'this',
            'throw', 'throws', 'to', 'transient', 'transitive', 'try', 'uses',
            'var', 'void', 'volatile', 'while', 'with', 'yield'
        ]

    return {
        'name': extract_name(content) or 'Java',
        'aliases': extract_aliases(content),
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': keywords,
            'literal': ['true', 'false', 'null'],
            'type': ['byte', 'short', 'char', 'int', 'long', 'float', 'double', 'boolean'],
        },
    }


def parse_c_lang(content: str) -> Dict[str, Any]:
    """Parse C language definition."""
    # C keywords from highlight.js c.js
    keywords = [
        'auto', 'break', 'case', 'const', 'continue', 'default', 'do', 'else',
        'enum', 'extern', 'for', 'goto', 'if', 'inline', 'register', 'restrict',
        'return', 'sizeof', 'static', 'struct', 'switch', 'typedef', 'union',
        'volatile', 'while', '_Alignas', '_Alignof', '_Atomic', '_Generic',
        '_Noreturn', '_Static_assert', '_Thread_local'
    ]
    types = [
        'char', 'double', 'float', 'int', 'long', 'short', 'signed', 'unsigned',
        'void', '_Bool', '_Complex', '_Imaginary', 'int8_t', 'int16_t', 'int32_t',
        'int64_t', 'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t', 'size_t',
        'ptrdiff_t', 'intptr_t', 'uintptr_t'
    ]
    return {
        'name': extract_name(content) or 'C',
        'aliases': extract_aliases(content) or ['h'],
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': keywords,
            'type': types,
            'literal': ['true', 'false', 'NULL'],
        },
    }


def parse_cpp_lang(content: str) -> Dict[str, Any]:
    """Parse C++ language definition."""
    # C++ adds to C keywords
    keywords = [
        'auto', 'break', 'case', 'catch', 'class', 'const', 'const_cast',
        'constexpr', 'continue', 'decltype', 'default', 'delete', 'do',
        'dynamic_cast', 'else', 'enum', 'explicit', 'export', 'extern', 'false',
        'final', 'for', 'friend', 'goto', 'if', 'inline', 'mutable', 'namespace',
        'new', 'noexcept', 'nullptr', 'operator', 'override', 'private',
        'protected', 'public', 'register', 'reinterpret_cast', 'return',
        'sizeof', 'static', 'static_assert', 'static_cast', 'struct', 'switch',
        'template', 'this', 'thread_local', 'throw', 'true', 'try', 'typedef',
        'typeid', 'typename', 'union', 'using', 'virtual', 'volatile', 'while',
        'alignas', 'alignof', 'char8_t', 'char16_t', 'char32_t', 'concept',
        'consteval', 'constinit', 'co_await', 'co_return', 'co_yield', 'requires'
    ]
    types = [
        'bool', 'char', 'double', 'float', 'int', 'long', 'short', 'signed',
        'unsigned', 'void', 'wchar_t', 'int8_t', 'int16_t', 'int32_t', 'int64_t',
        'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t', 'size_t', 'ptrdiff_t',
        'intptr_t', 'uintptr_t', 'string', 'vector', 'map', 'set', 'list',
        'deque', 'array', 'pair', 'tuple', 'shared_ptr', 'unique_ptr', 'weak_ptr'
    ]
    return {
        'name': extract_name(content) or 'C++',
        'aliases': extract_aliases(content) or ['cc', 'c++', 'hpp', 'hh', 'h++', 'cxx', 'hxx'],
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': keywords,
            'type': types,
            'literal': ['true', 'false', 'nullptr', 'NULL'],
        },
    }


def parse_sql_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse SQL language definition."""
    keywords = [
        'ADD', 'ALL', 'ALTER', 'AND', 'AS', 'ASC', 'BETWEEN', 'BY', 'CASE',
        'CHECK', 'COLUMN', 'CONSTRAINT', 'CREATE', 'CROSS', 'DATABASE', 'DELETE',
        'DESC', 'DISTINCT', 'DROP', 'ELSE', 'END', 'EXISTS', 'FOREIGN', 'FROM',
        'FULL', 'GROUP', 'HAVING', 'IN', 'INDEX', 'INNER', 'INSERT', 'INTO',
        'IS', 'JOIN', 'KEY', 'LEFT', 'LIKE', 'LIMIT', 'NOT', 'NULL', 'ON', 'OR',
        'ORDER', 'OUTER', 'PRIMARY', 'REFERENCES', 'RIGHT', 'SELECT', 'SET',
        'TABLE', 'THEN', 'TOP', 'TRUNCATE', 'UNION', 'UNIQUE', 'UPDATE', 'VALUES',
        'VIEW', 'WHEN', 'WHERE', 'WITH'
    ]
    built_ins = [
        'AVG', 'COUNT', 'MAX', 'MIN', 'SUM', 'COALESCE', 'NULLIF', 'CAST',
        'CONVERT', 'SUBSTRING', 'TRIM', 'UPPER', 'LOWER', 'LENGTH', 'CONCAT',
        'NOW', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'EXTRACT',
        'DATE_ADD', 'DATE_SUB', 'DATEDIFF', 'ROUND', 'FLOOR', 'CEIL', 'ABS',
        'MOD', 'IFNULL', 'IIF', 'NVL', 'DECODE'
    ]
    types = [
        'INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT', 'FLOAT', 'REAL',
        'DOUBLE', 'DECIMAL', 'NUMERIC', 'CHAR', 'VARCHAR', 'TEXT', 'NCHAR',
        'NVARCHAR', 'NTEXT', 'BINARY', 'VARBINARY', 'IMAGE', 'DATE', 'TIME',
        'DATETIME', 'TIMESTAMP', 'BOOLEAN', 'BOOL', 'BIT', 'BLOB', 'CLOB'
    ]
    return {
        'name': 'SQL',
        'aliases': [],
        'case_insensitive': True,
        'keywords': {
            'keyword': keywords,
            'built_in': built_ins,
            'type': types,
            'literal': ['TRUE', 'FALSE', 'NULL'],
        },
    }


def parse_bash_lang(content: str) -> Dict[str, Any]:
    """Parse Bash language definition."""
    keywords = [
        'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'in', 'do', 'done',
        'case', 'esac', 'function', 'select', 'until', 'return', 'exit',
        'break', 'continue', 'declare', 'typeset', 'local', 'export', 'readonly',
        'unset', 'shift', 'eval', 'exec', 'set', 'shopt', 'trap', 'source'
    ]
    built_ins = [
        'echo', 'printf', 'read', 'cd', 'pwd', 'pushd', 'popd', 'dirs', 'let',
        'test', 'true', 'false', 'alias', 'unalias', 'bind', 'builtin', 'caller',
        'command', 'compgen', 'complete', 'compopt', 'enable', 'getopts', 'hash',
        'help', 'history', 'jobs', 'kill', 'logout', 'mapfile', 'readarray',
        'suspend', 'times', 'type', 'ulimit', 'umask', 'wait', 'bg', 'fg',
        'disown', 'coproc'
    ]
    return {
        'name': extract_name(content) or 'Bash',
        'aliases': extract_aliases(content) or ['sh', 'zsh', 'shell'],
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {
            'keyword': keywords,
            'built_in': built_ins,
            'literal': ['true', 'false'],
        },
    }


def parse_xml_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse XML/HTML language definition."""
    # XML has no traditional keywords, detection is based on tag patterns
    return {
        'name': 'XML',
        'aliases': ['html', 'xhtml', 'rss', 'atom', 'xjb', 'xsd', 'xsl', 'plist', 'svg'],
        'case_insensitive': True,
        'keywords': {
            # HTML-specific tags as "keywords" for detection
            'keyword': ['DOCTYPE', 'CDATA'],
            'built_in': [
                'html', 'head', 'body', 'div', 'span', 'p', 'a', 'img', 'table',
                'tr', 'td', 'th', 'form', 'input', 'button', 'script', 'style',
                'link', 'meta', 'title', 'header', 'footer', 'nav', 'section',
                'article', 'aside', 'main', 'ul', 'ol', 'li', 'h1', 'h2', 'h3',
                'h4', 'h5', 'h6', 'br', 'hr', 'pre', 'code', 'blockquote', 'em',
                'strong', 'b', 'i', 'u', 'select', 'option', 'textarea', 'label'
            ],
        },
    }


def parse_css_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse CSS language definition."""
    # CSS keywords and properties
    keywords = [
        '@import', '@media', '@font-face', '@keyframes', '@supports', '@page',
        '@charset', '@namespace', '!important'
    ]
    built_ins = [
        'color', 'background', 'background-color', 'background-image', 'border',
        'border-radius', 'margin', 'padding', 'width', 'height', 'display',
        'position', 'top', 'right', 'bottom', 'left', 'float', 'clear', 'font',
        'font-size', 'font-family', 'font-weight', 'text-align', 'text-decoration',
        'line-height', 'letter-spacing', 'overflow', 'visibility', 'opacity',
        'z-index', 'flex', 'grid', 'transform', 'transition', 'animation',
        'box-shadow', 'cursor', 'content', 'list-style', 'vertical-align',
        'white-space', 'word-wrap', 'box-sizing', 'outline', 'min-width',
        'max-width', 'min-height', 'max-height'
    ]
    return {
        'name': 'CSS',
        'aliases': [],
        'case_insensitive': True,
        'keywords': {
            'keyword': keywords,
            'built_in': built_ins,
            'literal': ['inherit', 'initial', 'unset', 'none', 'auto', 'transparent'],
        },
    }


def parse_json_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse JSON language definition."""
    return {
        'name': 'JSON',
        'aliases': ['jsonc', 'json5'],
        'case_insensitive': False,
        'keywords': {
            'literal': ['true', 'false', 'null'],
        },
    }


def parse_go_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse Go language definition."""
    keywords = [
        'break', 'case', 'chan', 'const', 'continue', 'default', 'defer', 'else',
        'fallthrough', 'for', 'func', 'go', 'goto', 'if', 'import', 'interface',
        'map', 'package', 'range', 'return', 'select', 'struct', 'switch', 'type',
        'var'
    ]
    types = [
        'bool', 'byte', 'complex64', 'complex128', 'error', 'float32', 'float64',
        'int', 'int8', 'int16', 'int32', 'int64', 'rune', 'string', 'uint',
        'uint8', 'uint16', 'uint32', 'uint64', 'uintptr'
    ]
    built_ins = [
        'append', 'cap', 'close', 'complex', 'copy', 'delete', 'imag', 'len',
        'make', 'new', 'panic', 'print', 'println', 'real', 'recover'
    ]
    return {
        'name': 'Go',
        'aliases': ['golang'],
        'case_insensitive': False,
        'keywords': {
            'keyword': keywords,
            'type': types,
            'built_in': built_ins,
            'literal': ['true', 'false', 'nil', 'iota'],
        },
    }


def parse_ruby_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse Ruby language definition."""
    keywords = [
        'alias', 'and', 'begin', 'break', 'case', 'class', 'def', 'defined',
        'do', 'else', 'elsif', 'end', 'ensure', 'false', 'for', 'if', 'in',
        'module', 'next', 'nil', 'not', 'or', 'redo', 'rescue', 'retry',
        'return', 'self', 'super', 'then', 'true', 'undef', 'unless', 'until',
        'when', 'while', 'yield', 'raise', 'require', 'require_relative',
        'include', 'extend', 'prepend', 'attr_accessor', 'attr_reader',
        'attr_writer', 'private', 'protected', 'public'
    ]
    built_ins = [
        'puts', 'print', 'p', 'gets', 'chomp', 'each', 'map', 'select', 'reject',
        'reduce', 'inject', 'find', 'any?', 'all?', 'none?', 'sort', 'sort_by',
        'reverse', 'first', 'last', 'take', 'drop', 'length', 'size', 'count',
        'empty?', 'nil?', 'to_s', 'to_i', 'to_f', 'to_a', 'to_h', 'split', 'join',
        'gsub', 'sub', 'match', 'scan', 'strip', 'upcase', 'downcase', 'capitalize'
    ]
    return {
        'name': 'Ruby',
        'aliases': ['rb', 'gemspec', 'podspec', 'thor', 'irb'],
        'case_insensitive': False,
        'keywords': {
            'keyword': keywords,
            'built_in': built_ins,
            'literal': ['true', 'false', 'nil'],
        },
    }


def parse_php_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse PHP language definition."""
    keywords = [
        'abstract', 'and', 'array', 'as', 'break', 'callable', 'case', 'catch',
        'class', 'clone', 'const', 'continue', 'declare', 'default', 'die', 'do',
        'echo', 'else', 'elseif', 'empty', 'enddeclare', 'endfor', 'endforeach',
        'endif', 'endswitch', 'endwhile', 'eval', 'exit', 'extends', 'final',
        'finally', 'fn', 'for', 'foreach', 'function', 'global', 'goto', 'if',
        'implements', 'include', 'include_once', 'instanceof', 'insteadof',
        'interface', 'isset', 'list', 'match', 'namespace', 'new', 'or', 'print',
        'private', 'protected', 'public', 'readonly', 'require', 'require_once',
        'return', 'static', 'switch', 'throw', 'trait', 'try', 'unset', 'use',
        'var', 'while', 'xor', 'yield', 'yield from'
    ]
    types = [
        'array', 'bool', 'boolean', 'callable', 'double', 'false', 'float', 'int',
        'integer', 'iterable', 'mixed', 'never', 'null', 'numeric', 'object',
        'resource', 'self', 'static', 'string', 'true', 'void'
    ]
    built_ins = [
        'isset', 'unset', 'empty', 'die', 'exit', 'echo', 'print', 'var_dump',
        'print_r', 'strlen', 'substr', 'strpos', 'str_replace', 'array_push',
        'array_pop', 'array_shift', 'array_unshift', 'array_merge', 'array_keys',
        'array_values', 'count', 'sizeof', 'in_array', 'array_search', 'sort',
        'rsort', 'asort', 'ksort', 'usort', 'json_encode', 'json_decode',
        'file_get_contents', 'file_put_contents', 'fopen', 'fclose', 'fread',
        'fwrite', 'preg_match', 'preg_replace'
    ]
    return {
        'name': 'PHP',
        'aliases': [],
        'case_insensitive': True,
        'keywords': {
            'keyword': keywords,
            'type': types,
            'built_in': built_ins,
            'literal': ['true', 'false', 'null', 'TRUE', 'FALSE', 'NULL'],
        },
    }


def parse_rust_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse Rust language definition."""
    keywords = [
        'as', 'async', 'await', 'break', 'const', 'continue', 'crate', 'dyn',
        'else', 'enum', 'extern', 'false', 'fn', 'for', 'if', 'impl', 'in',
        'let', 'loop', 'match', 'mod', 'move', 'mut', 'pub', 'ref', 'return',
        'self', 'Self', 'static', 'struct', 'super', 'trait', 'true', 'type',
        'unsafe', 'use', 'where', 'while', 'macro_rules'
    ]
    types = [
        'bool', 'char', 'f32', 'f64', 'i8', 'i16', 'i32', 'i64', 'i128', 'isize',
        'str', 'u8', 'u16', 'u32', 'u64', 'u128', 'usize', 'Box', 'Option',
        'Result', 'String', 'Vec', 'HashMap', 'HashSet', 'Rc', 'Arc', 'Cell',
        'RefCell', 'Mutex', 'RwLock'
    ]
    built_ins = [
        'drop', 'Some', 'None', 'Ok', 'Err', 'println', 'print', 'eprintln',
        'eprint', 'format', 'panic', 'assert', 'assert_eq', 'assert_ne', 'debug_assert',
        'vec', 'clone', 'to_string', 'to_owned', 'into', 'from', 'default'
    ]
    return {
        'name': 'Rust',
        'aliases': ['rs'],
        'case_insensitive': False,
        'keywords': {
            'keyword': keywords,
            'type': types,
            'built_in': built_ins,
            'literal': ['true', 'false'],
        },
    }


def parse_yaml_lang(content: str) -> Dict[str, Any]:  # noqa: ARG001
    """Parse YAML language definition."""
    # YAML literals (from the source: 'true false yes no null')
    literals = ['true', 'false', 'yes', 'no', 'null', 'True', 'False', 'Yes', 'No', 'Null', 'NULL']
    return {
        'name': 'YAML',
        'aliases': ['yml'],
        'case_insensitive': True,
        'keywords': {
            'literal': literals,
        },
    }


def parse_generic_lang(content: str, lang_name: str) -> Dict[str, Any]:
    """Generic parser for languages we don't have specific handlers for."""
    return {
        'name': extract_name(content) or lang_name.title(),
        'aliases': extract_aliases(content),
        'case_insensitive': extract_case_insensitive(content),
        'keywords': {},
    }


# Language-specific parsers
LANG_PARSERS: Dict[str, Any] = {
    'python': parse_python_lang,
    'javascript': parse_javascript_lang,
    'typescript': parse_typescript_lang,
    'java': parse_java_lang,
    'c': parse_c_lang,
    'cpp': parse_cpp_lang,
    'sql': parse_sql_lang,
    'bash': parse_bash_lang,
    'xml': parse_xml_lang,
    'css': parse_css_lang,
    'json': parse_json_lang,
    'go': parse_go_lang,
    'ruby': parse_ruby_lang,
    'php': parse_php_lang,
    'rust': parse_rust_lang,
    'yaml': parse_yaml_lang,
}


def parse_language_file(filepath: Path, lang: str) -> Optional[Dict[str, Any]]:
    """Parse a single language definition file."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    parser = LANG_PARSERS.get(lang)
    if parser is None:
        return parse_generic_lang(content, lang)
    return parser(content)


def generate_python_module(languages: Dict[str, Dict], output_path: Path):
    """Generate the Python module with language definitions."""
    lines = [
        '"""',
        'highlight.js language definitions for Python.',
        '',
        'Auto-generated by scripts/extract_hljs_languages.py',
        'Source: highlight.js v11.11.1',
        '',
        'This module provides keyword data for language auto-detection that matches',
        'the highlight.js frontend algorithm.',
        '"""',
        '',
        'from typing import Dict, List, Set, Any',
        '',
        '',
        '# Common keywords with zero relevance (from highlight.js core.js)',
        '# These words are too common across languages to provide meaningful signal',
        f'COMMON_KEYWORDS: Set[str] = {repr(COMMON_KEYWORDS)}',
        '',
        '',
        '# Maximum keyword hits per word before capping relevance',
        'MAX_KEYWORD_HITS: int = 7',
        '',
        '',
        '# Superset relationships: {superset_lang: base_lang}',
        '# When tied, the base language wins over its superset',
        f'SUPERSETS: Dict[str, str] = {repr(SUPERSETS)}',
        '',
        '',
        '# Language definitions',
        '# Each language has:',
        '#   - name: Display name',
        '#   - aliases: Alternative names for the language',
        '#   - case_insensitive: Whether keyword matching is case-insensitive',
        '#   - keywords: Dict of keyword categories (keyword, built_in, literal, type)',
        'LANGUAGES: Dict[str, Dict[str, Any]] = {',
    ]

    for lang_id, lang_data in sorted(languages.items()):
        lines.append(f'    {repr(lang_id)}: {{')
        lines.append(f'        "name": {repr(lang_data["name"])},')
        lines.append(f'        "aliases": {repr(lang_data["aliases"])},')
        lines.append(f'        "case_insensitive": {repr(lang_data["case_insensitive"])},')
        lines.append('        "keywords": {')
        for cat, words in lang_data['keywords'].items():
            if words:
                lines.append(f'            {repr(cat)}: {repr(words)},')
        lines.append('        },')
        lines.append('    },')

    lines.append('}')
    lines.append('')
    lines.append('')
    lines.append('# Build reverse lookup for aliases')
    lines.append('ALIAS_MAP: Dict[str, str] = {}')
    lines.append('for lang_id, lang_data in LANGUAGES.items():')
    lines.append('    ALIAS_MAP[lang_id] = lang_id')
    lines.append('    for alias in lang_data.get("aliases", []):')
    lines.append('        ALIAS_MAP[alias] = lang_id')
    lines.append('')

    output_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Generated {output_path}")


def main():
    # Use clean source files from cloned highlight.js repo
    source_dir = Path.home() / 'other-prog' / 'highlightjs' / 'src' / 'languages'

    if not source_dir.exists():
        print(f"Error: highlight.js source not found: {source_dir}")
        print("Please clone highlight.js to ~/other-prog/highlightjs")
        return 1

    print(f"Extracting languages from: {source_dir}")

    # Find output paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_path = project_root / 'askbot' / 'utils' / 'hljs_languages.py'

    # Parse priority languages
    languages = {}
    for lang in PRIORITY_LANGUAGES:
        filepath = source_dir / f'{lang}.js'
        if not filepath.exists():
            print(f"  Warning: {filepath.name} not found")
            continue

        print(f"  Processing {lang}...")
        lang_data = parse_language_file(filepath, lang)
        if lang_data:
            languages[lang] = lang_data
            # Show keyword count
            total_kw = sum(len(v) for v in lang_data['keywords'].values())
            print(f"    -> {total_kw} keywords")

    # Generate output module
    generate_python_module(languages, output_path)

    print(f"\nExtracted {len(languages)} languages")
    return 0


if __name__ == '__main__':
    exit(main())
