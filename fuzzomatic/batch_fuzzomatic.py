#!/usr/bin/env python3
import argparse
import datetime
import glob
import os
import sys

from fuzzomatic.main import get_parser as fuzzomatic_parser
from fuzzomatic.main import main as fuzzomatic_main


def get_parser():
    parser = argparse.ArgumentParser(
        prog="batch-fuzzomatic",
        usage="Run fuzzomatic on all codebases in the specified directory.",
    )
    parser.add_argument("targets_dir", help="Directory containing codebases to target")
    parser.add_argument(
        "--run",
        action="store_true",
        dest="run",
        help="Run the generated fuzz target. "
        "Note that running arbitrary code generated by AI is insecure.",
    )
    parser.add_argument(
        "--backtrack",
        action="store_true",
        dest="backtrack",
        help="If the build is successful, but at runtime, "
        "we determine that the target is not useful, "
        "backtrack and attempt the approaches that haven't been tried yet, "
        "until all approaches have been tried"
        "or a useful target is generated.",
    )
    return parser


def get_targets(targets_dir):
    dirs = glob.glob(targets_dir + "/*")
    return dirs


def run_fuzzomatic(codebase_dir, run, backtrack):
    fparser = fuzzomatic_parser()
    args = fparser.parse_args(["foobar"])
    args.codebase_dir = codebase_dir

    if run:
        args.run = True

    if backtrack:
        args.backtrack = True

    print()
    print("*" * 80)
    print("Calling fuzzomatic:")
    print(f"{codebase_dir=}")
    print(f"{run=}")
    print(f"{backtrack=}")
    fuzzomatic_main(args=args)


def main():
    parser = get_parser()
    args = parser.parse_args()
    backtrack = args.backtrack
    run = args.run

    targets_dir = args.targets_dir
    print(targets_dir)

    if not os.path.exists(targets_dir):
        print(f"[ERROR] path does not exist: {targets_dir}")
        sys.exit(-1)

    very_start = datetime.datetime.utcnow()
    targets = get_targets(targets_dir)
    total_targets = len(targets)

    # initial run
    print("Starting initial run loop")
    for i, t in enumerate(targets):
        print(f"Running fuzzomatic on target {i + 1}/{total_targets}: {t}")
        run_fuzzomatic(t, run, backtrack)

    very_end = datetime.datetime.utcnow()
    total_duration = very_end - very_start
    print(f"Total duration: {total_duration}")


if __name__ == "__main__":
    main()
