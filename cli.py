"""CLI commands for the TableStore memory provider."""

from __future__ import annotations

import json
import sys
import uuid


def _parse_metadata(values: list[str] | None) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in values or []:
        key, sep, value = item.partition("=")
        key = key.strip()
        value = value.strip()
        if not sep or not key or not value:
            raise ValueError(f"Invalid metadata item '{item}'. Expected KEY=VALUE.")
        metadata[key] = value
    return metadata


def _make_provider():
    from plugins.memory import load_memory_provider

    provider = load_memory_provider("tablestore-mem")
    if not provider:
        raise RuntimeError("TableStore provider could not be loaded.")

    provider.initialize(
        f"cli-tablestore-mem-{uuid.uuid4().hex[:8]}",
        platform="cli",
        agent_identity="hermes",
    )
    return provider


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def tablestore_command(args) -> None:
    sub = getattr(args, "tablestore_command", None)
    if sub not in {"add", "search", "doctor"}:
        print("Usage: hermes tablestore-mem <add|search|doctor>")
        sys.exit(2)
        return

    try:
        provider = _make_provider()
    except Exception as exc:
        print(f"Failed to initialize tablestore provider: {exc}")
        sys.exit(1)
        return

    try:
        if sub == "add":
            payload = {
                "content": args.content,
                "sync": bool(getattr(args, "sync_write", False)),
            }
            metadata = _parse_metadata(getattr(args, "metadata", None))
            if metadata:
                payload["metadata"] = metadata
            result = json.loads(provider.handle_tool_call("tablestore_remember", payload))
            _print_json(result)
            if isinstance(result, dict) and result.get("error"):
                sys.exit(1)
            return

        if sub == "search":
            payload = {
                "query": args.query,
                "top_k": args.top_k,
            }
            metadata = _parse_metadata(getattr(args, "metadata", None))
            if metadata:
                payload["metadata"] = metadata
            result = json.loads(provider.handle_tool_call("tablestore_search", payload))
            _print_json(result)
            if isinstance(result, dict) and result.get("error"):
                sys.exit(1)
            return

        if sub == "doctor":
            result = provider.run_doctor()
            _print_json(result)
            if isinstance(result, dict) and not result.get("ok", False):
                sys.exit(1)
            return
    except ValueError as exc:
        print(str(exc))
        sys.exit(2)
    except Exception as exc:
        print(f"TableStore command failed: {exc}")
        sys.exit(1)
    finally:
        provider.shutdown()


def register_cli(subparser) -> None:
    """Build the ``hermes tablestore-mem`` argparse tree."""
    subs = subparser.add_subparsers(dest="tablestore_command")

    add_parser = subs.add_parser("add", help="Store a memory in TableStore")
    add_parser.add_argument("content", help="Content to persist")
    add_parser.add_argument(
        "--metadata",
        action="append",
        metavar="KEY=VALUE",
        help="Optional metadata pair. Repeat for multiple values.",
    )
    add_parser.add_argument(
        "--sync",
        dest="sync_write",
        action="store_true",
        help="Wait for the write to finish before returning.",
    )
    add_parser.set_defaults(func=tablestore_command)

    search_parser = subs.add_parser("search", help="Search memories in TableStore")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum results to return (default: 5)",
    )
    search_parser.add_argument(
        "--metadata",
        action="append",
        metavar="KEY=VALUE",
        help="Optional metadata filter. Repeat for multiple values.",
    )
    search_parser.set_defaults(func=tablestore_command)

    doctor_parser = subs.add_parser("doctor", help="Run read-only diagnostics for TableStore")
    doctor_parser.set_defaults(func=tablestore_command)
