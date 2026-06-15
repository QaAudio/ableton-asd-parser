from __future__ import annotations

from dataclasses import dataclass, field


# Primitive member type tags observed in the Live 11+ v6 schema dictionary.
# Names are descriptive; the parser stores the raw tag and does not depend on
# an exhaustive mapping (unknown tags are preserved as-is).
PRIMITIVE_TAGS: dict[int, str] = {
    0x10: "bool",
    0x11: "int32",
    0x12: "float64",
    0x17: "double",
    0x31: "blob",
    0x32: "floatArray",
    0x35: "doubleArray",
    0x40: "doubleArray2",
}


@dataclass(frozen=True)
class TypeRef:
    """Reference to a named schema type or a primitive tag."""

    name: str | None = None
    primitive: int | None = None

    @property
    def is_primitive(self) -> bool:
        return self.primitive is not None

    @property
    def label(self) -> str:
        if self.name is not None:
            return self.name
        if self.primitive is not None:
            return PRIMITIVE_TAGS.get(self.primitive, f"prim:{self.primitive:#x}")
        return "unknown"


@dataclass(frozen=True)
class SchemaMember:
    """One field of a schema type: a name and the type it points to."""

    name: str
    type_ref: TypeRef


@dataclass(frozen=True)
class SchemaType:
    """A type defined in the ASD schema dictionary.

    `is_collection` marks list/array container types, which carry a negative
    count marker and no member list.
    """

    name: str
    members: tuple[SchemaMember, ...]
    offset: int = 0
    is_collection: bool = False
    raw_count: int = 0


@dataclass
class SchemaGraph:
    """Parsed schema: header version, the declared types, and region bounds."""

    types: dict[str, SchemaType] = field(default_factory=dict)
    root: str = "SampleData"
    version: int | None = None
    schema_start: int = 0
    schema_end: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def type_names(self) -> list[str]:
        return sorted(self.types, key=lambda name: self.types[name].offset)

    @property
    def member_names(self) -> list[str]:
        names: set[str] = set()
        for schema_type in self.types.values():
            for member in schema_type.members:
                names.add(member.name)
        return sorted(names)
