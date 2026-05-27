"""Unit tests for semantic cache helpers (no Redis needed)."""

import numpy as np
import pytest
from src.cache.semantic_cache import _cosine_sim


def test_cosine_sim_identical_vectors():
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert abs(_cosine_sim(a, a) - 1.0) < 1e-6


def test_cosine_sim_orthogonal_vectors():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert abs(_cosine_sim(a, b)) < 1e-6


def test_cosine_sim_opposite_vectors():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([-1.0, 0.0], dtype=np.float32)
    assert abs(_cosine_sim(a, b) - (-1.0)) < 1e-6


def test_cosine_sim_zero_vector():
    a = np.array([1.0, 0.5], dtype=np.float32)
    b = np.zeros(2, dtype=np.float32)
    assert _cosine_sim(a, b) == 0.0


def test_cosine_sim_scale_invariant():
    a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    b = np.array([2.0, 4.0, 6.0], dtype=np.float32)  # 2*a
    assert abs(_cosine_sim(a, b) - 1.0) < 1e-6
