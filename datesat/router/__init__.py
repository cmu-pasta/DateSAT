"""
The router approach: picks one of DateSat's int encodings for each constraint with a model
trained in DateSATBench, and hands the constraint to it. See docs/router.md.
"""

import time

from .features import features_for
from .model import load_model


def route(constraint_data):
    """Pick the encoding for one constraint, a dict with "declarations" and "constraints".

    Returns (encoding, routing_time): the approach name of the chosen encoding, and the
    seconds that extracting the features and walking the model took. Loading the model
    is not counted; call load_model() first to keep it out of a timed region.
    """
    model = load_model()
    start = time.perf_counter()
    encoding = model.pick(features_for(constraint_data, ""))
    return encoding, time.perf_counter() - start
