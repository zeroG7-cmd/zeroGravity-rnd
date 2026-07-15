# Operator Zero Capability Graph Blueprint

## Stable hierarchy

`Main Stat → Domain → Category → Capability`

The hierarchy answers **where a capability belongs**. It stays shallow and readable.

## Capability ecosystem

Each capability opens an ecosystem containing:

`Concepts → Learning tracks → Projects → Evidence → XP events → Relationships`

The ecosystem answers **what the capability is made of** and how it connects to other capabilities.

## Compatibility rule

Existing `competency_id` values remain the permanent IDs. The user interface calls them **capabilities**. This avoids destructive migrations while allowing the model to grow.

## XP rule

Learning units award weighted XP to capabilities using the existing engine. Concept coverage is recorded separately and can later become independently levelled without changing the top-level tree.

## Provider rule

A provider progress snapshot must match a track by `track_id` or `resource_id`. The importer must stop when no match exists; it must never offer unrelated tracks.
