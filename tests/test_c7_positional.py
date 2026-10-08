"""Positional C7 tests (pure functions — no pdfplumber needed)."""
from __future__ import annotations

from aletheia.extract import assign_c7_marks, cluster_xs


def test_cluster_xs_groups_columns():
    assert cluster_xs([100.0, 101.5, 200.0, 201.0, 300.0, 400.5]) == [100.75, 200.5, 300.0, 400.5]


def test_assign_marks_left_to_right():
    rows = [
        {"text": "Academic GPA", "mark_x": 100.0},
        {"text": "Class rank", "mark_x": 300.0},
        {"text": "State residency", "mark_x": 400.0},
    ]
    got = assign_c7_marks(rows, [100.0, 200.0, 300.0, 400.0],
                          ["Very Important", "Important", "Considered", "Not Considered"])
    assert got == {"Academic GPA": "Very Important", "Class rank": "Considered", "State residency": "Not Considered"}


def test_assign_marks_unknown_column():
    got = assign_c7_marks([{"text": "Interview", "mark_x": 999.0}], [100.0, 200.0], ["Important", "Considered"])
    assert got == {}
