"""
Unit tests for the router approach: datesat.router and datesat.solve(approach="router").
"""

import json

import pytest

import datesat
from datesat import router
from datesat.router.features import FEATURES
from datesat.router.model import BUNDLED_MODEL, load_model

ONE_ATOM = {"declarations": ["x: date"], "constraints": ["x >= Date(2000, 1, 1)"]}
TWO_ATOMS = {"declarations": ["x: date"],
             "constraints": ["x >= Date(2000, 1, 1)", "x <= Date(2000, 12, 31)"]}


def write_model(path, tree, features=("n_atoms",)):
    """A model with one pair, epoch_days vs simple, of one tree, falling back to simple."""
    path.write_text(json.dumps({
        "format_version": 1, "bounds": "keep", "encodings": ["epoch_days", "simple"],
        "features": list(features), "fallback": "simple", "margin": 0.0,
        "trained_on": {}, "pairs": [{"a": "epoch_days", "b": "simple", "trees": [tree]}],
    }))
    return str(path)


# epoch_days is faster on one atom (n_atoms <= 1.5), simple on more.
SPLIT_ON_ATOMS = {"feature": [0, -1, -1], "threshold": [1.5, 0.0, 0.0],
                  "left": [1, -1, -1], "right": [2, -1, -1], "p_a": [0.0, 1.0, 0.0]}


def test_route_follows_the_model_at_the_given_path(tmp_path):
    path = write_model(tmp_path / "model.json", SPLIT_ON_ATOMS)
    assert router.route(ONE_ATOM, path)[0] == "epoch_days"
    assert router.route(TWO_ATOMS, path)[0] == "simple"


def test_solve_routes_with_the_given_model_and_times_the_routing(tmp_path):
    path = write_model(tmp_path / "model.json", SPLIT_ON_ATOMS)
    result = datesat.solve(ONE_ATOM, approach="router", router_model=path, verbose=False)
    assert result["status"] == "sat"
    assert result["routed_to"] == "epoch_days"
    assert 0 <= result["routing_time"] <= result["execution_time"]


def test_router_model_is_only_for_the_router_approach(tmp_path):
    path = write_model(tmp_path / "model.json", SPLIT_ON_ATOMS)
    with pytest.raises(ValueError, match="router_model"):
        datesat.solve(ONE_ATOM, approach="epoch_days", router_model=path, verbose=False)


def test_a_model_reading_a_feature_the_router_does_not_compute_is_refused(tmp_path):
    path = write_model(tmp_path / "model.json", SPLIT_ON_ATOMS, features=("no_such_feature",))
    with pytest.raises(ValueError, match="no_such_feature"):
        load_model(path)


def test_the_bundled_model_loads_and_picks_one_of_its_encodings():
    model = load_model(BUNDLED_MODEL)
    assert set(model.features) <= set(FEATURES)
    assert router.route(TWO_ATOMS, BUNDLED_MODEL)[0] in model.encodings
