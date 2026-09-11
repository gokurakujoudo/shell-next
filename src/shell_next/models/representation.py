"""Bounded diagnostic representations shared by public records and live objects."""

from dataclasses import Field, fields
from enum import Enum
from reprlib import Repr
from typing import Any, ClassVar

__all__ = ["RecordRepr", "describe"]
"""Internal reusable representation tools; the package root exports public models only."""

PREVIEW_BYTES = 32
"""Package-selected byte preview length, bounding escape expansion while showing useful output."""


class RecordRepr:
    """Give dataclasses a bounded field representation, honoring repr=False fields."""

    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    def __repr__(self) -> str:
        """Describe stored fields without changing them or opening resources.

        :returns: Named fields with bounded payloads, collections, and nesting.
        """
        return PREVIEW.repr(self)


class DiagnosticRepr(Repr):
    """Extend standard-library bounds to records, byte payloads, and enum names."""

    def repr1(self, value: object, level: int) -> str:
        """Format nested records using the same depth budget as their collections.

        :param value: Stored value to describe.
        :param level: Remaining nesting depth, shared with reprlib.
        :returns: A bounded description with hidden record fields omitted.
        """
        if isinstance(value, RecordRepr):
            if level <= 0:
                return f"{type(value).__name__}(...)"
            parts = (
                f"{item.name}={self.repr1(getattr(value, item.name), level - 1)}"
                for item in fields(value)
                if item.repr
            )
            return f"{type(value).__name__}({', '.join(parts)})"
        if isinstance(value, Enum):
            return f"{type(value).__name__}.{value.name}"
        if isinstance(value, bytes):
            if len(value) > PREVIEW_BYTES:
                return f"{value[:PREVIEW_BYTES]!r}... ({len(value)} bytes)"
            return repr(value)
        return super().repr1(value, level)


PREVIEW = DiagnosticRepr(maxlevel=3, maxstring=80, maxother=80, maxtuple=4, maxlist=4, maxdict=4)
"""Package display policy: three nesting levels, four collection entries, and 80 text characters.

These limits keep diagnostics readable; they never change capture or stored values.
"""


def describe(value: object, **attributes: object) -> str:
    """Format explicitly selected in-memory state for objects that are not records.

    :param value: Object supplying the displayed class name.
    :param attributes: Safe named values chosen by the caller.
    :returns: Class name followed by bounded state fields, without an object address.
    """
    parts = (f"{name}={PREVIEW.repr(item)}" for name, item in attributes.items())
    return f"{type(value).__name__}({', '.join(parts)})"
