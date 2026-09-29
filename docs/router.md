# The router

The router is not an encoding of its own. It looks at a constraint, picks one of the int encodings (`simple`, `epoch_days`, `hybrid_ymd`, `hybrid_epoch`, `alpha_beta`), and solves the constraint with it. No single encoding is fastest on every constraint, and which one wins depends on what the constraint contains; the router guesses the winner from the constraint's text.

```python
import datesat

result = datesat.solve(
    {"declarations": ["x: date"], "constraints": ["x >= Date(2000, 1, 1)"]},
    approach="router",
)
result["routed_to"]      # the encoding the router picked, e.g. "hybrid_ymd"
result["routing_time"]   # seconds spent picking it
```

The router is only available through `solve()`, because it needs the whole constraint before it can pick. `DateSATBuilder(approach="router")` raises an error, and so does `approach="router"` with `implementation="bitvector"`.

## How it picks

1. **Features.** It computes 37 static features of the constraint text, such as how many free date variables there are, how many atoms, and the largest day offset added to a date. `router/features.py` and `router/parser.py` compute them. Both are copies of DateSATBench's `analysis/features/` code, and DateSATBench's `analysis/features/features.md` defines every feature.
2. **Pairwise forests.** For each pair of encodings, a random forest says how likely the first one is to be faster on this constraint. Each forest votes for the more likely of its two.
3. **The vote.** The encoding that wins the most pairs gets the constraint. The router uses the model's **fallback** encoding instead when two or more encodings tie for the most wins, or when the pick does not beat the fallback in their own forest with probability above 0.5 + the model's **margin**. The fallback is the best performing single encoding on the training data unless the model was trained with another.

## Where the model comes from

The model is trained in DateSATBench, on the results of running every encoding on its benchmarks:

```
python -m analysis.router.train_router --timeout <the timeout the results were run with, in ms>
```

This writes `analysis/outputs/model/router.json`. The router reads it from:

- `$DATESAT_ROUTER_MODEL`, when that environment variable is set;
- otherwise `datesat/router/model.json`, the model bundled with DateSat.

To swap in a new model, copy the new `router.json` over `datesat/router/model.json`, or point `DATESAT_ROUTER_MODEL` at it. The model is loaded once per process.

The router refuses a model file whose `format_version` it does not know, whose features were extracted with DateSATBench's injected bounds stripped (the router sees the bounds, so the model must be trained with `extract_features --bounds keep`), or that names an encoding or a feature it does not know.

## What it costs

`execution_time` includes the routing: extracting the features and walking the trees. `routing_time` reports that part on its own. Loading the model is not counted, because it happens once per process, like importing z3.

## Keeping the features in step

The model is only as good as the features it is fed. `router/features.py` and `router/parser.py` must compute exactly what DateSATBench's copies compute, so change them only by copying DateSATBench's versions over them again, and retrain the model whenever the features change.
