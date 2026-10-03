"""Curated milestone / course-completion achievements.

Hand-authored only - there is deliberately no code path that auto-generates
an achievement per course or per level. See data/definitions.json for the
actual catalog and service.py for the checking/awarding logic.
"""
from operator_core.achievements.service import check_and_award_all

__all__ = ["check_and_award_all"]
