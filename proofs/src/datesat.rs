use vstd::prelude::*;
use vstd::map::*;
use crate::*;

verus! {

    pub struct Identifier(int);

    pub struct Environment {
        pub int_vars: Map<Identifier, int>,
        pub date_vars: Map<Identifier, SimpleDate>,
    }

    pub struct Ast {
        pub root: BoolExpr,
    }

    pub enum BoolExpr {
        And(Box<BoolExpr>, Box<BoolExpr>),
        Or(Box<BoolExpr>, Box<BoolExpr>),
        Not(Box<BoolExpr>),
        Literal(bool),
        DateLt(Box<DateExpr>, Box<DateExpr>),
        DateEq(Box<DateExpr>, Box<DateExpr>),
    }

    pub enum IntExpr {
        Literal(int),
        Var(Identifier),
        Year(Box<DateExpr>),
        Month(Box<DateExpr>),
        Day(Box<DateExpr>),
    }

    pub enum DateExpr {
        Literal(int, int, int),
        Var(Identifier),
        Add(Box<DateExpr>, PeriodExpr),
    }

    pub enum PeriodExpr {
        Literal(int, int, int),
    }

    impl Environment {
        pub open spec fn date_var_valid(self, id: Identifier) -> bool {
            self.date_vars.dom().contains(id) && self.date_vars[id].is_valid()
        }
    }

    impl Ast {
        pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> bool {
            self.root.eval::<D>(env)
        }

        pub open spec fn is_well_formed(self, env: Environment) -> bool {
            self.root.is_well_formed(env)
        }
    }

    impl IntExpr {
        pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> int
            decreases self,
        {
            match self {
                IntExpr::Literal(n) => n,
                IntExpr::Var(id) => env.int_vars[id],
                IntExpr::Year(d) => d.eval::<D>(env).year(),
                IntExpr::Month(d) => d.eval::<D>(env).month(),
                IntExpr::Day(d) => d.eval::<D>(env).day(),
            }
        }
    }

    impl DateExpr {
        pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> D
            decreases self,
        {
            match self {
                DateExpr::Literal(y, m, d) => {
                    D::from_ymd(y, m, d)
                },
                DateExpr::Var(id) => {
                    let sd = env.date_vars[id];
                    D::from_ymd(sd.year(), sd.month(), sd.day())
                },
                DateExpr::Add(base, period) => {
                    base.eval::<D>(env).add_period(period.eval())
                },
            }
        }
    }

    impl BoolExpr {
        pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> bool
            decreases self,
        {
            match self {
                BoolExpr::And(a, b) => a.eval::<D>(env) && b.eval::<D>(env),
                BoolExpr::Or(a, b) => a.eval::<D>(env) || b.eval::<D>(env),
                BoolExpr::Not(a) => !a.eval::<D>(env),
                BoolExpr::Literal(v) => v,
                BoolExpr::DateLt(a, b) => a.eval::<D>(env).lt(b.eval::<D>(env)),
                BoolExpr::DateEq(a, b) => a.eval::<D>(env).eq(b.eval::<D>(env)),
            }
        }
    }

    impl PeriodExpr {
        pub open spec fn eval(self) -> Period {
            match self {
                PeriodExpr::Literal(y, m, d) => Period(y, m, d),
            }
        }
    }

    // ── Well-formedness ────────────────────────────────────────────────

    impl DateExpr {
        pub open spec fn is_well_formed(self, env: Environment) -> bool
            decreases self,
        {
            match self {
                DateExpr::Literal(y, m, d) => SimpleDate(y, m, d).is_valid(),
                DateExpr::Var(id) => env.date_var_valid(id),
                DateExpr::Add(base, _) => base.is_well_formed(env),
            }
        }
    }

    impl IntExpr {
        pub open spec fn is_well_formed(self, env: Environment) -> bool
            decreases self,
        {
            match self {
                IntExpr::Literal(_) => true,
                IntExpr::Var(id) => env.int_vars.dom().contains(id),
                IntExpr::Year(d) => d.is_well_formed(env),
                IntExpr::Month(d) => d.is_well_formed(env),
                IntExpr::Day(d) => d.is_well_formed(env),
            }
        }
    }

    impl BoolExpr {
        pub open spec fn is_well_formed(self, env: Environment) -> bool
            decreases self,
        {
            match self {
                BoolExpr::And(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::Or(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::Not(a) => a.is_well_formed(env),
                BoolExpr::Literal(_) => true,
                BoolExpr::DateLt(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::DateEq(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
            }
        }
    }

    // ── EpochDelta equivalence proofs ───────────────────────────────────

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

    pub proof fn lemma_date_expr_ed_congruent(e: DateExpr, env: Environment)
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
                lemma_date_expr_ed_congruent(*base, env);
                lemma_date_wf_implies_valid(*base, env);
                theorem_epoch_delta_add_period_preserves_congruence(
                    base.eval::<SimpleDate>(env),
                    base.eval::<EpochDelta>(env),
                    period.eval(),
                );
            },
        }
    }

    pub proof fn lemma_int_expr_equiv(e: IntExpr, env: Environment)
        requires e.is_well_formed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<EpochDelta>(env),
        decreases e,
    {
        match e {
            IntExpr::Literal(_) => {},
            IntExpr::Var(_) => {},
            IntExpr::Year(d) => {
                lemma_date_expr_ed_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Month(d) => {
                lemma_date_expr_ed_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
            IntExpr::Day(d) => {
                lemma_date_expr_ed_congruent(*d, env);
                lemma_date_wf_implies_valid(*d, env);
                let sd = d.eval::<SimpleDate>(env);
                theorem_epoch_delta_to_ymd_from_simple_date_inverse(sd);
            },
        }
    }


    pub proof fn lemma_bool_expr_equiv(e: BoolExpr, env: Environment)
        requires e.is_well_formed(env),
        ensures e.eval::<SimpleDate>(env) == e.eval::<EpochDelta>(env),
        decreases e,
    {
        match e {
            BoolExpr::And(a, b) => {
                lemma_bool_expr_equiv(*a, env);
                lemma_bool_expr_equiv(*b, env);
            },
            BoolExpr::Or(a, b) => {
                lemma_bool_expr_equiv(*a, env);
                lemma_bool_expr_equiv(*b, env);
            },
            BoolExpr::Not(a) => {
                lemma_bool_expr_equiv(*a, env);
            },
            BoolExpr::Literal(_) => {},
            BoolExpr::DateLt(a, b) => {
                lemma_date_expr_ed_congruent(*a, env);
                lemma_date_expr_ed_congruent(*b, env);
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
                lemma_date_expr_ed_congruent(*a, env);
                lemma_date_expr_ed_congruent(*b, env);
                lemma_date_wf_implies_valid(*a, env);
                lemma_date_wf_implies_valid(*b, env);
                theorem_epoch_delta_congruent_preserves_comparison(
                    a.eval::<SimpleDate>(env),
                    a.eval::<EpochDelta>(env),
                    b.eval::<SimpleDate>(env),
                    b.eval::<EpochDelta>(env),
                );
            },
        }
    }


    pub proof fn theorem_ast_epoch_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<EpochDelta>(env),
    {
        lemma_bool_expr_equiv(ast.root, env);
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
        }
    }

    pub proof fn theorem_ast_ab_equiv(ast: Ast, env: Environment)
        requires ast.is_well_formed(env),
        ensures ast.eval::<SimpleDate>(env) == ast.eval::<AlphaBeta>(env),
    {
        lemma_bool_expr_ab_equiv(ast.root, env);
    }


} // verus!
