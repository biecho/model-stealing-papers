#!/usr/bin/env python3
"""
Main pipeline runner.

Orchestrates the full pipeline:
1. init - Load seed papers
2. fetch - Get metadata for pending papers
3. classify - LLM classification
4. expand - Citation graph expansion
5. export - Generate output files

Can run individual steps or the full pipeline.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(script: str, args: list[str] = None, env: dict = None):
    """Run a pipeline step."""
    cmd = [sys.executable, f"scripts/pipeline/{script}.py"] + (args or [])
    print(f"\n{'='*60}", flush=True)
    print(f"Running: {' '.join(cmd)}", flush=True)
    print('='*60, flush=True)

    result = subprocess.run(cmd, env=env)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run the ML Security Papers pipeline")
    parser.add_argument("steps", nargs="*", default=["all"],
                       help="Steps to run: init, fetch, classify, expand, discover, export, all")
    parser.add_argument("--state-file", type=Path, default=Path("data/paper_state.json"))
    parser.add_argument("--limit", type=int, default=0, help="Limit items per step")
    parser.add_argument("--rate-limit", type=float, default=3.0, help="API rate limit")
    parser.add_argument("--reset", action="store_true", help="Reset state before init")
    args = parser.parse_args()

    steps = args.steps
    if "all" in steps:
        steps = ["init", "fetch", "classify", "expand", "export"]

    common_args = [
        f"--state-file={args.state_file}",
    ]
    if args.limit > 0:
        common_args.append(f"--limit={args.limit}")
    if args.rate_limit:
        common_args.append(f"--rate-limit={args.rate_limit}")

    print(f"Pipeline steps: {steps}", flush=True)

    for step in steps:
        step_args = common_args.copy()

        if step == "init":
            if args.reset:
                step_args.append("--reset")
            success = run_step("init", step_args)
        elif step == "fetch":
            success = run_step("fetch", step_args)
        elif step == "classify":
            success = run_step("classify", step_args)
        elif step == "expand":
            step_args.append("--max-depth=2")
            success = run_step("expand", step_args)
        elif step == "discover":
            step_args.append("--days=7")
            success = run_step("discover", step_args)
        elif step == "export":
            success = run_step("export", [f"--state-file={args.state_file}"])
        else:
            print(f"Unknown step: {step}", flush=True)
            continue

        if not success:
            print(f"\nStep '{step}' failed!", flush=True)
            # Continue anyway for now
            # sys.exit(1)

    print(f"\n{'='*60}", flush=True)
    print("Pipeline complete!", flush=True)
    print('='*60, flush=True)


if __name__ == "__main__":
    main()
