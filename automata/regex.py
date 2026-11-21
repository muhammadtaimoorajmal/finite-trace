"""Step 1: check the regular expression and convert it to postfix.

Textbook notation:  +  union (OR),  *  Kleene star,  writing side by side = concatenation.
Precedence (high to low):  *   then concatenation   then +
"""

PROJECT_RE = "(b + bbb + bb)* cc + ad + bbd"
LANGUAGE = "b*cc ∪ {ad, bbd}"  # the set of strings our RE describes


class RegexError(ValueError):
    """The input is not a well-formed regular expression."""


class NotProjectRegex(ValueError):
    """The input is valid, but it is not the Project 29 regular expression."""


def tokenize(text):
    """Return (character, position) pairs, skipping spaces. Positions start at 1."""
    tokens = []
    for pos, ch in enumerate(text, start=1):
        if ch.isspace():
            continue
        if ch not in "+*()" and not (ch.isascii() and ch.isalnum()):
            raise RegexError(f"Invalid symbol '{ch}' at position {pos}. Allowed: letters, digits, + * ( )")
        tokens.append((ch, pos))
    return tokens


def check_syntax(text):
    """Raise RegexError with a clear message if the expression is malformed."""
    if not text.strip():
        raise RegexError("Please enter a regular expression.")
    open_parens = []        # positions of '(' not closed yet
    prev, prev_pos = None, 0  # the previous token
    for ch, pos in tokenize(text):
        if ch == "(":
            open_parens.append(pos)
        elif ch == ")":
            if not open_parens:
                raise RegexError(f"Unmatched closing parenthesis at position {pos}.")
            if prev == "(":
                raise RegexError(f"Empty parentheses '()' at position {prev_pos}.")
            if prev == "+":
                raise RegexError(f"'+' at position {prev_pos} has no right-hand side.")
            open_parens.pop()
        elif ch == "+":
            if prev == "+":
                raise RegexError(f"Two operators in a row ('++') at position {pos}.")
            if prev in (None, "("):
                raise RegexError(f"'+' at position {pos} has no left-hand side.")
        elif ch == "*" and prev in (None, "(", "+"):
            raise RegexError(f"'*' at position {pos} has nothing to repeat.")
        prev, prev_pos = ch, pos
    if prev == "+":
        raise RegexError(f"'+' at position {prev_pos} (end of expression) has no right-hand side.")
    if open_parens:
        raise RegexError(f"Missing closing parenthesis for '(' at position {open_parens[-1]}.")


def validate(text):
    """Accept only the Project 29 RE (spaces ignored). Raise RegexError or NotProjectRegex otherwise."""
    check_syntax(text)
    if "".join(text.split()) != "".join(PROJECT_RE.split()):
        raise NotProjectRegex(
            f"'{text.strip()}' is a valid regular expression, but this machine is built only for "
            f"Project 29: {PROJECT_RE}"
        )


def to_postfix(text):
    """Convert the RE to postfix with the shunting-yard algorithm. '.' = concatenation."""
    # 1. Make concatenation explicit: insert '.' between "ab", "a(", ")a", ")(", "*a", "*(".
    infix = []
    for ch, _ in tokenize(text):
        if infix and infix[-1] not in "+(" and ch not in "+*)":
            infix.append(".")
        infix.append(ch)

    # 2. Shunting-yard: operands go straight to the output, operators wait on a stack.
    precedence = {"+": 1, ".": 2}
    output, stack = [], []
    for ch in infix:
        if ch == "(":
            stack.append(ch)
        elif ch == ")":
            while stack[-1] != "(":
                output.append(stack.pop())
            stack.pop()  # drop the '('
        elif ch == "*":
            output.append(ch)  # unary postfix operator with the highest precedence
        elif ch in precedence:
            while stack and stack[-1] != "(" and precedence[stack[-1]] >= precedence[ch]:
                output.append(stack.pop())
            stack.append(ch)
        else:
            output.append(ch)  # a symbol
    while stack:
        output.append(stack.pop())
    return output
