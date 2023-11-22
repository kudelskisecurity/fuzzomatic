#!/usr/bin/env python3

import argparse

from fuzzomatic.approaches.functions import score_functions
from fuzzomatic.tools.cargo_doc import parse_cargo_doc_json


def get_parser():
    prog_name = "docparse"
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Parse cargo doc json and print public functions",
    )
    parser.add_argument(
        "json_path",
        help="Path to cargo doc json file",
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    functions = parse_cargo_doc_json(args.json_path)
    ordered_functions = score_functions(functions)
    for f in ordered_functions:
        print(f)


if __name__ == "__main__":
    main()
