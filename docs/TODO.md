DateSMT
[X] Review and clean up code (Angel)
[X] Figure out the hybrid approach (Angel)
[X] Alpha/beta approach (Angel)
[X] Rename all approaches
[X] Update constraints to (1900,3,1) to (2100,2,28) - inclusive
[X] Library behavior when an input is an invalid day/out of range?
[X] Clean up symbolic_alpha_beta_table
[X] Check if we can specify temp var (var that we don't need result for) - still need to solve but can not return the result -> don't matter in terms of performance?
[X] Use bit vector? - Added
[X] Further reduce bit width?
[X] Dynamic bit width? - No
[ ] BitVector/Int hybrid approach?
[X] Think about hybrid method: do we need lazy approach?
[X] Update hybrid method: lazy on both ymd and epoch
[X] Think about cases where bitvector is slower? (div/mod)
[X] Optimize add func for all methods (fast paths for adding days within a month?)
[X] Support OR (CNF)
[X] List of clauses, each clause is a disjunction of items - have a list of list

Unit test
[X] Add unit test coverage (Angel)
[X] Clean up core_data_structures, epoch_days_specific, baseline_specific (Angel)
[X] Replace java with python? (Angel)
[X] Update date constraints test
[X] Write up unit tests

Property test
[X] Validate java vs python (Angel)

Integration test
[X] Remove prediction_correct that was based on LLM predicted output (Angel)
[X] Remove expected_satisfiable that was generated from LLM (Angel)
[X] Implement check integration test results (declare the solved result as Date and assert that operation is satisfiable)
[X] Fix integration test check result so that it uses python library to check for ground truth

LLM test generation
[X] Make llm_constraints_generator better in generating integration tests that cover more cases
[X] Make constraint_code just a list of strings of constraints, write the constraints parser

Debugging
[X] Figure out 1758090062-13 for baseline - See nothing wrong after updating the implementation -> ?
[X] Figure out the "error" cases in the results
    [X]1758086606-5: Date - Date
    [X]1758086606-8: PeriodVar should not be supported - add check & remove period_variables in tests
    [X]1758090062-4: Same as 1758086606-8
    [X]1758090062-5: Date - Date
    [X]1758090062-9: Same as 1758086606-8
[X] Figure out the "timeout" cases in the results
    [X]1758090062-12
[X] Figure out the "wrong" cases in the results - NO WRONG CASES
    [X]1758090062-11
    [X]1758090062-13

Evaluation
[X] Dump smt to run on cvc 5 - better performance - NO
[X] Keep num of lines only for information but not for evaluation
[X] Constrant generator? (Random Testing) - Ask Vasu
[X] LLM generated ones
[ ] Legal docs
[X] Add a baseline groundtruth just by enumerating with Python datetime library
[ ] IAM Policies
[ ] Look into vector distance in performance for diverse benchmark creation (diverse and hard) -> can use to prune benchmark
[X] Make a universal llm client code
[ ] Verify that timeout now don't save as unsat, but as timeout
[ ] Enable parallel runs

General
[X] Organize repo (Angel)
[ ] Clean up existing code
    [X] datesmt/
        [X] __init__.py
        [X] api.py
        [X] concrete.py
        [X] core.py
        [X] constraint_parser.py
        [X] symbolic_int/
            [X] baseline
            [X] epoch_days
            [X] hybrid
            [X] alpha_beta
            [X] alpha_beta_table
        [X] symbolic_bitvector/
            [X] baseline
            [X] epoch_days
            [X] hybrid
            [X] alpha_beta
            [X] alpha_beta_table
    [ ] tests/
        [X] core_data_structures/
            [X] test_date.py
            [X] test_period.py
        [X] test_constraint_parser.py
[X] Clean up existing doc
[X] Add READMEs
[X] Add documentation for each method
[X] Flatten data from llm_constraints_generator?
[X] Fix CI so that do not run unit tests when push, only when raising PR
[X] Accept timeout for enumeration baseline unit tests
[ ] Rename baseline encoding into naive encoding
