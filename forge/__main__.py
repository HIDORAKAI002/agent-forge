from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Agent Forge — a full-screen terminal-native agent workstation")
    parser.add_argument("--project", default=str(Path.cwd()), help="Trusted project folder (defaults to current directory)")
    commands = parser.add_subparsers(dest="command")
    memory = commands.add_parser("memory", help="Shared project memory")
    memory_commands = memory.add_subparsers(dest="operation", required=True)
    listing = memory_commands.add_parser("list")
    listing.add_argument("--query", default="")
    add = memory_commands.add_parser("add")
    add.add_argument("--text", required=True)
    add.add_argument("--kind", choices=["fact", "decision", "handoff"], default="handoff")
    add.add_argument("--author", default="agent")
    commands.add_parser("mcp", help="Shared project stdio MCP server")
    doctor = commands.add_parser("doctor", help="List harnesses or check secret-free setup readiness")
    doctor.add_argument("--full", action="store_true", help="Read-only dependency and readiness report")
    doctor.add_argument("--probe-ollama", action="store_true", help="Probe local Ollama only; no auth or generation")
    doctor.add_argument("--probe-isolation", action="store_true", help="Run a bounded Linux kernel-isolation startup check")
    doctor.add_argument("--require", choices=["core","local","local_coding","isolation"], help="Exit nonzero unless this readiness gate passes")
    ruflo = commands.add_parser("ruflo", help="Permission-gated pinned upstream MCP tools")
    ruflo.add_argument("operation", choices=["tools", "run"])
    ruflo.add_argument("--requests-file", help="JSON array of explicit {tool, arguments} requests")
    ruflo.add_argument("--approve", help="Exact review digest printed by the preview; permits listed side effects")
    args = parser.parse_args(argv)
    if args.command == "ruflo" and args.operation == "run" and not args.requests_file:
        parser.error("ruflo run requires --requests-file")
    try:
        if args.command == "ruflo":
            import asyncio
            from .ruflo_tools import cli
            try:
                return asyncio.run(cli(args.project, args.operation, args.requests_file, args.approve))
            except ValueError:
                raise
            except Exception:
                # SDK errors may quote argument values; do not emit raw traces.
                raise ValueError("Ruflo gateway failed or timed out; no rollback is claimed. Check pinned runtime, grants and schemas. No unrestricted fallback was used.") from None
        elif args.command == "memory":
            store = Store(args.project)
            try:
                result = store.memories(args.query) if args.operation == "list" else store.remember(args.text, args.kind, args.author, False)
                print(json.dumps(result, indent=2))
            finally:
                store.close()
        elif args.command == "mcp":
            from .mcp_server import serve
            serve(args.project)
        elif args.command == "doctor" and (args.full or args.probe_ollama or args.probe_isolation or args.require):
            from .health import diagnose
            report=diagnose(args.project,ollama=args.probe_ollama,isolation=args.probe_isolation)
            print(json.dumps(report,indent=2))
            return 1 if args.require and not report['ready_for'][args.require] else 0
        elif args.command == "doctor":
            from .profiles import profiles
            store = Store(args.project)
            try:
                print(json.dumps([dict(id=p.id, label=p.label, installed=p.available, task_mode=bool(p.task_argv), tier=p.tier) for p in profiles(store.project).values()], indent=2))
            finally:
                store.close()
        else:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                parser.error("The full-screen interface needs an interactive terminal. Use memory, doctor or mcp for scripted work.")
            from .tui import ForgeApp
            app = ForgeApp(args.project)
            try:
                app.run()
            finally:
                app.runtime.close()
    except (ValueError, OSError, ImportError) as error:
        print(f"Agent Forge: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
