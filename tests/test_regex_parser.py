"""Tests for the regular expression parser (tokenizer, concatenation, postfix, validation)."""

import pytest

from core.regex_parser import (
    CONCAT,
    EPSILON,
    LEFT_PAREN,
    LITERAL,
    MAX_EXPRESSION_LENGTH,
    OPERATOR_ARITY,
    OPTIONAL,
    PLUS,
    RIGHT_PAREN,
    STAR,
    UNION,
    RegexSyntaxError,
    Token,
    format_tokens,
    insert_concatenation,
    parse_regex,
    to_postfix,
    tokenize,
    validate_regex,
)


def kinds_and_values(tokens):
    return [(token.kind, token.value) for token in tokens]


def assert_postfix_is_well_formed(postfix):
    """Simulate the stack Module 03 will use: every operator must find its operands."""
    depth = 0
    for token in postfix:
        if token.is_operand:
            depth += 1
        else:
            arity = OPERATOR_ARITY[token.kind]
            assert depth >= arity, f"operator {token.display} lacks operands"
            depth -= arity - 1
    assert depth == 1


# --- A: basic expressions -------------------------------------------------

@pytest.mark.parametrize(
    "expression, postfix, alphabet",
    [
        ("a", "a", {"a"}),
        ("b", "b", {"b"}),
        ("0", "0", {"0"}),
        ("1", "1", {"1"}),
        ("ab", "ab.", {"a", "b"}),
        ("abc", "ab.c.", {"a", "b", "c"}),
        ("a|b", "ab|", {"a", "b"}),
        ("0|1", "01|", {"0", "1"}),
        ("a*", "a*", {"a"}),
        ("a+", "a+", {"a"}),
        ("a?", "a?", {"a"}),
    ],
)
def test_basic_expressions(expression, postfix, alphabet):
    parsed = parse_regex(expression)
    assert parsed.original == expression
    assert parsed.postfix_form == postfix
    assert parsed.alphabet == frozenset(alphabet)
    assert_postfix_is_well_formed(parsed.postfix)


def test_basic_token_kinds():
    assert kinds_and_values(tokenize("a|b*c+d?")) == [
        (LITERAL, "a"), (UNION, "|"), (LITERAL, "b"), (STAR, "*"),
        (LITERAL, "c"), (PLUS, "+"), (LITERAL, "d"), (OPTIONAL, "?"),
    ]


def test_tokenize_records_one_based_positions():
    tokens = tokenize("a (b)")
    assert [token.position for token in tokens] == [1, 3, 4, 5]


def test_tokenize_groups_and_operators():
    assert kinds_and_values(tokenize("a(b|c)*")) == [
        (LITERAL, "a"), (LEFT_PAREN, "("), (LITERAL, "b"), (UNION, "|"),
        (LITERAL, "c"), (RIGHT_PAREN, ")"), (STAR, "*"),
    ]


def test_supported_literal_characters():
    parsed = parse_regex("aZ09_")
    assert parsed.alphabet == frozenset("aZ09_")


# --- B: parentheses and nesting -------------------------------------------

@pytest.mark.parametrize(
    "expression, postfix",
    [
        ("(ab)", "ab."),
        ("(a|b)", "ab|"),
        ("a(b|c)", "abc|."),
        ("(a|b)c", "ab|c."),
        ("((a|b))", "ab|"),
        ("((a|b)c)*", "ab|c.*"),
        ("(ab)+", "ab.+"),
        ("(a|b)*(ab|ba)", "ab|*ab.ba.|."),
    ],
)
def test_parentheses(expression, postfix):
    parsed = parse_regex(expression)
    assert parsed.postfix_form == postfix
    assert all(token.kind not in (LEFT_PAREN, RIGHT_PAREN) for token in parsed.postfix)
    assert_postfix_is_well_formed(parsed.postfix)


# --- C: concatenation -----------------------------------------------------

@pytest.mark.parametrize(
    "expression, explicit, concat_count",
    [
        ("ab", "a.b", 1),
        ("abc", "a.b.c", 2),
        ("a(b)", "a.(b)", 1),
        ("(a)b", "(a).b", 1),
        ("(a)(b)", "(a).(b)", 1),
        ("a*b", "a*.b", 1),
        ("a+b", "a+.b", 1),
        ("a?b", "a?.b", 1),
        ("(a|b)(c|d)", "(a|b).(c|d)", 1),
        ("a|b", "a|b", 0),
        ("(a|b)*abb", "(a|b)*.a.b.b", 3),
    ],
)
def test_implicit_concatenation(expression, explicit, concat_count):
    parsed = parse_regex(expression)
    assert parsed.explicit_form == explicit
    assert sum(token.kind == CONCAT for token in parsed.infix) == concat_count


