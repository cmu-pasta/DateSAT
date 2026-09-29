"""
The router's model: one random forest per pair of encodings, trained in DateSATBench
(analysis/router/train_router.py writes it as analysis/outputs/model/router.json).

The file holds every tree as parallel node arrays: feature, threshold, left, right, and
p_a, the probability at a leaf that the pair's first encoding is faster. At a node, go
left if x[feature] <= threshold; leaves have left == -1. A forest's probability is the
mean of its trees' leaf p_a. The features are rounded to 32-bit floats first, because
scikit-learn, which chose the thresholds, compares them that way.

The model is read from $DATESAT_ROUTER_MODEL when that is set, and from the model.json
bundled next to this file otherwise.
"""

import json
import os
import struct
from functools import lru_cache
from pathlib import Path

from .features import FEATURES

FORMAT_VERSION = 1
MODEL_ENV = "DATESAT_ROUTER_MODEL"
BUNDLED_MODEL = Path(__file__).with_name("model.json")
# The int approaches the router may hand a constraint to.
INT_APPROACHES = ("simple", "epoch_days", "hybrid_ymd", "hybrid_epoch", "alpha_beta",
                  "alpha_beta_table")


def model_path():
    """The model file the router uses."""
    return Path(os.environ.get(MODEL_ENV) or BUNDLED_MODEL)


def load_model():
    """The router's model, loaded once per process and per path."""
    return _load(str(model_path()))


@lru_cache(maxsize=None)
def _load(path):
    return RouterModel.from_file(Path(path))


def as_float32(v):
    """`v` rounded to the nearest 32-bit float."""
    return struct.unpack("f", struct.pack("f", v))[0]


def forest_probability(trees, x):
    """P(the pair's first encoding is faster), for the float32-rounded feature vector x."""
    total = 0.0
    for t in trees:
        feature, threshold, left, right = t["feature"], t["threshold"], t["left"], t["right"]
        node = 0
        while left[node] != -1:
            node = left[node] if x[feature[node]] <= threshold[node] else right[node]
        total += t["p_a"][node]
    return total / len(trees)


class RouterModel:
    """A loaded model file and the rule that routes by it."""

    def __init__(self, data):
        self.encodings = data["encodings"]
        self.features = data["features"]
        self.fallback = data["fallback"]
        self.margin = data["margin"]
        self.pairs = data["pairs"]

    @classmethod
    def from_file(cls, path):
        if not path.exists():
            raise FileNotFoundError(
                f"no router model at {path}. Train one in DateSATBench "
                f"(python -m analysis.router.train_router writes "
                f"analysis/outputs/model/router.json), then copy it to {BUNDLED_MODEL} "
                f"or set {MODEL_ENV} to its path.")
        data = json.loads(path.read_text())
        problems = []
        if data.get("format_version") != FORMAT_VERSION:
            problems.append(f"format_version is {data.get('format_version')!r}, "
                            f"not {FORMAT_VERSION}")
        if data.get("bounds") != "keep":
            problems.append("its features were extracted with the injected bounds "
                            f"{data.get('bounds')!r}, but the router sees them; retrain on "
                            "features extracted with --bounds keep")
        unknown = [e for e in data.get("encodings", []) if e not in INT_APPROACHES]
        if unknown:
            problems.append(f"unknown encodings {unknown}")
        if data.get("fallback") not in data.get("encodings", []):
            problems.append(f"the fallback {data.get('fallback')!r} is not one of its encodings")
        missing = [f for f in data.get("features", []) if f not in FEATURES]
        if missing:
            problems.append(f"features the router does not compute: {missing}")
        if problems:
            raise ValueError(f"router model {path}: " + "; ".join(problems))
        return cls(data)

    def pick(self, features):
        """The encoding for one constraint, given its features as a dict.

        Each pairwise forest votes for the faster of its two encodings (probability above
        0.5), and the encoding that wins the most pairs is picked. The fallback is used
        instead when two or more encodings tie for the most wins, or when the pick does
        not beat the fallback in their own forest with probability above 0.5 + margin.
        """
        x = [as_float32(float(features[name])) for name in self.features]
        wins = dict.fromkeys(self.encodings, 0)
        beats = {}                                 # (a, b) -> P(a is faster than b)
        for pair in self.pairs:
            a, b = pair["a"], pair["b"]
            p = forest_probability(pair["trees"], x)
            beats[(a, b)], beats[(b, a)] = p, 1 - p
            if p > 0.5:
                wins[a] += 1
            elif p < 0.5:
                wins[b] += 1

        top = max(wins.values())
        leaders = [e for e in self.encodings if wins[e] == top]
        pick = leaders[0]
        if len(leaders) > 1:
            return self.fallback
        if pick != self.fallback and beats[(pick, self.fallback)] <= 0.5 + self.margin:
            return self.fallback
        return pick
