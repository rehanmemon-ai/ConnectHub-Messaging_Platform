import pytest

from evals.dataset import MESSAGES, QUERIES
from evals.metrics import (
    average_precision_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)
from evals.summary_dataset import FIXTURES


def test_synthetic_datasets_have_expected_size_and_no_empty_content() -> None:
    assert len(MESSAGES) == 120
    assert len(QUERIES) == 60
    assert len(FIXTURES) == 18
    assert all(message.text and message.id for message in MESSAGES)
    assert all(query.text for query in QUERIES)


def test_metrics_reward_a_perfect_ranking() -> None:
    ranked = ["a", "b", "c"]
    relevant = {"a", "b"}
    grades = {"a": 3, "b": 2}
    assert precision_at_k(ranked, relevant, 2) == 1
    assert recall_at_k(ranked, relevant, 2) == 1
    assert reciprocal_rank_at_k(ranked, relevant, 3) == 1
    assert ndcg_at_k(ranked, grades, 2) == 1
    assert average_precision_at_k(ranked, relevant, 3) == 1


def test_metrics_handle_bad_empty_and_no_relevance_rankings() -> None:
    assert precision_at_k(["x", "a"], {"a"}, 2) == 0.5
    assert recall_at_k([], {"a"}, 5) == 0
    assert reciprocal_rank_at_k(["x", "a"], {"a"}, 2) == 0.5
    assert ndcg_at_k(["x", "a"], {"a": 3}, 2) < 1
    assert ndcg_at_k([], {}, 5) == 0
    assert average_precision_at_k([], set(), 5) == 0


@pytest.mark.parametrize(
    "metric",
    [precision_at_k, recall_at_k, reciprocal_rank_at_k, ndcg_at_k],
)
def test_metrics_reject_nonpositive_k(metric) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        metric([], {}, 0)
