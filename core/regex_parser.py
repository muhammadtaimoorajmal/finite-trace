"""
Regular expression parser for FiniteTrace.

Turns a formal regular expression such as "(a|b)*abb" into a postfix token
sequence that Thompson's construction (core/thompson.py) can process with a stack.

Pipeline:
    1. tokenize()              characters    -> tokens (literals, operators, parentheses)
    2. check_syntax()          tokens        -> raises RegexSyntaxError on malformed input
    3. insert_concatenation()  tokens        -> tokens with explicit CONCAT where implied
    4. to_postfix()            infix tokens  -> postfix tokens (Shunting-Yard algorithm)

Supported grammar (from highest to lowest precedence):
    ( R )            grouping
    R*  R+  R?       postfix unary operators: star, plus, optional
    R S  or  R.S     concatenation
    R|S              union

Literals are ASCII letters, digits and "_". "ε" and "λ" both mean the empty
string. A backslash makes a reserved character literal, e.g. "\\|" is a pipe
symbol rather than union. Unescaped whitespace is ignored. Character
positions in error messages are counted from 1 and include whitespace.
"""

from dataclasses import dataclass
from typing import Optional

MAX_EXPRESSION_LENGTH = 512

# Token kinds.
LITERAL = "LITERAL"
EPSILON = "EPSILON"
UNION = "UNION"
CONCAT = "CONCAT"
STAR = "STAR"
PLUS = "PLUS"
OPTIONAL = "OPTIONAL"
LEFT_PAREN = "LEFT_PAREN"
RIGHT_PAREN = "RIGHT_PAREN"

# Characters that act as operators when they are not escaped.
OPERATOR_KINDS = {
    "|": UNION,
    ".": CONCAT,
    "*": STAR,
    "+": PLUS,
    "?": OPTIONAL,
    "(": LEFT_PAREN,
    ")": RIGHT_PAREN,
}
EPSILON_CHARACTERS = {"ε", "λ"}

# Characters that may follow a backslash to become literal symbols.
ESCAPABLE_CHARACTERS = set(OPERATOR_KINDS) | {"\\", "[", "]", "{", "}", "^", "$"}

# Number of operands each operator takes; core/thompson.py pops this many NFA fragments.
OPERATOR_ARITY = {UNION: 2, CONCAT: 2, STAR: 1, PLUS: 1, OPTIONAL: 1}

# Binary operator precedence: higher binds tighter. Postfix unary operators
# bind tighter than both, so to_postfix() emits them immediately.
BINARY_PRECEDENCE = {UNION: 1, CONCAT: 2}

UNARY_KINDS = {STAR, PLUS, OPTIONAL}
BINARY_KINDS = {UNION, CONCAT}
# A token that can start an operand, and a token that can end one.
OPERAND_START_KINDS = {LITERAL, EPSILON, LEFT_PAREN}
OPERAND_END_KINDS = {LITERAL, EPSILON, RIGHT_PAREN} | UNARY_KINDS

KIND_LABELS = {
    LITERAL: "Literal",
    EPSILON: "Epsilon",
    UNION: "Union",
    CONCAT: "Concatenation",
    STAR: "Kleene star",
    PLUS: "Kleene plus",
    OPTIONAL: "Optional",
    LEFT_PAREN: "Left parenthesis",
    RIGHT_PAREN: "Right parenthesis",
}


class RegexSyntaxError(ValueError):
    """Raised for malformed or unsupported regular expressions."""

    def __init__(self, message: str, position: Optional[int] = None):
        super().__init__(message)
        self.position = position  # 1-based character position, or None


@dataclass(frozen=True)
class Token:
    """One regex token. position is 1-based, or None for inserted concatenation."""

    kind: str
    value: str
    position: Optional[int] = None

    @property
    def is_operand(self) -> bool:
        return self.kind in (LITERAL, EPSILON)

    @property
    def is_operator(self) -> bool:
        return self.kind in OPERATOR_ARITY

    @property
    def display(self) -> str:
        """Unambiguous text form: literal reserved characters are shown escaped."""
        if self.kind == LITERAL and self.value in ESCAPABLE_CHARACTERS:
            return "\\" + self.value
        if self.kind == EPSILON:
            return "ε"
        return self.value


@dataclass(frozen=True)
class ParsedRegex:
    """Result of parse_regex(): the input, its tokens in infix and postfix order, and its alphabet."""

    original: str
    infix: tuple[Token, ...]      # with explicit CONCAT tokens inserted
    postfix: tuple[Token, ...]
    alphabet: frozenset[str]      # literal symbols only; epsilon is never included

    @property
    def explicit_form(self) -> str:
        return format_tokens(self.infix)

    @property
    def postfix_form(self) -> str:
        return format_tokens(self.postfix)


