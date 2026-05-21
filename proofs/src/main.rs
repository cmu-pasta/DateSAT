use vstd::prelude::*;
use vstd::math::*;

mod period;
use period::*;

mod simple_date;
use simple_date::*;

mod monotonicity;
use monotonicity::*;

mod epoch_delta;
use epoch_delta::*;

mod hybrid;
use hybrid::*;

mod alpha_beta;
use alpha_beta::*;

mod datesat;
use datesat::*;

verus! {

    /// Trait for date encodings that support construction from YMD,
    /// comparison, and period addition.
    pub trait DateEncoding: Sized {
        spec fn from_ymd(y: int, m: int, d: int) -> Self;
        spec fn year(self) -> int;
        spec fn month(self) -> int;
        spec fn day(self) -> int;
        spec fn lt(self, other: Self) -> bool;
        spec fn eq(self, other: Self) -> bool;
        spec fn add_period(self, period: Period) -> Self;
    }

    /// The epoch: March 1, 2000. Chosen so that the leap day (Feb 29) falls
    /// at the end of the epoch-year, simplifying the from_simple_date formula.
    pub spec const EPOCH : SimpleDate = SimpleDate(2000, 3, 1);

    fn main() {
        // Theorem 1: Well-formedness of Date-{eriod Addition
        assert forall|d: SimpleDate, p: Period| #![auto]
            d.is_valid() implies d.add_period(p).is_valid() by { theorem_date_add_period_preserves_validity(d, p); }

        // Theorem 2: Monotonicity of Date-Period Addition
        assert forall|d1: SimpleDate, d2: SimpleDate, p: Period| #![auto]
            d1.is_valid() && d2.is_valid() && d1.leq(d2) implies
                d1.add_period(p).leq(d2.add_period(p)) by { theorem_date_add_period_is_monotonic(d1, d2, p); }

        // Theorem 3: EpochDelta equivalence
        assert forall|ast: Ast, env: Environment| #![auto]
            ast.is_well_formed(env) implies
                ast.eval::<SimpleDate>(env) == ast.eval::<EpochDelta>(env)
            by { theorem_ast_epoch_equiv(ast, env); }

        // Theorem 4: Hybrid equivalence
        assert forall|ast: Ast, env: Environment| #![auto]
            ast.is_well_formed(env) implies
                ast.eval::<SimpleDate>(env) == ast.eval::<Hybrid>(env)
            by { theorem_ast_hybrid_equiv(ast, env); }

        // Theorem 5: AlphaBeta equivalence
        assert forall|ast: Ast, env: Environment| #![auto]
            ast.is_well_formed(env) implies
                ast.eval::<SimpleDate>(env) == ast.eval::<AlphaBeta>(env)
            by { theorem_ast_ab_equiv(ast, env); }

    }

} // verus!