def test_explicit_concatenation_matches_implicit():
    assert parse_regex("a.b.c").postfix_form == parse_regex("abc").postfix_form == "ab.c."
    assert parse_regex("(a|b).c").postfix_form == parse_regex("(a|b)c").postfix_form


def test_inserted_concatenation_has_no_position():
    infix = insert_concatenation(tokenize("ab"))
    assert infix[1] == Token(CONCAT, ".", None)


# --- D: operator precedence -----------------------------------------------

@pytest.mark.parametrize(
    "expression, expected",
    [
        ("a|bc", [(LITERAL, "a"), (LITERAL, "b"), (LITERAL, "c"), (CONCAT, "."), (UNION, "|")]),
        ("ab|c", [(LITERAL, "a"), (LITERAL, "b"), (CONCAT, "."), (LITERAL, "c"), (UNION, "|")]),
        ("ab*", [(LITERAL, "a"), (LITERAL, "b"), (STAR, "*"), (CONCAT, ".")]),
        ("(ab)*", [(LITERAL, "a"), (LITERAL, "b"), (CONCAT, "."), (STAR, "*")]),
        ("a|b*", [(LITERAL, "a"), (LITERAL, "b"), (STAR, "*"), (UNION, "|")]),
        ("(a|b)*abb", [
            (LITERAL, "a"), (LITERAL, "b"), (UNION, "|"), (STAR, "*"),
            (LITERAL, "a"), (CONCAT, "."), (LITERAL, "b"), (CONCAT, "."),
            (LITERAL, "b"), (CONCAT, "."),
        ]),
        ("a(b|c)*", [(LITERAL, "a"), (LITERAL, "b"), (LITERAL, "c"), (UNION, "|"), (STAR, "*"), (CONCAT, ".")]),
        ("a|bc*", [(LITERAL, "a"), (LITERAL, "b"), (LITERAL, "c"), (STAR, "*"), (CONCAT, "."), (UNION, "|")]),
    ],
)
def test_operator_precedence(expression, expected):
    assert kinds_and_values(parse_regex(expression).postfix) == expected


def test_union_and_concatenation_are_left_associative():
    assert parse_regex("a|b|c").postfix_form == "ab|c|"
    assert parse_regex("a.b.c").postfix_form == "ab.c."


# --- E: epsilon and lambda ------------------------------------------------

@pytest.mark.parametrize(
    "expression, postfix, alphabet",
    [
        ("ε", "ε", set()),
        ("λ", "ε", set()),
        ("a|ε", "aε|", {"a"}),
        ("(a|ε)b", "aε|b.", {"a", "b"}),
        ("εa", "εa.", {"a"}),
        ("aε", "aε.", {"a"}),
        ("ε*", "ε*", set()),
    ],
)
def test_epsilon_and_lambda(expression, postfix, alphabet):
    parsed = parse_regex(expression)
    assert parsed.postfix_form == postfix
    assert parsed.alphabet == frozenset(alphabet)
    assert "ε" not in parsed.alphabet and "λ" not in parsed.alphabet


def test_lambda_is_an_epsilon_token():
    assert tokenize("λ")[0].kind == EPSILON


def test_lowercase_e_is_a_literal():
    parsed = parse_regex("e|ε")
    assert parsed.alphabet == frozenset({"e"})
    assert kinds_and_values(parsed.postfix) == [(LITERAL, "e"), (EPSILON, "ε"), (UNION, "|")]


# --- F: escaped symbols ---------------------------------------------------

@pytest.mark.parametrize(
    "expression, literal",
    [
        (r"a\|b", "|"),
        (r"a\*b", "*"),
        (r"a\.b", "."),
        (r"a\(b", "("),
        (r"a\\b", "\\"),
        (r"a\+b", "+"),
        (r"a\?b", "?"),
        (r"a\)b", ")"),
    ],
)
def test_escaped_symbols_are_literals(expression, literal):
    parsed = parse_regex(expression)
    # Three literals joined by two concatenations: a <literal> b.
    assert kinds_and_values(parsed.postfix) == [
        (LITERAL, "a"), (LITERAL, literal), (CONCAT, "."), (LITERAL, "b"), (CONCAT, "."),
    ]
    assert parsed.alphabet == frozenset({"a", literal, "b"})


