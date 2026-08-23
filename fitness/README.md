# Fitness

Daily bodyweight/cardio habit tracking for Zero, and the weekly gym routine
that goes with it. This is the physical-training counterpart to `learning/`:
`learning/` turns study into INT; `fitness/` turns training into STR, CON and
Discipline evidence.

## Daily habits (v1)

Manual, quantity-based logging until an exercise-recognition device exists
(see `journal/` / `lab/` for that research thread). Each day you can log:

| Habit             | Daily target | Feeds                                              |
|-------------------|-------------:|-----------------------------------------------------|
| Push-ups          | 60           | `str.muscular_strength.upper_body.push_ups`          |
| Pull-ups          | 60           | `str.muscular_strength.upper_body.pull_ups`          |
| Sit-ups           | 60           | `str.muscular_strength.core.sit_ups`                 |
| Squats            | 60           | `str.muscular_strength.lower_body.squats`            |
| Jog               | 30 minutes   | `con.endurance.aerobic_capacity.running`             |
| Stretch/mobility  | 10 minutes   | `con.health_management.mobility.stretching` **+** `dex.agility.mobility.dynamic_flexibility` |

Every logged habit also puts a small share of its XP into
`disc.consistency.routine_adherence.daily_practice` — showing up is Discipline
evidence regardless of which stat the exercise itself trains.

**Why stretching feeds two stats:** the existing skill tree keeps general
flexibility/joint-health maintenance under CON (`health_management.mobility`)
and reserves DEX for skill-in-motion — agility, balance, coordination, martial
arts (footwork, reaction time, capoeira, taekwondo, etc). Flexibility is
genuinely both: how supple and resilient your tissue/joints are is a CON
trait, but how well that range of motion actually shows up in controlled,
active movement is closer to DEX. Rather than pick one, the stretch/mobility
habit's non-Discipline XP splits 50/50 between
`con.health_management.mobility.stretching` (tissue/joint health) and the new
`dex.agility.mobility.dynamic_flexibility` (movement quality — see
`operator_core/capabilities/capability_graph.json`). Every other habit still
feeds a single stat; this split is specific to stretching.

100/day (a "Century") is the stretch goal once 60/day is consistent — see the
`push_ups.century` / `pull_ups.century` / etc. concepts in the capability
graph.

## Targets & scoring

Targets and per-exercise XP pools live in `fitness/engine/config.py`. XP for
a logged quantity scales linearly with how close to (or past) target you are,
capped at 2x target, so overshooting is rewarded without being unbounded.

## Weekly gym routine

`fitness/routines/weekly_routine.json` holds the weekly split (push / pull /
legs / core & cardio / mobility / rest) referenced by the Zero Command System
fitness dashboard. Edit it directly to change the plan.

## Engine

```
python -m fitness.engine.tracker --pushups 62 --pullups 58 --situps 70 --squats 65 --run-minutes 32 --stretch-minutes 12
python -m fitness.engine.tracker --status
python -m fitness.engine.stats
```

`tracker.py` logs one day's numbers, distributes XP through
`operator_core.events` / `operator_core.distribution` (the same shared
mechanics `learning/` uses), updates `operator_core/capabilities/competencies.json`,
and calls `fitness/engine/stats.py` to recompute average levels in
`operator_core/hubs/learning/stats/learning_stats.json` for every branch this
touches (STR's Muscular Strength tree, CON's Endurance/Health Management
trees, DEX's Agility tree, and DISC's Consistency tree). It intentionally
does not touch INT or anything learning-owns.

This is a deliberately simple v1 (see `operator_core/hubs/tasks/README.md`'s
philosophy: start simple, extend later). Streak-based bonuses beyond a flat
"you showed up today" credit, and WILL evidence for pushing through a hard
session, are left for a later pass.
