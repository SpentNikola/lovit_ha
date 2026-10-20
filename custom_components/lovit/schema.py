"""Compatibility layer for Home Assistant config flow schemas.

Home Assistant 2026.10 switched config flow schemas from ``voluptuous`` to
``probatio``.  Both libraries expose ``Schema`` and ``Required`` objects with
the same purpose, so the right one is selected at runtime and the rest of the
integration does not have to care about the version it runs on.
"""

from __future__ import annotations

from homeassistant import data_entry_flow as _data_entry_flow

if hasattr(_data_entry_flow, "probatio"):
    # Home Assistant 2026.10 and newer.
    import probatio as _schema
else:
    # Home Assistant 2026.9 and older.
    import voluptuous as _schema  # type: ignore[no-redef]

Schema = _schema.Schema
Required = _schema.Required

__all__ = ["Required", "Schema"]
