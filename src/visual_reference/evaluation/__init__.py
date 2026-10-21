"""Evaluation: metadata scoring plus transparent diversity selection."""

from .diversity import DiversePick, distance, feature_vector, pairwise_distances, select_diverse
from .scoring import Score, evaluation_record, image_role, score_candidate

__all__ = [
    "DiversePick",
    "Score",
    "distance",
    "evaluation_record",
    "feature_vector",
    "image_role",
    "pairwise_distances",
    "score_candidate",
    "select_diverse",
]
