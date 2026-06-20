use vstd::prelude::*;
use vstd::map::*;
use crate::*;

verus! {

    pub struct Identifier(int);

    pub struct Environment {
        pub int_vars: Map<Identifier, int>,
        pub bool_vars: Map<Identifier, bool>,
        pub date_vars: Map<Identifier, SimpleDate>,
    }

    pub struct Ast {
        pub root: BoolExpr,
    }

    pub enum BoolExpr {
        And(Box<BoolExpr>, Box<BoolExpr>),
        Or(Box<BoolExpr>, Box<BoolExpr>),
        Not(Box<BoolExpr>),
        Implies(Box<BoolExpr>, Box<BoolExpr>),
        Literal(bool),
        Var(Identifier),
        DateLt(Box<DateExpr>, Box<DateExpr>),
        DateEq(Box<DateExpr>, Box<DateExpr>),
        IntLt(Box<IntExpr>, Box<IntExpr>),
        IntEq(Box<IntExpr>, Box<IntExpr>),
    }

    pub enum IntExpr {
        Literal(int),
        Var(Identifier),
        Year(Box<DateExpr>),
        Month(Box<DateExpr>),
        Day(Box<DateExpr>),
        Add(Box<IntExpr>, Box<IntExpr>),
        Sub(Box<IntExpr>, Box<IntExpr>),
        Mul(Box<IntExpr>, int),
    }

    pub enum DateExpr {
        Literal(int, int, int),
        Var(Identifier),
        Add(Box<DateExpr>, PeriodExpr),
    }

    pub enum PeriodExpr {
        Literal(int, int, int),
        Add(Box<PeriodExpr>, Box<PeriodExpr>),
        Scale(Box<PeriodExpr>, int),
    }

    // ── Well-formedness ────────────────────────────────────────────────

    impl Environment {
        pub open spec fn date_var_valid(self, id: Identifier) -> bool {
            self.date_vars.dom().contains(id) && self.date_vars[id].is_valid()
        }
    }

    impl Ast {
        pub open spec fn is_well_formed(self, env: Environment) -> bool {
            self.root.is_well_formed(env)
        }
    }

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
                IntExpr::Add(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                IntExpr::Sub(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                IntExpr::Mul(a, _) => a.is_well_formed(env),
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
                BoolExpr::Implies(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::Literal(_) => true,
                BoolExpr::Var(id) => env.bool_vars.dom().contains(id),
                BoolExpr::DateLt(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::DateEq(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::IntLt(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
                BoolExpr::IntEq(a, b) => a.is_well_formed(env) && b.is_well_formed(env),
            }
        }
    }

    // ── Evaluation ─────────────────────────────────────────────────────

    impl Ast {
        pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> bool {
            self.root.eval::<D>(env)
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
                IntExpr::Add(a, b) => a.eval::<D>(env) + b.eval::<D>(env),
                IntExpr::Sub(a, b) => a.eval::<D>(env) - b.eval::<D>(env),
                IntExpr::Mul(a, k) => a.eval::<D>(env) * k,
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
                BoolExpr::Implies(a, b) => a.eval::<D>(env) ==> b.eval::<D>(env),
                BoolExpr::Literal(v) => v,
                BoolExpr::Var(id) => env.bool_vars[id],
                BoolExpr::DateLt(a, b) => a.eval::<D>(env).lt(b.eval::<D>(env)),
                BoolExpr::DateEq(a, b) => a.eval::<D>(env).eq(b.eval::<D>(env)),
                BoolExpr::IntLt(a, b) => a.eval::<D>(env) < b.eval::<D>(env),
                BoolExpr::IntEq(a, b) => a.eval::<D>(env) == b.eval::<D>(env),
            }
        }
    }

    impl PeriodExpr {
        pub open spec fn eval(self) -> Period
            decreases self,
        {
            match self {
                PeriodExpr::Literal(y, m, d) => Period(y, m, d),
                PeriodExpr::Add(a, b) => a.eval().add(b.eval()),
                PeriodExpr::Scale(p, k) => p.eval().scale(k),
            }
        }
    }


} // verus!
