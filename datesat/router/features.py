# Copied from DateSATBench: the helpers, features_for and FEATURE_GROUPS of
# analysis/features/extract_features.py. The router's model is trained on features
# computed by DateSATBench's copy, so keep the two in step: change this code only by
# copying the DateSATBench version over it again.

"""
The router's features: static counts over a constraint's text, one dict per constraint.
features_for(entry, corpus) also returns the id, corpus and label_ fields DateSATBench
writes; the router reads only the names in FEATURES.
"""

from itertools import combinations

from .parser import (
    BinOp, BoolLit, DateAdd, DateCtor, Field, IntLit, PeriodConst, UnOp, Var,
    COMPARISONS, ORDERING,
    canonical, date_chain_base, date_chain_len, flatten, is_comparison,
    is_connective, is_ground_date, parse_constraint, parse_declarations,
    to_nnf, walk,
)


# --------------------------------------------------------------------------
# structural helpers
# --------------------------------------------------------------------------

def top_level_conjuncts(trees):
    """The constraint list is one conjunction; split it, and split on `&&` too."""
    out = []
    for t in trees:
        out.extend(flatten(t, "&&"))
    return out


def pinned_variables(conjuncts, sorts):
    """Variables fixed by an unconditional top-level equality, closed transitively."""
    pinned = set()
    changed = True
    while changed:
        changed = False
        for c in conjuncts:
            if not (isinstance(c, BinOp) and c.op == "=="):
                continue
            for lhs, rhs in ((c.lhs, c.rhs), (c.rhs, c.lhs)):
                if not (isinstance(lhs, Var) and lhs.name in sorts):
                    continue
                if lhs.name in pinned:
                    continue
                if rhs_is_determined(rhs, pinned):
                    pinned.add(lhs.name)
                    changed = True
    return pinned


def rhs_is_determined(n, pinned):
    """True if this expression evaluates to a fixed value given `pinned`."""
    if isinstance(n, (IntLit, BoolLit, PeriodConst)):
        return True
    if isinstance(n, Var):
        return n.name in pinned
    if isinstance(n, DateCtor):
        return all(rhs_is_determined(c, pinned) for c in (n.y, n.m, n.d))
    if isinstance(n, DateAdd):
        return rhs_is_determined(n.base, pinned)
    if isinstance(n, Field):
        return rhs_is_determined(n.base, pinned)
    if isinstance(n, BinOp):
        return rhs_is_determined(n.lhs, pinned) and rhs_is_determined(n.rhs, pinned)
    if isinstance(n, UnOp):
        return rhs_is_determined(n.operand, pinned)
    return False


def atoms_with_implication_flag(tree):
    """Yield (atom, under_impl) where under_impl means an `->` sits above the atom.

    Both sides of the implication count: the antecedent as well as the consequent.
    """
    def rec(n, under_impl):
        if is_comparison(n) or isinstance(n, (Var, BoolLit)) and n.sort == "bool":
            yield n, under_impl
            return
        if isinstance(n, BinOp) and n.op == "->":
            yield from rec(n.lhs, True)
            yield from rec(n.rhs, True)
            return
        if isinstance(n, BinOp) and n.op in ("&&", "||"):
            yield from rec(n.lhs, under_impl)
            yield from rec(n.rhs, under_impl)
            return
        if isinstance(n, UnOp) and n.op == "!":
            yield from rec(n.operand, under_impl)
            return
        if is_comparison(n):
            yield n, under_impl
    yield from rec(tree, False)


