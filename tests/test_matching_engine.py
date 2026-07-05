import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from matching_engine import filter_results_to_dataset


def test_filter_results_to_dataset_removes_unknown_usernames():
    kols = [
        {"username": "alpha"},
        {"username": "beta"},
    ]
    results = [
        {"username": "alpha"},
        {"username": "ghost"},
        {"username": "beta"},
    ]

    filtered = filter_results_to_dataset(results, kols)

    assert [item["username"] for item in filtered] == ["alpha", "beta"]
