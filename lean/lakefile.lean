import Lake
open Lake DSL

package «DateTheory» where

lean_lib «DateSAT» where
  roots := #[`DateSATSemantics, `DateSATNaive, `Check]
