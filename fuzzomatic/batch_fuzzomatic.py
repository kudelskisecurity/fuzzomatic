#!/usr/bin/env python3

import argparse
import datetime
import glob
import os
import sys

from fuzzomatic.main import get_parser as fuzzomatic_parser, add_parser_shared_arguments
from fuzzomatic.main import main as fuzzomatic_main


def get_parser():
    parser = argparse.ArgumentParser(
        prog="batch-fuzzomatic",
        usage="Run fuzzomatic on all codebases in the specified directory.",
    )
    parser.add_argument("targets_dir", help="Directory containing codebases to target")
    parser = add_parser_shared_arguments(parser)

    return parser


def get_targets(targets_dir):
    dirs = glob.glob(targets_dir + "/*")
    return dirs


def run_fuzzomatic(codebase_dir, fz_batch_args):
    fparser = fuzzomatic_parser()
    args = fparser.parse_args(["foobar"])
    args.codebase_dir = codebase_dir

    # pass arguments from fz-batch down to fz
    skip_args = ["targets_dir"]
    for arg_name, arg_value in vars(fz_batch_args).items():
        if arg_name not in skip_args:
            setattr(args, arg_name, arg_value)

    print()
    print("*" * 80)
    print("Calling fuzzomatic:")
    for arg_name, arg_value in vars(args).items():
        print(f"{arg_name}={arg_value}")
    fuzzomatic_main(args=args)


def main():
    parser = get_parser()
    args = parser.parse_args()

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
        run_fuzzomatic(t, args)

    very_end = datetime.datetime.utcnow()
    total_duration = very_end - very_start
    print(f"Batch total duration: {total_duration}")


if __name__ == "__main__":
    main()
