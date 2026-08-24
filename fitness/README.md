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
| Push-ups          | 60           | `str.muscular_strength.pushing_strength.push_ups`    |
| Pull-ups          | 60           | `str.muscular_strength.pulling_strength.pull_ups`    |
| Sit-ups           | 60           | `str.muscular_strength.core_strength.sit_ups`        |
| Squats            | 60           | `str.muscular_strength.leg_strength.squats`          |
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

## Muscular Strength tree

`Upper Body` and `Functional Strength` don't exist anymore under STR. The
tree was restructured to actually reflect the weekly gym routine below
instead of a generic muscle-group split with mostly-empty placeholder
leaves:

- **Pushing Strength** — Push-ups plus the Monday push-day lifts (Bench
  Press, Overhead Press, Incline Press / Dips, Lateral Raises, Triceps
  Extension).
- **Pulling Strength** — Pull-ups plus the Thursday pull-day lifts (Lat
  Pulldown, Rows, Face Pulls, Bicep Curls).
- **Grip Strength** — Crush Grip (renamed from the original "Grip Strength"
  capability, to avoid sharing a name with its own category, moved out of
  the now-deleted Functional Strength domain) plus Farmer's Carry.
- **Leg Strength** — Squats plus the Tuesday leg-day and Friday deadlift work
  (Barbell Squat, Romanian Deadlift, Deadlift, Leg Press / Lunges, Leg Curl,
  Calf Raise). Named "Leg Strength" rather than "Lower Body" or "Lower
  Strength" (the latter reads as *reduced* strength) to match the
  Pushing/Pulling Strength naming pattern.
- **Core Strength** — Sit-ups, Bracing, Anti-rotation (unchanged capabilities,
  renamed category to match the pattern).

All five Muscular Strength categories now follow the same `[X] Strength`
naming shape (Pushing Strength, Pulling Strength, Grip Strength, Leg
Strength, Core Strength) instead of mixing that with plain body-region
labels.

Bodyweight daily habits (Push-ups, Pull-ups, Squats, Sit-ups) stay separate
capabilities from their loaded gym-lift counterparts (Bench Press, Barbell
Squat, etc.) on purpose — high-rep bodyweight work and heavy low-rep lifting
train genuinely different qualities (muscular endurance vs. maximal
strength), the same way `stretch_minutes` earns two different stats instead
of being forced into one.

Functional Strength was cut entirely rather than kept as an empty
placeholder — it was designed around occupational load-bearing (warehouse
work, awkward equipment carrying) that doesn't apply right now. It can come
back if that ever changes. Anti-rotation stays as a placeholder under Core
even though nothing in the current routine trains it yet, pending adding a
rotational exercise (Pallof press, wood chop, etc.) later.

Exercises that were listed as alternatives for the same slot in the routine
(e.g. "barbell row or dumbbell row or seated cable row", "leg press or
walking lunges") share one capability rather than getting a separate leaf
each — same pattern Push-ups already uses via its `variations` concept.

Only Push-ups, Pull-ups, Sit-ups and Squats have full `capability_graph.json`
entries (concepts, relationships) today, matching the existing pattern where
a capability gets fleshed out once it's actually being tracked. The new gym
lifts are registered in `competencies.json` and the skill tree now, ready to
receive XP, but don't have concepts yet — logging them is a separate piece
of work (see the note in "Weekly gym routine" below).

## Targets & scoring

Targets and per-exercise XP pools live in `fitness/engine/config.py`. XP for
a logged quantity scales linearly with how close to (or past) target you are,
capped at 2x target, so overshooting is rewarded without being unbounded.

## Weekly gym routine

`fitness/routines/weekly_routine.json` holds the weekly split (push / pull /
legs / core & cardio / mobility / rest) referenced by the Zero Command System
fitness dashboard. Edit it directly to change the plan.

Logging a gym day's completion (and awarding XP into the capabilities listed
above) isn't built yet — right now the routine is display-only. A simple
day-completion log (mark today's session done, award a flat XP amount into
that day's target capabilities) is the planned next step.

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
