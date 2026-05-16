"""Vector Home Pipeline v2 — utterance → router → parser → HA bridge.

Usage:
    python -m src.pipeline "turn on the lights in the living room"
    python -m src.pipeline --interactive
    python -m src.pipeline --dry-run "set bedroom to 22 degrees"
"""
import os, sys, json, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
sys.path.insert(0, str(Path(__file__).resolve().parent))

from router import HomeRouter
from parser import HomeParser
from ha_bridge import HABridge, call_ha_sync


def process(utterance: str, router: HomeRouter, parser: HomeParser,
            ha: HABridge, verbose=True):
    """Full pipeline: route → parse → HA call."""

    # 1. Route
    tool_name, confident = router.route(utterance)
    used_fallback = False

    if not confident:
        try:
            tool_name, used_fallback = router.route_with_fallback(utterance)
            confident = True
            if verbose:
                print(f"  [fallback→Ollama] → {tool_name}")
        except Exception as e:
            if verbose:
                print(f"  [fallback failed: {e}]")
            return {"tool": "none", "error": "unroutable"}

    if tool_name == "none":
        if verbose:
            print(f"  [router] → none (not a home command)")
        return {"tool": "none", "arguments": {}}

    # 2. Parse
    if verbose:
        print(f"  [router] → {tool_name} {'(fallback)' if used_fallback else ''}")

    result = parser.parse(utterance, tool_name)
    arguments = result.get("arguments", {})
    latency = result.get("_latency_s", 0)

    if result.get("_parse_error"):
        if verbose:
            print(f"  [parser] ERROR: {result.get('_raw', '')[:80]}")

    # 3. Map to HA
    ha_service = ha.build_service_call(tool_name, arguments)

    output = {
        "tool": tool_name,
        "arguments": arguments,
        "ha_service": ha_service,
        "latency_s": latency,
        "used_fallback": used_fallback,
    }

    if verbose:
        args_str = json.dumps(arguments, separators=(", ", ": "), ensure_ascii=False)
        print(f"  [parser] → {tool_name}({args_str}) [{latency:.1f}s]")
        if ha_service:
            print(f"  [HA]     → {ha_service['domain']}.{ha_service['service']}({ha_service.get('entity_id', '')})")
            if ha_service.get("service_data"):
                print(f"  [HA]     data: {ha_service['service_data']}")

    # 4. Execute HA call (unless dry_run)
    if tool_name != "none" and ha_service:
        ha_result = call_ha_sync(tool_name, arguments,
                                 url=ha.url, token=ha.token, dry_run=ha.dry_run)
        output["ha_result"] = ha_result
        if verbose:
            if ha_result.get("dry_run"):
                print(f"  [HA]     {ha_result['message']}")
            elif ha_result.get("success"):
                print(f"  [HA]     ✓ executed")
            else:
                print(f"  [HA]     ✗ {ha_result.get('error', 'unknown error')}")

    return output


def main():
    argp = argparse.ArgumentParser(description="Vector Home Pipeline v2")
    argp.add_argument("command", nargs="*", help="Command to process")
    argp.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    argp.add_argument("--quiet", "-q", action="store_true", help="Minimal output (JSON)")
    argp.add_argument("--dry-run", action="store_true", default=True, help="Don't call HA (default: True)")
    argp.add_argument("--live", action="store_true", help="Actually call HA (overrides dry-run)")
    argp.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://homeassistant.local:8123"))
    argp.add_argument("--ha-token", default=os.environ.get("HA_TOKEN", ""))
    argp.add_argument("--weights", default=None, help="Path to GPT-2 weights file")
    argp.add_argument("--tools-spec", default=None, help="Path to tools_spec_v2.json")
    args = argp.parse_args()

    verbose = not args.quiet
    dry_run = not args.live

    if verbose:
        print("Vector Home v2 — loading...")

    router = HomeRouter()
    parser = HomeParser(weights_path=args.weights, tools_spec_path=args.tools_spec, verbose=verbose)
    ha = HABridge(url=args.ha_url, token=args.ha_token, dry_run=dry_run)

    if verbose:
        print(f"Ready ({len(router.ALL_TOOLS)} tools). {'[DRY RUN]' if dry_run else '[LIVE]'}\n")

    if args.interactive:
        print("Enter commands (Ctrl+D to exit):")
        while True:
            try:
                line = input("🏠 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break
            if not line:
                continue
            if line in ("quit", "exit", "q"):
                break
            process(line, router, parser, ha, verbose)
            print()
    elif args.command:
        utterance = " ".join(args.command)
        result = process(utterance, router, parser, ha, verbose)
        if not verbose:
            print(json.dumps(result, ensure_ascii=False))
    else:
        # Run validation suite
        from router import TEST_CASES

        if verbose:
            print("=== Validation Suite ===\n")

        correct = 0
        total = 0
        for utterance, expected in TEST_CASES:
            result = process(utterance, router, parser, ha, verbose=True)
            total += 1
            if result.get("tool") == expected:
                correct += 1
            print()

        precision = correct / total * 100 if total else 0
        print(f"\n{'='*40}")
        print(f"Result: {correct}/{total} = {precision:.0f}%")
        print(f"Stats: {router.stats}")
        print(f"HA mode: {'DRY RUN' if dry_run else 'LIVE'}")


if __name__ == "__main__":
    main()