DateSMT
[X] Review and clean up code (Angel)
[X] Figure out the hybrid approach (Angel)
[X] Alpha/beta approach (Angel)
[X] Rename all approaches
[X] Update constraints to (1900,3,1) to (2100,2,28) - inclusive
[X] Library behavior when an input is an invalid day/out of range?
[X] Clean up symbolic_alpha_beta_table
[ ] Check if we can specify temp var (var that we don't need result for)
[ ] Think about hybrid method: do we need lazy approach?

Unit test
[X] Add unit test coverage (Angel)
[X] Clean up core_data_structures, epoch_days_specific, baseline_specific (Angel)
[X] Replace java with python? (Angel)
[X] Update date constraints test
[ ] Write up unit tests for all datesmt code

Property test
[X] Validate java vs python (Angel)

Integration test
[X] Remove prediction_correct that was based on LLM predicted output (Angel)
[X] Remove expected_satisfiable that was generated from LLM (Angel)
[X] Implement check integration test results (declare the solved result as Date and assert that operation is satisfiable)
[ ] Fix integration test check result so that it uses python library to check for ground truth

LLM test generation
[ ] Make llm_generator better in generating integration tests that cover more cases
[ ] Make constraint_code just a list of strings of constraints

Debugging
[ ] Figure out 1758090062-13 for baseline
[ ] Figure out the "error" cases in the results
[ ] Figure out the "timeout" cases in the results

General
[X] Organize repo (Angel)
[ ] Clean up existing code
[ ] Make helper functions' names begin with _
[ ] Clean up existing doc
[ ] Add documentation for each method
