# DateSATBench Datasets

**Note:** All commands assume you are running from the repository root directory.

This directory contains DateSATBench's datasets and code to furthur generate DateSATBench constraints, code for evaluating DateSAT solvers, and util code for generating summarization stats/graphs.

## DateSATBench

DateSATBench contains 3 curated dataset. Please see paper for more details.
- **LLM Constraint Generation**: See `llm_constraints/README.md`
- **Legally Grounded Constraint Generation**: See `legal_doc_constraints/README.md`

## Evaluation Script

To run evaluation on different DateSAT solvers for different DateSATBench dataset, see `python datesatbench/run_benchmarks.py --help`.

## Utils

The `utils/` directory contains utility scripts for datesatbench analysis and benchmarking:

- **`plot_benchmark_stats.py`**: Generates publication-quality plots showing benchmark statistics (variables and constraints per datesatbench) with standard deviation. Outputs PDF figures and console statistics including extreme cases. 
  ```bash
  python datesatbench/utils/plot_benchmark_stats.py -o benchmark_stats.pdf
  ```

- **`plot_normalized_speedup.py`**: Generates publication-quality plots showing `run_benchmarks.py`'s generated results' statistics. Note that you need to run the evaluation first to generate this plot.

- **`compute_time.py`**: Computes execution time statistics from benchmark result files (mean, median, std dev, percentiles).

- **`validation.py`**: Validates solver solutions against constraints using concrete evaluation.

- **`llm.py`**: Universal LLM client supporting OpenAI and Anthropic APIs.