def format_tokens(tokens) -> str:
    """Join token display forms, e.g. tokens of a.b| become 'ab.|'."""
    return "".join(token.display for token in tokens)


def describe_token(token: Token) -> str:
    """Short plain-English meaning of a token, used in the interface."""
    descriptions = {
        EPSILON: "Match the empty string",
        UNION: "Either alternative",
        CONCAT: "Followed by",
        STAR: "Zero or more repetitions",
        PLUS: "One or more repetitions",
        OPTIONAL: "Zero or one occurrence",
        LEFT_PAREN: "Start of group",
        RIGHT_PAREN: "End of group",
    }
    if token.kind == LITERAL:
        return f"Match '{token.value}'"
    return descriptions[token.kind]


# ---------------------------------------------------------------------------
# Stage 1: tokenization
# ---------------------------------------------------------------------------

def _is_plain_literal(character: str) -> bool:
    return character.isascii() and (character.isalnum() or character == "_")


def _unsupported_character_error(character: str, position: int) -> RegexSyntaxError:
    hints = {
        "[": "character classes are not supported. Use explicit union, such as (a|b).",
        "]": "character classes are not supported. Use explicit union, such as (a|b).",
        "{": "counted repetition is not supported. Repeat the expression explicitly, such as aa instead of a{2}.",
        "}": "counted repetition is not supported. Repeat the expression explicitly, such as aa instead of a{2}.",
        "^": "anchors are not supported; every expression already describes whole strings.",
        "$": "anchors are not supported; every expression already describes whole strings.",
    }
    reason = hints.get(character, "it is not part of the supported syntax. Escape it with '\\' if allowed, or remove it.")
    return RegexSyntaxError(f"Unsupported '{character}' at position {position}: {reason}", position)


def tokenize(expression: str) -> list[Token]:
    """Split the expression into tokens, left to right. Whitespace is skipped."""
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise RegexSyntaxError(
            f"Expression is {len(expression)} characters long; the maximum is {MAX_EXPRESSION_LENGTH}."
        )

    tokens = []
    index = 0
    while index < len(expression):
        character = expression[index]
        position = index + 1

        if character.isspace():
            index += 1
            continue

        if character == "\\":
            if index + 1 >= len(expression):
                raise RegexSyntaxError(
                    f"Incomplete escape at position {position}: '\\' must be followed by the character to escape.",
                    position,
                )
            escaped = expression[index + 1]
            if escaped.isspace():
                raise RegexSyntaxError(
                    f"Escaped whitespace at position {position} is not allowed: whitespace cannot be an alphabet symbol.",
                    position,
                )
            if escaped in EPSILON_CHARACTERS:
                raise RegexSyntaxError(
                    f"'\\{escaped}' at position {position} is not allowed: '{escaped}' is reserved for the empty string.",
                    position,
                )
            if escaped not in ESCAPABLE_CHARACTERS:
                raise RegexSyntaxError(
                    f"Unsupported escape '\\{escaped}' at position {position}: only reserved characters "
                    f"({' '.join(sorted(ESCAPABLE_CHARACTERS))}) can be escaped.",
                    position,
                )
            tokens.append(Token(LITERAL, escaped, position))
            index += 2
            continue

        if character in OPERATOR_KINDS:
            tokens.append(Token(OPERATOR_KINDS[character], character, position))
        elif character in EPSILON_CHARACTERS:
            tokens.append(Token(EPSILON, character, position))
        elif _is_plain_literal(character):
            tokens.append(Token(LITERAL, character, position))
        else:
            raise _unsupported_character_error(character, position)
        index += 1

    return tokens


# ---------------------------------------------------------------------------
# Stage 2: syntax validation
# ---------------------------------------------------------------------------

