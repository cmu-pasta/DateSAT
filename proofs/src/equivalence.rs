use vstd::prelude::*;
use crate::*;

verus! {

    // ── Well-formedness ───────────────────────────────────────────────────

    pub proof fn lemma_date_wf_implies_valid(e: DateExpr, env: Environment)
        requires e.is_well_formed(env),
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
        requires e.is_well_formed(env),
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
        requires e.is_well_formed(env),
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
        requires e.is_well_formed(env),
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
        requires ast.is_well_formed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<EpochDelta>(env),
    {
        lemma_bool_expr_epoch_delta_equiv(ast.root, env);
    }


    // ── Hybrid equivalence proofs ──────────────────────────────────────

    pub proof fn lemma_date_expr_hybrid_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(env),
        ensures hybrid_congruent(e.eval::<SimpleDate>(env), e.eval::<Hybrid>(env)),
        decreases e,
    {
        match e {
            DateExpr::Literal(y, m, d) => {
                theorem_hybrid_from_ymd_congruent(y, m, d);
            },
            DateExpr::Var(id) => {
                let sd = env.date_vars[id];
                theorem_hybrid_from_ymd_congruent(sd.year(), sd.month(), sd.day());
            },
            DateExpr::Add(base, period) => {
                lemma_date_expr_hybrid_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                theorem_hybrid_add_period_preserves_congruence(
                    base.eval::<SimpleDate>(env),
                    base.eval::<Hybrid>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_hybrid_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<Hybrid>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_hybrid_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<Hybrid>(env);
                lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_hybrid_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<Hybrid>(env);
                lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_hybrid_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                let h = d.eval::<Hybrid>(env);
                lemma_hybrid_to_ymd(sd, h);
            },
            IntExpr::Add(a, b) => {
                lemma_int_expr_hybrid_equiv(*a, env);
                lemma_int_expr_hybrid_equiv(*b, env);
            },
            IntExpr::Sub(a, b) => {
                lemma_int_expr_hybrid_equiv(*a, env);
                lemma_int_expr_hybrid_equiv(*b, env);
            },
            IntExpr::Mul(a, _) => {
                lemma_int_expr_hybrid_equiv(*a, env);
            },
        }
    }

    pub proof fn lemma_bool_expr_hybrid_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<Hybrid>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_hybrid_equiv(*a, env);
                lemma_bool_expr_hybrid_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_hybrid_equiv(*a, env);
                lemma_bool_expr_hybrid_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_hybrid_equiv(*a, env);
            },
            BoolExpr::Implies(a, b) => {
                lemma_bool_expr_hybrid_equiv(*a, env);
                lemma_bool_expr_hybrid_equiv(*b, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_hybrid_congruent(*a, env);
                lemma_date_expr_hybrid_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<Hybrid>(env),
                );
            },
            BoolExpr::DateEq(a, b) => {
                lemma_date_expr_hybrid_congruent(*a, env);
                lemma_date_expr_hybrid_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_hybrid_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<Hybrid>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<Hybrid>(env),
                );
            },
            BoolExpr::IntLt(a, b) => {
                lemma_int_expr_hybrid_equiv(*a, env);
                lemma_int_expr_hybrid_equiv(*b, env);
            },
            BoolExpr::IntEq(a, b) => {
                lemma_int_expr_hybrid_equiv(*a, env);
                lemma_int_expr_hybrid_equiv(*b, env);
            },
        }
    }

    pub proof fn theorem_ast_hybrid_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<Hybrid>(env),
    {
        lemma_bool_expr_hybrid_equiv(ast.root, env);
    }


    // ── AlphaBeta equivalence proofs ───────────────────────────────────

    pub proof fn lemma_date_expr_ab_congruent(e: DateExpr, env: Environment)
        requires e.is_well_formed(env),
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
        requires e.is_well_formed(env),
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
        requires e.is_well_formed(env),
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
        requires ast.is_well_formed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<AlphaBeta>(env),
    {
        lemma_bool_expr_ab_equiv(ast.root, env);
    }

} // verus!