def is_leap_year(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def nnf_depth_and_polarity(tree):
    """Max connective depth to an atom, and the count of odd-polarity orderings.

    A flat chain of one connective is one level: `a || b || c` has depth 1, and a
    level is added only where the connective alternates (`&&` under `||` or vice versa).
    """
    nnf = to_nnf(tree)
    max_depth = 0
    neg_ordering = 0
    total_ordering = 0

    def rec(n, depth, negated, parent_op=None):
        nonlocal max_depth, neg_ordering, total_ordering
        if isinstance(n, UnOp) and n.op == "!":
            rec(n.operand, depth, not negated, parent_op)
            return
        if isinstance(n, BinOp) and n.op in ("&&", "||"):
            d = depth if n.op == parent_op else depth + 1
            rec(n.lhs, d, negated, n.op)
            rec(n.rhs, d, negated, n.op)
            return
        max_depth = max(max_depth, depth)
        if isinstance(n, BinOp) and n.op in ORDERING:
            total_ordering += 1
            if negated:
                neg_ordering += 1

    rec(nnf, 0, False)
    return max_depth, neg_ordering, total_ordering


def atom_variables(atom, sorts):
    return {n.name for n in walk(atom) if isinstance(n, Var) and n.name in sorts}


# --------------------------------------------------------------------------
# feature extraction
# --------------------------------------------------------------------------

def features_for(entry, corpus):
    sorts = parse_declarations(entry["declarations"])
    trees = [parse_constraint(s, sorts) for s in entry["constraints"]]
    conjuncts = top_level_conjuncts(trees)
    f = {"id": entry.get("id", ""), "corpus": corpus}

    # ---- search space -------------------------------------------------
    declared = {"date": [], "int": [], "bool": []}
    for name, s in sorts.items():
        if s in declared:
            declared[s].append(name)
    pinned = pinned_variables(conjuncts, sorts)
    n_vars = len(sorts)

    f["n_free_date_vars"] = len([v for v in declared["date"] if v not in pinned])
    f["n_free_int_vars"] = len([v for v in declared["int"] if v not in pinned])
    f["n_free_bool_vars"] = len([v for v in declared["bool"] if v not in pinned])
    f["pinned_var_frac"] = (len(pinned) / n_vars) if n_vars else 0.0
    for s in ("date", "int", "bool"):
        n_s = len(declared[s])
        n_pinned_s = sum(1 for v in declared[s] if v in pinned)
        f[f"pinned_{s}_frac"] = (n_pinned_s / n_s) if n_s else 0.0

    date_exprs = {
        canonical(n) for t in trees for n in walk(t)
        if n.sort == "date" and not isinstance(n, Var)
    }
    f["n_date_subexprs"] = len(date_exprs | set(declared["date"]))

    # ---- boolean skeleton ---------------------------------------------
    all_atoms = []
    under_impl = 0
    for t in trees:
        for atom, g in atoms_with_implication_flag(t):
            all_atoms.append(atom)
            under_impl += int(g)
    n_atoms = len(all_atoms)
    f["n_atoms"] = n_atoms

    date_cmps = [a for a in all_atoms if is_comparison(a) and a.lhs.sort == "date"]
    int_cmps = [a for a in all_atoms if is_comparison(a) and a.lhs.sort == "int"]
    all_cmps = [a for a in all_atoms if is_comparison(a)]
    f["n_date_comparisons"] = len(date_cmps)
    f["n_int_comparisons"] = len(int_cmps)
    f["ordering_cmp_frac"] = (
        sum(1 for a in all_cmps if a.op in ORDERING) / len(all_cmps)
    ) if all_cmps else 0.0

    n_or = sum(1 for t in trees for n in walk(t) if isinstance(n, BinOp) and n.op == "||")
    n_impl = sum(1 for t in trees for n in walk(t) if isinstance(n, BinOp) and n.op == "->")
    f["n_case_splits"] = n_or + n_impl

    widths = [len(flatten(n, "||")) for t in trees for n in walk(t)
              if isinstance(n, BinOp) and n.op == "||"]
    f["max_disjunction_width"] = max(widths) if widths else 1

    depths, neg_ord, tot_ord = [], 0, 0
    for t in trees:
        d, no, to = nnf_depth_and_polarity(t)
        depths.append(d)
        neg_ord += no
        tot_ord += to
    f["bool_alternation_depth"] = max(depths) if depths else 0
    f["neg_ordering_frac"] = (neg_ord / tot_ord) if tot_ord else 0.0

    f["implication_atom_frac"] = (under_impl / n_atoms) if n_atoms else 0.0
    # In NNF `a -> b` is `!a || b` and `!(a && b)` is `!a || !b`, so both count as splits.
    f["n_unit_constraints"] = sum(
        1 for t in trees for c in flatten(to_nnf(t), "&&")
        if not any(isinstance(n, BinOp) and n.op == "||" for n in walk(c))
    )

    # ---- date arithmetic ----------------------------------------------
    all_adds = [n for t in trees for n in walk(t) if isinstance(n, DateAdd)]
    ground_adds = [n for n in all_adds if is_ground_date(n)]
    live = [n for n in all_adds if not is_ground_date(n)]

    f["n_date_period_ops"] = len(live)
    f["ground_arith_frac"] = (len(ground_adds) / len(all_adds)) if all_adds else 0.0

    f["max_abs_years"] = max((abs(n.period.ny) for n in live), default=0)
    f["max_abs_months"] = max((abs(n.period.nm) for n in live), default=0)
    f["max_abs_days"] = max((abs(n.period.nd) for n in live), default=0)

    mixed = sum(1 for n in live if n.period.months != 0 and n.period.nd != 0)
    f["mixed_frac"] = (mixed / len(live)) if live else 0.0

    f["max_date_chain_len"] = max(
        (date_chain_len(n) for t in trees for n in walk(t) if n.sort == "date"),
        default=0,
    )

    # ---- component extraction ------------------------------------------
    fields = [n for t in trees for n in walk(t) if isinstance(n, Field)]
    f["n_dot_year"] = sum(1 for n in fields if n.fname == "year")
    f["n_dot_month"] = sum(1 for n in fields if n.fname == "month")
    f["n_dot_day"] = sum(1 for n in fields if n.fname == "day")
    denom = len(fields) + len(date_cmps)
    f["property_access_frac"] = (len(fields) / denom) if denom else 0.0

    f["n_symbolic_date_ctors"] = sum(
        1 for t in trees for n in walk(t)
        if isinstance(n, DateCtor) and not all(isinstance(c, IntLit) for c in (n.y, n.m, n.d))
    )

    # ---- calendar corners ----------------------------------------------
    lit_ctors = [
        n for t in trees for n in walk(t)
        if isinstance(n, DateCtor) and all(isinstance(c, IntLit) for c in (n.y, n.m, n.d))
    ]
    f["uses_feb29"] = int(any(n.m.value == 2 and n.d.value == 29 for n in lit_ctors))
    f["uses_leap_year"] = int(any(is_leap_year(n.y.value) for n in lit_ctors))
    # Day 28 or later: where month steps clamp and day steps roll over into the next month.
    f["near_month_end_frac"] = (
        sum(1 for n in lit_ctors if n.d.value >= 28) / len(lit_ctors)
    ) if lit_ctors else 0.0

    # ---- variable coupling ----------------------------------------------
    edges = set()
    for a in all_atoms:
        vs = sorted(atom_variables(a, sorts))
        for u, v in combinations(vs, 2):
            edges.add((u, v))

    parent = {v: v for v in sorts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in edges:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv

    if n_vars:
        comps = {}
        for v in sorts:
            comps.setdefault(find(v), []).append(v)
        f["n_components"] = len(comps)
        f["largest_component_frac"] = max(len(c) for c in comps.values()) / n_vars
        possible = n_vars * (n_vars - 1) / 2
        f["graph_density"] = (len(edges) / possible) if possible else 0.0
    else:
        f["n_components"] = 0
        f["largest_component_frac"] = 0.0
        f["graph_density"] = 0.0

    f["mixed_sort_coupling"] = sum(
        1 for a in all_atoms
        if any(isinstance(n, Field) for n in walk(a))
        and any(isinstance(n, Var) and sorts.get(n.name) == "int" for n in walk(a))
    )

    # ---- labels (solver output, NOT features) ---------------------------
    f["label_execution_time"] = entry.get("execution_time")
    entry_id = str(entry.get("id", ""))
    f["label_status"] = entry_id.split("-")[1] if entry_id.startswith("grammar-") else None

    return f


FEATURE_GROUPS = [
    ("Search space", [
        "n_free_date_vars", "n_free_int_vars", "n_free_bool_vars", "pinned_var_frac",
        "pinned_date_frac", "pinned_int_frac", "pinned_bool_frac", "n_date_subexprs"]),
    ("Boolean skeleton", [
        "n_atoms", "n_date_comparisons", "n_int_comparisons", "ordering_cmp_frac",
        "n_case_splits", "max_disjunction_width", "bool_alternation_depth",
        "implication_atom_frac", "neg_ordering_frac", "n_unit_constraints"]),
    ("Date arithmetic", [
        "n_date_period_ops", "ground_arith_frac", "max_abs_years", "max_abs_months",
        "max_abs_days", "mixed_frac", "max_date_chain_len"]),
    ("Component extraction", [
        "n_dot_year", "n_dot_month", "n_dot_day", "property_access_frac",
        "n_symbolic_date_ctors"]),
    ("Calendar corners", ["uses_feb29", "uses_leap_year", "near_month_end_frac"]),
    ("Variable coupling", [
        "n_components", "largest_component_frac", "graph_density", "mixed_sort_coupling"]),
]

FEATURES = [f for _, feats in FEATURE_GROUPS for f in feats]
