"""Persistence layer (Step 4a/4b).

Domain models + repository interfaces + a SQLite-backed store. Everything above
this package touches state only through the repository interfaces (principle 9),
so swapping SQLite for Postgres later is a single-layer change.
"""
