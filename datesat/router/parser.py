# Copied from DateSATBench: analysis/features/datesat_parser.py. The router's model is trained on
# features computed by DateSATBench's copy, so keep the two in step: change this file
# only by copying the DateSATBench version over it again.

"""
Parser and canonicaliser for the DateSAT constraint language.

Implements the grammar of Figure 6 in the DateSAT paper (Appendix A), with one
deliberate deviation: Figure 6 places `==`/`!=` at a LOWER precedence than `||`
and `&&`, which does not match the shipped datasets. For example

    d2.month == 2 && (d2.day == 28 || d2.day == 29)

can only mean `(d2.month == 2) && (...)`. This parser therefore binds all six
comparison operators tighter than `&&`, i.e. the conventional precedence:

    ->   (right associative, loosest)
    ||
    &&
    !
    == != < <= > >=
    + -
    *
    unary -, postfix .field, primary   (tightest)

Sorts (date / period / int / bool) are resolved bottom-up from the instance's
`declarations`, which is what disambiguates `a == b` between a date comparison,
an int comparison and a boolean equality.

Canonicalisation performed after parsing:
  * every period expression folds to a signed triple (ny, nm, nd) -- always
    possible, since Period takes only integer literals and `*` scales by one
  * a date expression rooted at an all-literal Date(...) is marked ground; its
    arithmetic folds and costs nothing under every encoding
  * `a -> b` rewrites to `!a || b` on demand for polarity/NNF analysis
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

DATE_FIELDS = ("year", "month", "day")


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------
# Tokeniser
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""
    \s+                        (?P<ws>)
  | ->                         (?P<implies>)
  | \|\|                       (?P<or>)
  | &&                         (?P<and>)
  | <=|>=|==|!=|<|>            (?P<cmp>)
  | [A-Za-z_][A-Za-z_0-9]*     (?P<ident>)
  | \d+                        (?P<int>)
  | [()+\-*,.!]                (?P<punct>)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str   # 'op' | 'ident' | 'int' | 'punct'
    text: str
    pos: int


def tokenize(src: str) -> List[Token]:
    out: List[Token] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if src.startswith("->", i):
            out.append(Token("op", "->", i)); i += 2; continue
        if src.startswith("||", i):
            out.append(Token("op", "||", i)); i += 2; continue
        if src.startswith("&&", i):
            out.append(Token("op", "&&", i)); i += 2; continue
        two = src[i:i + 2]
        if two in ("<=", ">=", "==", "!="):
            out.append(Token("op", two, i)); i += 2; continue
        if c in "<>":
            out.append(Token("op", c, i)); i += 1; continue
        if c.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            out.append(Token("int", src[i:j], i)); i = j; continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            out.append(Token("ident", src[i:j], i)); i = j; continue
        if c in "()+-*,.!":
            out.append(Token("punct", c, i)); i += 1; continue
        raise ParseError(f"unexpected character {c!r} at {i} in {src!r}")
    return out


# --------------------------------------------------------------------------
# AST
# --------------------------------------------------------------------------

@dataclass
class Node:
    sort: str = "unknown"          # 'date' | 'period' | 'int' | 'bool'


@dataclass
class Var(Node):
    name: str = ""


@dataclass
class IntLit(Node):
    value: int = 0


@dataclass
class BoolLit(Node):
    value: bool = True


@dataclass
class PeriodConst(Node):
    """A fully folded period: ny years, nm months, nd days."""
    ny: int = 0
    nm: int = 0
    nd: int = 0

    @property
    def months(self) -> int:
        return 12 * self.ny + self.nm


@dataclass
class DateCtor(Node):
    y: Node = None
    m: Node = None
    d: Node = None


@dataclass
class DateAdd(Node):
    """base +/- period, with the period already folded and signed."""
    base: Node = None
    period: PeriodConst = None


@dataclass
class Field(Node):
    """date_expr . year|month|day"""
    base: Node = None
    fname: str = ""


@dataclass
class BinOp(Node):
    op: str = ""
    lhs: Node = None
    rhs: Node = None


@dataclass
class UnOp(Node):
    op: str = ""
    operand: Node = None


COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")
ORDERING = ("<", "<=", ">", ">=")


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: List[Token], sorts: dict, src: str):
        self.toks = tokens
        self.i = 0
        self.sorts = sorts      # variable name -> declared sort
        self.src = src

    # -- token helpers ----------------------------------------------------
    def peek(self) -> Optional[Token]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def at(self, text: str) -> bool:
        t = self.peek()
        return t is not None and t.text == text

    def at_any(self, texts) -> bool:
        t = self.peek()
        return t is not None and t.text in texts

    def eat(self, text: str) -> Token:
        t = self.peek()
        if t is None or t.text != text:
            got = "EOF" if t is None else repr(t.text)
            raise ParseError(f"expected {text!r}, got {got} in {self.src!r}")
        self.i += 1
        return t

    def advance(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    # -- entry ------------------------------------------------------------
    def parse(self) -> Node:
        e = self.parse_implication()
        if self.peek() is not None:
            raise ParseError(f"trailing input at {self.peek().text!r} in {self.src!r}")
        return e

    # -- precedence levels ------------------------------------------------
    def parse_implication(self) -> Node:
        lhs = self.parse_or()
        if self.at("->"):
            self.advance()
            rhs = self.parse_implication()           # right associative
            return BinOp("bool", "->", lhs, rhs)
        return lhs

    def parse_or(self) -> Node:
        lhs = self.parse_and()
        while self.at("||"):
            self.advance()
            lhs = BinOp("bool", "||", lhs, self.parse_and())
        return lhs

    def parse_and(self) -> Node:
        lhs = self.parse_not()
        while self.at("&&"):
            self.advance()
            lhs = BinOp("bool", "&&", lhs, self.parse_not())
        return lhs

    def parse_not(self) -> Node:
        if self.at("!"):
            self.advance()
            return UnOp("bool", "!", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        lhs = self.parse_additive()
        if self.at_any(COMPARISONS):
            op = self.advance().text
            rhs = self.parse_additive()
            return BinOp("bool", op, lhs, rhs)
        return lhs

    def parse_additive(self) -> Node:
        lhs = self.parse_multiplicative()
        while self.at_any(("+", "-")):
            op = self.advance().text
            rhs = self.parse_multiplicative()
            lhs = self.combine_additive(op, lhs, rhs)
        return lhs

    def parse_multiplicative(self) -> Node:
        lhs = self.parse_unary()
        while self.at("*"):
            self.advance()
            rhs = self.parse_unary()
            lhs = self.combine_mul(lhs, rhs)
        return lhs

    def parse_unary(self) -> Node:
        if self.at("-"):
            self.advance()
            operand = self.parse_unary()
            if isinstance(operand, IntLit):
                return IntLit("int", -operand.value)
            if isinstance(operand, PeriodConst):
                return PeriodConst("period", -operand.ny, -operand.nm, -operand.nd)
            return UnOp("int", "neg", operand)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        e = self.parse_primary()
        while self.at("."):
            self.advance()
            t = self.peek()
            if t is None or t.text not in DATE_FIELDS:
                raise ParseError(f"bad field access in {self.src!r}")
            self.advance()
            e = Field("int", e, t.text)
        return e

    def parse_primary(self) -> Node:
        t = self.peek()
        if t is None:
            raise ParseError(f"unexpected end of input in {self.src!r}")

        if t.text == "(":
            self.advance()
            e = self.parse_implication()
            self.eat(")")
            return e

        if t.kind == "int":
            self.advance()
            return IntLit("int", int(t.text))

        if t.kind == "ident":
            name = t.text
            if name == "Date":
                return self.parse_date_ctor()
            if name == "Period":
                return self.parse_period_ctor()
            if name in ("True", "False"):
                self.advance()
                return BoolLit("bool", name == "True")
            self.advance()
            return Var(self.sorts.get(name, "unknown"), name)

        raise ParseError(f"unexpected token {t.text!r} in {self.src!r}")

    def parse_date_ctor(self) -> Node:
        self.eat("Date"); self.eat("(")
        y = self.parse_additive(); self.eat(",")
        m = self.parse_additive(); self.eat(",")
        d = self.parse_additive(); self.eat(")")
        return DateCtor("date", y, m, d)

    def parse_period_ctor(self) -> Node:
        self.eat("Period"); self.eat("(")
        ny = self.parse_additive(); self.eat(",")
        nm = self.parse_additive(); self.eat(",")
        nd = self.parse_additive(); self.eat(")")
        for c in (ny, nm, nd):
            if not isinstance(c, IntLit):
                raise ParseError(f"Period with non-literal component in {self.src!r}")
        return PeriodConst("period", ny.value, nm.value, nd.value)

    # -- sort-directed combination ---------------------------------------
    def combine_additive(self, op: str, lhs: Node, rhs: Node) -> Node:
        lp, rp = lhs.sort == "period", rhs.sort == "period"
        sign = 1 if op == "+" else -1

        # period +/- period  ->  folds componentwise
        if lp and rp and isinstance(lhs, PeriodConst) and isinstance(rhs, PeriodConst):
            return PeriodConst(
                "period",
                lhs.ny + sign * rhs.ny,
                lhs.nm + sign * rhs.nm,
                lhs.nd + sign * rhs.nd,
            )

        # date +/- period  ->  a DateAdd link
        if lhs.sort == "date" and rp:
            p = rhs if sign == 1 else PeriodConst("period", -rhs.ny, -rhs.nm, -rhs.nd)
            return DateAdd("date", lhs, p)

        # otherwise integer arithmetic
        return BinOp("int", op, lhs, rhs)

    def combine_mul(self, lhs: Node, rhs: Node) -> Node:
        # INTEGER * period  or  period * INTEGER  ->  scales the triple
        if isinstance(lhs, PeriodConst) and isinstance(rhs, IntLit):
            k = rhs.value
            return PeriodConst("period", lhs.ny * k, lhs.nm * k, lhs.nd * k)
        if isinstance(lhs, IntLit) and isinstance(rhs, PeriodConst):
            k = lhs.value
            return PeriodConst("period", rhs.ny * k, rhs.nm * k, rhs.nd * k)
        return BinOp("int", "*", lhs, rhs)


def parse_constraint(src: str, sorts: dict) -> Node:
    return Parser(tokenize(src), sorts, src).parse()


def parse_declarations(decls: List[str]) -> dict:
    """['x: date', 'n: int'] -> {'x': 'date', 'n': 'int'}"""
    sorts = {}
    for d in decls:
        name, _, sort = d.partition(":")
        sorts[name.strip()] = sort.strip()
    return sorts


# --------------------------------------------------------------------------
# AST utilities
# --------------------------------------------------------------------------

def children(n: Node) -> List[Node]:
    if isinstance(n, BinOp):
        return [n.lhs, n.rhs]
    if isinstance(n, UnOp):
        return [n.operand]
    if isinstance(n, Field):
        return [n.base]
    if isinstance(n, DateAdd):
        return [n.base]
    if isinstance(n, DateCtor):
        return [n.y, n.m, n.d]
    return []


def walk(n: Node):
    yield n
    for c in children(n):
        yield from walk(c)


def is_comparison(n: Node) -> bool:
    return isinstance(n, BinOp) and n.op in COMPARISONS


def is_connective(n: Node) -> bool:
    return (isinstance(n, BinOp) and n.op in ("&&", "||", "->")) or (
        isinstance(n, UnOp) and n.op == "!"
    )


def is_ground_date(n: Node) -> bool:
    """True if this date expression folds to a concrete calendar date."""
    if isinstance(n, DateCtor):
        return all(isinstance(c, IntLit) for c in (n.y, n.m, n.d))
    if isinstance(n, DateAdd):
        return is_ground_date(n.base)
    return False


def date_chain_base(n: Node) -> Node:
    """Follow a DateAdd chain down to whatever it is rooted at."""
    while isinstance(n, DateAdd):
        n = n.base
    return n


def date_chain_len(n: Node) -> int:
    k = 0
    while isinstance(n, DateAdd):
        k += 1
        n = n.base
    return k


def canonical(n: Node) -> str:
    """A stable textual form, used to count DISTINCT date subexpressions."""
    if isinstance(n, Var):
        return n.name
    if isinstance(n, IntLit):
        return str(n.value)
    if isinstance(n, BoolLit):
        return "True" if n.value else "False"
    if isinstance(n, PeriodConst):
        return f"P({n.ny},{n.nm},{n.nd})"
    if isinstance(n, DateCtor):
        return f"D({canonical(n.y)},{canonical(n.m)},{canonical(n.d)})"
    if isinstance(n, DateAdd):
        p = n.period
        return f"({canonical(n.base)}+P({p.ny},{p.nm},{p.nd}))"
    if isinstance(n, Field):
        return f"{canonical(n.base)}.{n.fname}"
    if isinstance(n, BinOp):
        return f"({canonical(n.lhs)}{n.op}{canonical(n.rhs)})"
    if isinstance(n, UnOp):
        return f"({n.op}{canonical(n.operand)})"
    return "?"


def to_nnf(n: Node, negated: bool = False) -> Node:
    """Push negations to the leaves, expanding `a -> b` to `!a || b`."""
    if isinstance(n, UnOp) and n.op == "!":
        return to_nnf(n.operand, not negated)
    if isinstance(n, BinOp) and n.op == "->":
        expanded = BinOp("bool", "||", UnOp("bool", "!", n.lhs), n.rhs)
        return to_nnf(expanded, negated)
    if isinstance(n, BinOp) and n.op in ("&&", "||"):
        op = n.op
        if negated:
            op = "||" if n.op == "&&" else "&&"
        return BinOp("bool", op, to_nnf(n.lhs, negated), to_nnf(n.rhs, negated))
    if negated:
        return UnOp("bool", "!", n)
    return n


def flatten(n: Node, op: str) -> List[Node]:
    """Flatten a left-nested chain of one connective into its arms."""
    if isinstance(n, BinOp) and n.op == op:
        return flatten(n.lhs, op) + flatten(n.rhs, op)
    return [n]
