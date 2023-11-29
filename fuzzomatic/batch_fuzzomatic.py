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
        "--stop-on",
        dest="stop_on",
        default="bug",
        help="Stop on can be one of `building`, `useful` or `bug`. "
        "`building` means stop when a building fuzz target was generated."
        "`useful` means stop when a useful fuzz target was generated."
        "`bug` means stop when a bug is found. ",
    )
    parser.add_argument(
        "--max-fuzz-targets",
        dest="max_fuzz_targets",
        type=int,
        default=1,
        help="Stop if `max_fuzz_targets` fuzz targets match the "
        "`stop_on` condition for this code base."
        "For example, if max_fuzz_targets is 2 and stop_on is bug, "
        "we will stop as soon as 2 bugs are found.",
    )

    return parser


def get_targets(targets_dir):
    dirs = glob.glob(targets_dir + "/*")
    return dirs


def run_fuzzomatic(codebase_dir, run_on, max_fuzz_targets):
    fparser = fuzzomatic_parser()
    args = fparser.parse_args(["foobar"])
    args.codebase_dir = codebase_dir

    args.run_on = run_on
    args.max_fuzz_targets = max_fuzz_targets

    print()
    print("*" * 80)
    print("Calling fuzzomatic:")
    print(f"{codebase_dir=}")
    print(f"{run_on=}")
    print(f"{max_fuzz_targets=}")
    fuzzomatic_main(args=args)


def main():
    parser = get_parser()
    args = parser.parse_args()
    run_on = args.run_on
    max_fuzz_targets = args.max_fuzz_targets

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
        run_fuzzomatic(t, run_on, max_fuzz_targets)

    very_end = datetime.datetime.utcnow()
    total_duration = very_end - very_start
    print(f"Total duration: {total_duration}")


if __name__ == "__main__":
    main()
