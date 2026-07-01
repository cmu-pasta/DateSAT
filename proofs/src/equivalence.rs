use vstd::prelude::*;
use crate::*;
use crate::hybrid_ymd;
use crate::hybrid_epoch;

verus! {

    // ── Well-formedness ───────────────────────────────────────────────────

    pub proof fn lemma_date_wf_implies_valid(e: DateExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env).is_valid(),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {},
            DateExpr::Var(id) => {},
            DateExpr::Add(base, period) => {
                lemma_date_wf_implies_valid(*base, env);
                theorem_date_add_period_preserves_validity(
                    base.eval::<SimpleDate>(env),
                    period.eval(),
                );
            },
        }
    }

    // ── EpochDelta equivalence proofs ───────────────────────────────────

    pub proof fn lemma_date_expr_epoch_delta_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures ed_congruent(e.eval::<SimpleDate>(env), e.eval::<EpochDelta>(env)),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {
                theorem_epoch_delta_from_ymd_congruent(y, m, d);
            },
            DateExpr::Var(id) => {
                let sd = env.date_vars[id];
                theorem_epoch_delta_from_ymd_congruent(sd.year(), sd.month(), sd.day());
            },
            DateExpr::Add(base, period) => {
                lemma_date_expr_epoch_delta_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                theorem_epoch_delta_add_period_preserves_congruence(
                    base.eval::<SimpleDate>(env),
                    base.eval::<EpochDelta>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_epoch_delta_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<EpochDelta>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_epoch_delta_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_epoch_delta_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_epoch_delta_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Add(a, b) => {
                lemma_int_expr_epoch_delta_equiv(*a, env);
                lemma_int_expr_epoch_delta_equiv(*b, env);
            },
            IntExpr::Sub(a, b) => {
                lemma_int_expr_epoch_delta_equiv(*a, env);
                lemma_int_expr_epoch_delta_equiv(*b, env);
            },
            IntExpr::Mul(a, _) => {
                lemma_int_expr_epoch_delta_equiv(*a, env);
            },
        }
    }

    pub proof fn lemma_bool_expr_epoch_delta_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<EpochDelta>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_epoch_delta_equiv(*a, env);
                lemma_bool_expr_epoch_delta_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_epoch_delta_equiv(*a, env);
                lemma_bool_expr_epoch_delta_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_epoch_delta_equiv(*a, env);
            },
            BoolExpr::Implies(a, b) => {
                lemma_bool_expr_epoch_delta_equiv(*a, env);
                lemma_bool_expr_epoch_delta_equiv(*b, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::Var(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_epoch_delta_congruent(*a, env);
                lemma_date_expr_epoch_delta_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_epoch_delta_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<EpochDelta>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<EpochDelta>(env),
                );
            },
            BoolExpr::DateEq(a, b) => {
                lemma_date_expr_epoch_delta_congruent(*a, env);
                lemma_date_expr_epoch_delta_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_epoch_delta_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<EpochDelta>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<EpochDelta>(env),
                );
            },
            BoolExpr::IntLt(a, b) => {
                lemma_int_expr_epoch_delta_equiv(*a, env);
                lemma_int_expr_epoch_delta_equiv(*b, env);
            },
            BoolExpr::IntEq(a, b) => {
                lemma_int_expr_epoch_delta_equiv(*a, env);
                lemma_int_expr_epoch_delta_equiv(*b, env);
            },
        }
    }

    pub proof fn theorem_ast_epoch_delta_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(), ast.is_properly_closed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<EpochDelta>(env),
    {
        lemma_bool_expr_epoch_delta_equiv(ast.root, env);
    }


    // ── Hybrid (YMD-initial) equivalence proofs ─────────────────────────

    pub proof fn lemma_date_expr_hybrid_ymd_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures hybrid_ymd::hybrid_congruent(e.eval::<SimpleDate>(env), e.eval::<hybrid_ymd::Hybrid>(env)),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {
                hybrid_ymd::theorem_hybrid_from_ymd_congruent(y, m, d);
            },
            DateExpr::Var(id) => {
                let sd = env.date_vars[id];
                hybrid_ymd::theorem_hybrid_from_ymd_congruent(sd.year(), sd.month(), sd.day());
            },
            DateExpr::Add(base, period) => {
                lemma_date_expr_hybrid_ymd_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                hybrid_ymd::theorem_hybrid_add_period_preserves_congruence(
                    base.eval::<SimpleDate>(env),
                    base.eval::<hybrid_ymd::Hybrid>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_hybrid_ymd_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<hybrid_ymd::Hybrid>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_hybrid_ymd_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_ymd::Hybrid>(env);
                hybrid_ymd::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_hybrid_ymd_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_ymd::Hybrid>(env);
                hybrid_ymd::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_hybrid_ymd_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_ymd::Hybrid>(env);
                hybrid_ymd::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Add(a, b) => {
                lemma_int_expr_hybrid_ymd_equiv(*a, env);
                lemma_int_expr_hybrid_ymd_equiv(*b, env);
            },
            IntExpr::Sub(a, b) => {
                lemma_int_expr_hybrid_ymd_equiv(*a, env);
                lemma_int_expr_hybrid_ymd_equiv(*b, env);
            },
            IntExpr::Mul(a, _) => {
                lemma_int_expr_hybrid_ymd_equiv(*a, env);
            },
        }
    }

    pub proof fn lemma_bool_expr_hybrid_ymd_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<hybrid_ymd::Hybrid>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_hybrid_ymd_equiv(*a, env);
                lemma_bool_expr_hybrid_ymd_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_hybrid_ymd_equiv(*a, env);
                lemma_bool_expr_hybrid_ymd_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_hybrid_ymd_equiv(*a, env);
            },
            BoolExpr::Implies(a, b) => {
                lemma_bool_expr_hybrid_ymd_equiv(*a, env);
                lemma_bool_expr_hybrid_ymd_equiv(*b, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::Var(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_hybrid_ymd_congruent(*a, env);
                lemma_date_expr_hybrid_ymd_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                hybrid_ymd::theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<hybrid_ymd::Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<hybrid_ymd::Hybrid>(env),
                );
            },
            BoolExpr::DateEq(a, b) => {
                lemma_date_expr_hybrid_ymd_congruent(*a, env);
                lemma_date_expr_hybrid_ymd_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                hybrid_ymd::theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<hybrid_ymd::Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<hybrid_ymd::Hybrid>(env),
                );
            },
            BoolExpr::IntLt(a, b) => {
                lemma_int_expr_hybrid_ymd_equiv(*a, env);
                lemma_int_expr_hybrid_ymd_equiv(*b, env);
            },
            BoolExpr::IntEq(a, b) => {
                lemma_int_expr_hybrid_ymd_equiv(*a, env);
                lemma_int_expr_hybrid_ymd_equiv(*b, env);
            },
        }
    }

    pub proof fn theorem_ast_hybrid_ymd_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(), ast.is_properly_closed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<hybrid_ymd::Hybrid>(env),
    {
        lemma_bool_expr_hybrid_ymd_equiv(ast.root, env);
    }


    // ── Hybrid (epoch-initial) equivalence proofs ───────────────────────

    pub proof fn lemma_date_expr_hybrid_epoch_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures hybrid_epoch::hybrid_congruent(e.eval::<SimpleDate>(env), e.eval::<hybrid_epoch::Hybrid>(env)),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {
                hybrid_epoch::theorem_hybrid_from_ymd_congruent(y, m, d);
            },
            DateExpr::Var(id) => {
                let sd = env.date_vars[id];
                hybrid_epoch::theorem_hybrid_from_ymd_congruent(sd.year(), sd.month(), sd.day());
            },
            DateExpr::Add(base, period) => {
                lemma_date_expr_hybrid_epoch_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                hybrid_epoch::theorem_hybrid_add_period_preserves_congruence(
                    base.eval::<SimpleDate>(env),
                    base.eval::<hybrid_epoch::Hybrid>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_hybrid_epoch_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<hybrid_epoch::Hybrid>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_hybrid_epoch_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_epoch::Hybrid>(env);
                hybrid_epoch::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_hybrid_epoch_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_epoch::Hybrid>(env);
                hybrid_epoch::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_hybrid_epoch_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<hybrid_epoch::Hybrid>(env);
                hybrid_epoch::lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Add(a, b) => {
                lemma_int_expr_hybrid_epoch_equiv(*a, env);
                lemma_int_expr_hybrid_epoch_equiv(*b, env);
            },
            IntExpr::Sub(a, b) => {
                lemma_int_expr_hybrid_epoch_equiv(*a, env);
                lemma_int_expr_hybrid_epoch_equiv(*b, env);
            },
            IntExpr::Mul(a, _) => {
                lemma_int_expr_hybrid_epoch_equiv(*a, env);
            },
        }
    }

    pub proof fn lemma_bool_expr_hybrid_epoch_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<hybrid_epoch::Hybrid>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_hybrid_epoch_equiv(*a, env);
                lemma_bool_expr_hybrid_epoch_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_hybrid_epoch_equiv(*a, env);
                lemma_bool_expr_hybrid_epoch_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_hybrid_epoch_equiv(*a, env);
            },
            BoolExpr::Implies(a, b) => {
                lemma_bool_expr_hybrid_epoch_equiv(*a, env);
                lemma_bool_expr_hybrid_epoch_equiv(*b, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::Var(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_hybrid_epoch_congruent(*a, env);
                lemma_date_expr_hybrid_epoch_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                hybrid_epoch::theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<hybrid_epoch::Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<hybrid_epoch::Hybrid>(env),
                );
            },
            BoolExpr::DateEq(a, b) => {
                lemma_date_expr_hybrid_epoch_congruent(*a, env);
                lemma_date_expr_hybrid_epoch_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                hybrid_epoch::theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<hybrid_epoch::Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<hybrid_epoch::Hybrid>(env),
                );
            },
            BoolExpr::IntLt(a, b) => {
                lemma_int_expr_hybrid_epoch_equiv(*a, env);
                lemma_int_expr_hybrid_epoch_equiv(*b, env);
            },
            BoolExpr::IntEq(a, b) => {
                lemma_int_expr_hybrid_epoch_equiv(*a, env);
                lemma_int_expr_hybrid_epoch_equiv(*b, env);
            },
        }
    }

    pub proof fn theorem_ast_hybrid_epoch_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(), ast.is_properly_closed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<hybrid_epoch::Hybrid>(env),
    {
        lemma_bool_expr_hybrid_epoch_equiv(ast.root, env);
    }


    // ── AlphaBeta equivalence proofs ───────────────────────────────────

    pub proof fn lemma_date_expr_ab_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures ab_congruent(e.eval::<SimpleDate>(env), e.eval::<AlphaBeta>(env)),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {
                theorem_ab_from_ymd_congruent(y, m, d);
            },
            DateExpr::Var(id) => {
                let sd = env.date_vars[id];
                theorem_ab_from_ymd_congruent(sd.year(), sd.month(), sd.day());
            },
            DateExpr::Add(base, period) => {
                lemma_date_expr_ab_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                theorem_ab_congruent_add_period(
                    base.eval::<SimpleDate>(env),
                    base.eval::<AlphaBeta>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_ab_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<AlphaBeta>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_ab_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_ab_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_ab_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_ab_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_ab_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_ab_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Add(a, b) => {
                lemma_int_expr_ab_equiv(*a, env);
                lemma_int_expr_ab_equiv(*b, env);
            },
            IntExpr::Sub(a, b) => {
                lemma_int_expr_ab_equiv(*a, env);
                lemma_int_expr_ab_equiv(*b, env);
            },
            IntExpr::Mul(a, _) => {
                lemma_int_expr_ab_equiv(*a, env);
            },
        }
    }

    pub proof fn lemma_bool_expr_ab_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(), e.is_properly_closed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<AlphaBeta>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_ab_equiv(*a, env);
                lemma_bool_expr_ab_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_ab_equiv(*a, env);
                lemma_bool_expr_ab_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_ab_equiv(*a, env);
            },
            BoolExpr::Implies(a, b) => {
                lemma_bool_expr_ab_equiv(*a, env);
                lemma_bool_expr_ab_equiv(*b, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::Var(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_ab_congruent(*a, env);
                lemma_date_expr_ab_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_ab_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<AlphaBeta>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<AlphaBeta>(env),
                );
            },
            BoolExpr::DateEq(a, b) => {
                lemma_date_expr_ab_congruent(*a, env);
                lemma_date_expr_ab_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_ab_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<AlphaBeta>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<AlphaBeta>(env),
                );
            },
            BoolExpr::IntLt(a, b) => {
                lemma_int_expr_ab_equiv(*a, env);
                lemma_int_expr_ab_equiv(*b, env);
            },
            BoolExpr::IntEq(a, b) => {
                lemma_int_expr_ab_equiv(*a, env);
                lemma_int_expr_ab_equiv(*b, env);
            },
        }
    }

    pub proof fn theorem_ast_ab_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(), ast.is_properly_closed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<AlphaBeta>(env),
    {
        lemma_bool_expr_ab_equiv(ast.root, env);
    }

    // ── Equisatisfiability theorems ─────────────────────────────────────

    pub proof fn theorem_ast_epoch_delta_equisat(ast: Ast)
        requires ast.is_well_formed(),
        ensures ast.is_sat::<SimpleDate>() == ast.is_sat::<EpochDelta>(),
    {
        if ast.is_sat::<SimpleDate>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<SimpleDate>(env);
            theorem_ast_epoch_delta_equiv(ast, env);
        }
        if ast.is_sat::<EpochDelta>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<EpochDelta>(env);
            theorem_ast_epoch_delta_equiv(ast, env);
        }
    }

    pub proof fn theorem_ast_hybrid_ymd_equisat(ast: Ast)
        requires ast.is_well_formed(),
        ensures ast.is_sat::<SimpleDate>() == ast.is_sat::<hybrid_ymd::Hybrid>(),
    {
        if ast.is_sat::<SimpleDate>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<SimpleDate>(env);
            theorem_ast_hybrid_ymd_equiv(ast, env);
        }
        if ast.is_sat::<hybrid_ymd::Hybrid>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<hybrid_ymd::Hybrid>(env);
            theorem_ast_hybrid_ymd_equiv(ast, env);
        }
    }

    pub proof fn theorem_ast_hybrid_epoch_equisat(ast: Ast)
        requires ast.is_well_formed(),
        ensures ast.is_sat::<SimpleDate>() == ast.is_sat::<hybrid_epoch::Hybrid>(),
    {
        if ast.is_sat::<SimpleDate>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<SimpleDate>(env);
            theorem_ast_hybrid_epoch_equiv(ast, env);
        }
        if ast.is_sat::<hybrid_epoch::Hybrid>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<hybrid_epoch::Hybrid>(env);
            theorem_ast_hybrid_epoch_equiv(ast, env);
        }
    }

    pub proof fn theorem_ast_ab_equisat(ast: Ast)
        requires ast.is_well_formed(),
        ensures ast.is_sat::<SimpleDate>() == ast.is_sat::<AlphaBeta>(),
    {
        if ast.is_sat::<SimpleDate>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<SimpleDate>(env);
            theorem_ast_ab_equiv(ast, env);
        }
        if ast.is_sat::<AlphaBeta>() {
            let env = choose|env: Environment| ast.is_properly_closed(env) && ast.eval::<AlphaBeta>(env);
            theorem_ast_ab_equiv(ast, env);
        }
    }

} // verus!