def check_syntax(tokens: list[Token]) -> None:
    """
    Check that tokens form a well-formed expression, raising RegexSyntaxError otherwise.

    Each token is checked against the token before it, and parentheses are
    matched with a stack. Once this passes, postfix conversion cannot fail.
    """
    if not tokens:
        raise RegexSyntaxError(
            "The expression is empty. Enter a regular expression, or use ε for the empty-string language."
        )

    open_parens: list[Token] = []
    previous: Optional[Token] = None

    for token in tokens:
        if token.kind in BINARY_KINDS:
            if previous is None or previous.kind == LEFT_PAREN:
                raise RegexSyntaxError(
                    f"Unexpected '{token.value}' at position {token.position}: a left-hand expression is required.",
                    token.position,
                )
            if previous.kind in BINARY_KINDS:
                raise RegexSyntaxError(
                    f"Unexpected '{token.value}' at position {token.position}: it directly follows "
                    f"'{previous.value}' at position {previous.position}; an expression is required between them.",
                    token.position,
                )

        elif token.kind in UNARY_KINDS:
            if previous is not None and previous.kind in UNARY_KINDS:
                raise RegexSyntaxError(
                    f"Unexpected '{token.value}' at position {token.position}: repeated postfix operators such as "
                    f"'{previous.value}{token.value}' are not supported. Use parentheses, such as (a{previous.value}){token.value}.",
                    token.position,
                )
            if previous is None or previous.kind not in OPERAND_END_KINDS:
                raise RegexSyntaxError(
                    f"Unexpected '{token.value}' at position {token.position}: there is no expression before it to apply it to.",
                    token.position,
                )

        elif token.kind == LEFT_PAREN:
            open_parens.append(token)

        elif token.kind == RIGHT_PAREN:
            if not open_parens:
                raise RegexSyntaxError(
                    f"Unexpected ')' at position {token.position}: there is no matching '('.",
                    token.position,
                )
            opening = open_parens.pop()
            if previous.kind == LEFT_PAREN:
                raise RegexSyntaxError(
                    f"Empty group '()' at position {opening.position}: put an expression inside, or use ε for the empty string.",
                    opening.position,
                )
            if previous.kind in BINARY_KINDS:
                raise RegexSyntaxError(
                    f"Unexpected ')' at position {token.position}: a right-hand expression is required "
                    f"after '{previous.value}' at position {previous.position}.",
                    token.position,
                )

        previous = token

    if previous.kind in BINARY_KINDS:
        raise RegexSyntaxError(
            f"Unexpected '{previous.value}' at position {previous.position}: a right-hand expression is required.",
            previous.position,
        )
    if open_parens:
        opening = open_parens[-1]
        raise RegexSyntaxError(
            f"Unmatched '(' at position {opening.position}: missing closing ')'.",
            opening.position,
        )


# ---------------------------------------------------------------------------
# Stage 3: implicit concatenation
# ---------------------------------------------------------------------------

def insert_concatenation(tokens: list[Token]) -> list[Token]:
    """
    Insert CONCAT tokens wherever concatenation is implied.

    Two neighbouring tokens are concatenated when the first can end an operand
    (a literal, ε, ')' or a postfix operator) and the second can start one
    (a literal, ε or '('). Examples: "ab" -> "a.b", "a*(b)" -> "a*.(b)".
    """
    result = []
    for token in tokens:
        if result and result[-1].kind in OPERAND_END_KINDS and token.kind in OPERAND_START_KINDS:
            result.append(Token(CONCAT, "."))
        result.append(token)
    return result


# ---------------------------------------------------------------------------
# Stage 4: postfix conversion (Shunting-Yard)
# ---------------------------------------------------------------------------

def to_postfix(tokens: list[Token]) -> list[Token]:
    """
    Convert infix tokens (with explicit CONCAT) to postfix using Shunting-Yard.

    - Operands go straight to the output.
    - Postfix unary operators (* + ?) also go straight to the output: they
      already follow their operand and bind tighter than anything else.
    - A binary operator first pops operators of greater or equal precedence
      (this makes union and concatenation left-associative), then is pushed.
    - '(' is pushed; ')' pops operators until the matching '('.
    """
    output = []
    stack = []
    for token in tokens:
        if token.is_operand or token.kind in UNARY_KINDS:
            output.append(token)
        elif token.kind in BINARY_KINDS:
            while (
                stack
                and stack[-1].kind in BINARY_KINDS
                and BINARY_PRECEDENCE[stack[-1].kind] >= BINARY_PRECEDENCE[token.kind]
            ):
                output.append(stack.pop())
            stack.append(token)
        elif token.kind == LEFT_PAREN:
            stack.append(token)
        elif token.kind == RIGHT_PAREN:
            while stack[-1].kind != LEFT_PAREN:
                output.append(stack.pop())
            stack.pop()  # discard the '('

    while stack:
        output.append(stack.pop())
    return output


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def validate_regex(expression: str) -> list[Token]:
    """Tokenize and check the expression; return its tokens or raise RegexSyntaxError."""
    tokens = tokenize(expression)
    check_syntax(tokens)
    return tokens


def parse_regex(expression: str) -> ParsedRegex:
    """Parse a regular expression into postfix tokens and its alphabet."""
    tokens = validate_regex(expression)
    infix = insert_concatenation(tokens)
    postfix = to_postfix(infix)
    alphabet = frozenset(token.value for token in tokens if token.kind == LITERAL)
    return ParsedRegex(
        original=expression,
        infix=tuple(infix),
        postfix=tuple(postfix),
        alphabet=alphabet,
    )