def test_escaped_literal_display_is_unambiguous():
    escaped = parse_regex(r"a\|b")
    union = parse_regex("a|b")
    assert escaped.postfix_form == r"a\|.b."
    assert union.postfix_form == "ab|"
    assert escaped.explicit_form == r"a.\|.b"


def test_escaped_operator_inside_expression():
    parsed = parse_regex(r"(a|\*)*")
    assert parsed.postfix_form == r"a\*|*"
    assert parsed.alphabet == frozenset({"a", "*"})


# --- G: invalid syntax ----------------------------------------------------

@pytest.mark.parametrize(
    "expression, message, position",
    [
        ("", "empty", None),
        ("   ", "empty", None),
        ("a|", "right-hand expression", 2),
        ("|a", "left-hand expression", 1),
        ("a||b", "directly follows", 3),
        ("(ab", "Unmatched '('", 1),
        ("ab)", "no matching '('", 3),
        ("()", "Empty group", 1),
        ("*a", "no expression before it", 1),
        ("a|*b", "no expression before it", 3),
        ("a.", "right-hand expression", 2),
        (".a", "left-hand expression", 1),
        ("a..b", "directly follows", 3),
        ("a(", "Unmatched '('", 2),
        ("a\\", "Incomplete escape", 2),
        ("a{2}", "counted repetition", 2),
        ("[ab]", "character classes", 1),
        ("a**", "repeated postfix", 3),
        ("a++", "repeated postfix", 3),
        ("a+?", "repeated postfix", 3),
        ("^a", "anchors", 1),
        ("a$", "anchors", 2),
        ("a-b", "Unsupported '-'", 2),
        ("aé", "Unsupported 'é'", 2),
        ("a\\ b", "whitespace", 2),
        ("a\\ε", "reserved for the empty string", 2),
        ("a\\d", "Unsupported escape", 2),
        ("(a|)", "right-hand expression", 4),
        ("(|a)", "left-hand expression", 2),
        ("a|.b", "directly follows", 3),
        ("((a)", "Unmatched '('", 1),
        ("(a))", "no matching '('", 4),
        ("a(*b)", "no expression before it", 3),
    ],
)
def test_invalid_syntax(expression, message, position):
    with pytest.raises(RegexSyntaxError, match=message.replace("(", r"\(").replace("[", r"\[")) as info:
        parse_regex(expression)
    assert info.value.position == position


def test_error_message_names_operator_and_position():
    with pytest.raises(RegexSyntaxError) as info:
        validate_regex("a|")
    assert str(info.value) == "Unexpected '|' at position 2: a right-hand expression is required."


def test_whitespace_is_ignored_between_tokens():
    assert parse_regex(" a | b ").postfix_form == parse_regex("a|b").postfix_form
    assert parse_regex("( a b ) *").postfix_form == "ab.*"


def test_deeply_nested_valid_groups():
    expression = "(" * 50 + "a|b" + ")" * 50 + "*"
    parsed = parse_regex(expression)
    assert parsed.postfix_form == "ab|*"


def test_parser_error_is_a_value_error():
    assert issubclass(RegexSyntaxError, ValueError)


# --- H: input limits ------------------------------------------------------

def test_expression_at_length_limit_is_accepted():
    expression = "a" * MAX_EXPRESSION_LENGTH
    parsed = parse_regex(expression)
    assert len(parsed.postfix) == 2 * MAX_EXPRESSION_LENGTH - 1


def test_expression_over_length_limit_is_rejected():
    with pytest.raises(RegexSyntaxError, match=f"maximum is {MAX_EXPRESSION_LENGTH}"):
        parse_regex("a" * (MAX_EXPRESSION_LENGTH + 1))


def test_complex_expression():
    expression = "((a|b)*c(d|e|ε)+f?)|(0|1)*01|\\(x\\)"
    parsed = parse_regex(expression)
    assert_postfix_is_well_formed(parsed.postfix)
    assert parsed.alphabet == frozenset("abcdef01x()")


# --- Stage functions individually ----------------------------------------

def test_to_postfix_on_explicit_infix_tokens():
    infix = insert_concatenation(tokenize("(a|b)*abb"))
    assert format_tokens(infix) == "(a|b)*.a.b.b"
    assert format_tokens(to_postfix(infix)) == "ab|*a.b.b."


def test_parsed_regex_is_immutable():
    parsed = parse_regex("ab")
    assert isinstance(parsed.postfix, tuple)
    assert isinstance(parsed.alphabet, frozenset)
    with pytest.raises(AttributeError):
        parsed.original = "x"
