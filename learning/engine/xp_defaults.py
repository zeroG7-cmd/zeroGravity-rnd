"""Default XP and competency targets per journal entry type.

This is Step 1 of the plan discussed in chat: a deterministic lookup
table so you stop typing --base-xp/--target by hand for every entry.
You still pick the entry type(s) when you write the entry; this module
decides the XP amount and where it goes for you. Step 2 (later, an AI
layer that picks the entry type itself from what you wrote) feeds this
exact same table - nothing here needs to change when that gets built.

Targets point at real competencies already sitting in the SPIRIT branch
of your skill tree (Reflection, Identity, Purpose, Creativity) rather
than a bare stat code. This matters: a bare "stat:SPIRIT" target only
updates operator_core/profile's flat stats file, which your Overall
rating no longer reads from (see chat - Overall was rewired to read
learning_stats.json, fed by the competency/skill-tree hierarchy).
Targeting a real competency here means journal entries actually move
Overall, not just your total operator level.

Some entry types below (technical, test_log, business, decision,
planning, problem, learning) are inherently context-dependent - the
"right" target really depends on what the entry is about, which a
fixed table can't know. The defaults here are reasonable starting
points, not settled truth - adjust any of them freely, it's just a
dict.
"""
from __future__ import annotations

from learning.engine.xp import _normalise_awards

# A modest, flat default - journal entries are lighter-weight than a
# full course unit (which uses 40 XP). Tune freely.
DEFAULT_ENTRY_XP = 30

# entry_type -> list of {competency_id, weight}. Weights within one
# entry type's own list should sum to 1.0.
DEFAULT_XP_TARGETS: dict[str, list[dict[str, object]]] = {
    "epiphany": [
        {"competency_id": "spirit.reflection.reflective_practice.epiphanies", "weight": 1.0},
    ],
    "insight": [
        {"competency_id": "spirit.reflection.reflective_practice.meaning_making", "weight": 1.0},
    ],
    "reflection": [
        {"competency_id": "spirit.reflection.reflective_practice.self_assessment", "weight": 1.0},
    ],
    "spiritual": [
        {"competency_id": "spirit.reflection.reflective_practice.journaling", "weight": 1.0},
    ],
    "personal": [
        {"competency_id": "spirit.identity.self_knowledge.authenticity", "weight": 1.0},
    ],
    "creative": [
        {"competency_id": "int.creative_production.storytelling.worldbuilding", "weight": 1.0},
    ],
    # Business now correctly targets the real Business domain under INT,
    # not a SPIRIT placeholder - this was wrong in the first version.
    "business": [
        {"competency_id": "int.business.strategy.growth_planning", "weight": 1.0},
    ],
    "decision": [
        {"competency_id": "will.decisiveness.decision_execution.commitment", "weight": 1.0},
    ],
    "planning": [
        {"competency_id": "disc.time_management.planning.prioritisation", "weight": 1.0},
    ],
    "problem": [
        {"competency_id": "will.discomfort_tolerance.cognitive_discomfort.complex_problems", "weight": 1.0},
    ],
    "learning": [
        {"competency_id": "int.learning_practice.learning_systems.reflection", "weight": 1.0},
    ],
    # Technical/test_log now point at real R&D-shaped competencies
    # (shipping and logging evidence) instead of a vague SPIRIT guess.
    "technical": [
        {"competency_id": "will.courage.performance_courage.shipping_work", "weight": 1.0},
    ],
    "test_log": [
        {"competency_id": "disc.accountability.evidence.logging", "weight": 1.0},
    ],
}


def resolve_default_xp(
    entry_types: tuple[str, ...],
) -> tuple[int, list[dict[str, object]]]:
    """Return (base_xp, xp_targets) for the given entry types.

    If none of the entry types are in the table, returns (0, []) - the
    entry gets recorded with no XP, same as today's default behaviour.
    If multiple entry types are given, each type's own target list is
    weighted evenly against the others and then combined, so the
    weights across the whole result still sum to 1.0.
    """
    matched = [entry_type for entry_type in entry_types if entry_type in DEFAULT_XP_TARGETS]
    if not matched:
        return 0, []

    raw_awards: list[dict[str, object]] = []
    for entry_type in matched:
        raw_awards.extend(DEFAULT_XP_TARGETS[entry_type])

    return DEFAULT_ENTRY_XP, _normalise_awards(raw_awards)