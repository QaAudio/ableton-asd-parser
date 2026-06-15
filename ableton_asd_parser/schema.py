from __future__ import annotations

from .reader import ByteReader
from .schema_types import SchemaGraph, SchemaMember, SchemaType, TypeRef

_MAX_NAME_LEN = 64
_MAX_MEMBERS = 256


def _looks_like_type_name(data: bytes, pos: int) -> bool:
    if pos + 2 > len(data) or data[pos] != 0:
        return False
    length = data[pos + 1]
    if length < 1 or length > _MAX_NAME_LEN:
        return False
    end = pos + 2 + length
    if end > len(data):
        return False
    return all(32 <= byte < 127 for byte in data[pos + 2 : end])


def _read_type_name(reader: ByteReader) -> str:
    if reader.u8() != 0:
        raise ValueError("expected 0x00 type-name prefix")
    return reader.ascii_pstr()


def _read_type_ref(reader: ByteReader) -> TypeRef:
    tag = reader.u8()
    if tag == 0:
        return TypeRef(name=reader.ascii_pstr())
    return TypeRef(primitive=tag)


def _read_member(reader: ByteReader) -> SchemaMember:
    char_count = reader.u32()
    if char_count < 1 or char_count > _MAX_NAME_LEN:
        raise ValueError(f"invalid member name length: {char_count}")
    name = reader.bytes(char_count * 2).decode("utf-16-le")
    if not name or not (name[0].isalpha() or name[0] == "_"):
        raise ValueError(f"implausible member name: {name!r}")
    return SchemaMember(name=name, type_ref=_read_type_ref(reader))


def _try_read_type_def(data: bytes, pos: int) -> SchemaType | None:
    """Parse one type definition at `pos`, or return None if it is not one."""
    if not _looks_like_type_name(data, pos):
        return None
    reader = ByteReader(data, pos)
    try:
        name = _read_type_name(reader)
        raw_count = reader.u32()
        signed = raw_count - 0x1_0000_0000 if raw_count >= 0x8000_0000 else raw_count
        if signed < 0:
            # Collection marker (e.g. List<...>, RemoteableList/Array): no members.
            return SchemaType(
                name=name,
                members=(),
                offset=pos,
                is_collection=True,
                raw_count=raw_count,
            )
        if signed > _MAX_MEMBERS:
            return None
        members = tuple(_read_member(reader) for _ in range(signed))
    except ValueError:
        return None
    return SchemaType(name=name, members=members, offset=pos, raw_count=raw_count)


def _consume_type_def(data: bytes, pos: int) -> tuple[SchemaType, int] | None:
    schema_type = _try_read_type_def(data, pos)
    if schema_type is None:
        return None
    reader = ByteReader(data, pos)
    _read_type_name(reader)
    reader.u32()
    if not schema_type.is_collection:
        for _ in schema_type.members:
            _read_member(reader)
    return schema_type, reader.pos


def parse_schema(data: bytes, schema_start: int) -> SchemaGraph:
    """Parse the self-describing ASD schema dictionary.

    The schema is a version header (``00 <len> SampleData <u32 version>``)
    followed by a stream of type definitions. Parsing stops at the first byte
    that is not a valid type definition; that offset is the instance-data start
    (``schema_end``).
    """
    graph = SchemaGraph(schema_start=schema_start)
    pos = schema_start

    if _looks_like_type_name(data, pos):
        header = ByteReader(data, pos)
        try:
            root_name = _read_type_name(header)
            version = header.u32()
            # A header is distinguished from a real type def: the bytes that
            # follow the version are themselves another type-name prefix.
            if _looks_like_type_name(data, header.pos):
                graph.root = root_name
                graph.version = version
                pos = header.pos
        except ValueError:
            pass

    while pos < len(data):
        consumed = _consume_type_def(data, pos)
        if consumed is None:
            break
        schema_type, pos = consumed
        if schema_type.name not in graph.types:
            graph.types[schema_type.name] = schema_type

    graph.schema_end = pos
    if graph.root not in graph.types and graph.types:
        graph.root = next(iter(graph.types))
    return graph


def scan_schema_types(data: bytes, schema_start: int) -> list[str]:
    return parse_schema(data, schema_start).type_names


def scan_property_names(data: bytes, schema_start: int) -> list[str]:
    return parse_schema(data, schema_start).member_names
