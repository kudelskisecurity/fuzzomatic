#!/usr/bin/env python3

import argparse
import collections
import datetime
import glob
import json
import os.path
import statistics
import sys

from fuzzomatic.tools.constants import FUZZOMATIC_RESULTS_FILENAME


def get_parser():
    prog_name = "fuzzomatic-results"
    parser = argparse.ArgumentParser(
        prog=prog_name, description="Evaluate results of a batch fuzzomatic run"
    )
    parser.add_argument(
        "fuzz_projects_dir",
        help="Path to the directory containing all the codebases that were autofuzzed",
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        action="store_true",
        help="Show verbose output (including generated fuzz target code)",
    )
    parser.add_argument(
        "--useful",
        dest="useful",
        action="store_true",
        help="Show verbose output, useful targets only",
    )
    parser.add_argument(
        "--bug-found",
        dest="bug_found",
        action="store_true",
        help="Show verbose output, bug found targets only",
    )
    parser.add_argument(
        "--build-failure",
        dest="build_failure",
        action="store_true",
        help="Show verbose output, build failure targets only",
    )
    parser.add_argument(
        "--not-useful",
        dest="not_useful",
        action="store_true",
        help="Show verbose output, not useful targets only",
    )

    return parser


def read_results(fuzz_projects_dir):
    results = []

    # check if it's a single codebase directory
    root_fuzzomatic_results_file = os.path.join(
        fuzz_projects_dir, FUZZOMATIC_RESULTS_FILENAME
    )
    if os.path.exists(root_fuzzomatic_results_file):
        with open(root_fuzzomatic_results_file) as f:
            jso = json.loads(f.read())
            results.append(jso)
            return results

    dirs = glob.glob(f"{fuzz_projects_dir}/*")
    for codebase_dir in dirs:
        results_file_path = os.path.join(codebase_dir, FUZZOMATIC_RESULTS_FILENAME)
        if os.path.exists(results_file_path):
            with open(results_file_path) as f:
                jso = json.loads(f.read())
                results.append(jso)
    return results


def histogram(xs, col1="Col44", col2="Count", col3="Percentage"):
    def print_aligned_row(col1, col2, col3):
        print(f"{col1:<25} {col2:<5} {col3:<4}")

    uniq_elements = set(xs)
    total_count = len(xs)
    by_most_common = sorted(uniq_elements, key=xs.count, reverse=True)
    # print header
    print_aligned_row(col1, col2, col3)
    print_aligned_row("---", "---", "---")
    for e in by_most_common:
        elem = str(e)
        elem_count = xs.count(e)
        percent = round(100 * elem_count / total_count)
        percent = f"{percent}%"
        print_aligned_row(elem, elem_count, percent)


def print_xy(
    xys,
    x="Category",
    y="Value",
    col3="Percentage",
    other_columns=[],
    reverse=True,
    key=lambda x: x[1],
    print_transform=lambda x: x,
):
    def print_aligned_row(x, y, col3, *rest):
        line = f"{x:<25} {y:<15} {col3:<10}"
        if len(rest) > 0:
            for col in rest:
                line += f" {col:<25}"
        print(line)

    total_count = sum(key(val) for val in xys)

    ordered = sorted(xys, key=key, reverse=reverse)
    # print header
    print_aligned_row(x, y, col3, *other_columns)
    rest = ["---"] * len(other_columns)
    print_aligned_row("---", "---", "---", *rest)
    for row in ordered:
        category, number, *rest = row
        if total_count == 0:
            percent = 0
        else:
            percent = round(100 * number / total_count)
        percent = f"{percent}%"
        printed_number = print_transform(number)
        print_aligned_row(category, printed_number, percent, *rest)


def print_category(xys, x="Category", y="Category2"):
    def print_aligned_row(x, y):
        line = f"{str(x):<25} {str(y):<15} "
        print(line)

    print_aligned_row(x, y)
    print_aligned_row("---", "---")
    for row in xys:
        category, category2 = row
        print_aligned_row(category, category2)


def strip_libfuzzer_error(runtime_error):
    lines = runtime_error.split("\n")
    kept_lines = []
    skip = True
    for line in lines:
        if "thread" in line and "panicked" in line:
            skip = False

        if not skip:
            kept_lines.append(line)

    stripped_error = "\n".join(kept_lines)
    return stripped_error


def print_aligned(*cols, spacing=25, spacings=None):
    line = ""
    for i, col in enumerate(cols):
        if spacings is None:
            sp = spacing
        else:
            sp = spacings[i]
        line += f"{str(col):<{sp}}"
    print(line)


def min_max_stats(values):
    if len(values) > 0:
        print("Median:", statistics.median(values))
        print("Average", statistics.mean(values))
        print("Min", min(values))
        print("Max", max(values))
        total = sum(values)
        print("Total", total)
    else:
        print("No values")


def show_runtime_duration_stats(durations):
    print("Median runtime:", datetime.timedelta(seconds=statistics.median(durations)))
    print("Average runtime", datetime.timedelta(seconds=statistics.mean(durations)))
    print("Min runtime", datetime.timedelta(seconds=min(durations)))
    print("Max runtime", datetime.timedelta(seconds=max(durations)))
    total_duration_seconds = sum(durations)
    total_duration = datetime.timedelta(seconds=total_duration_seconds)
    print("Total runtime", total_duration)


def main():
    parser = get_parser()
    args = parser.parse_args()

    fuzz_dir = args.fuzz_projects_dir
    if not os.path.exists(fuzz_dir):
        print(f"[Error] Path does not exist: {fuzz_dir}")
        sys.exit(-1)

    results = read_results(fuzz_dir)
    if len(results) == 0:
        print(f"No results available in directory: {fuzz_dir}")
        sys.exit(-1)

    successes = 0
    failures = 0
    total_outcomes = 0
    outcome_reasons = []
    durations = []
    success_durations = []
    fuzz_targets = []
    approach_prices = {}
    projects_with_durations = []

    building_targets = []
    useful_targets = []
    bug_found_targets = []
    no_approach_worked_targets = []

    print("*" * 80)
    print("Projects covered:")
    print("*" * 80)
    print()

    # print column headers
    titles = [
        "Project",
        "Build",
        "Reason",
        "Useful",
        "Bug found",
        "Successful approaches",
    ]
    spacings = [30, 16, 25, 9, 12, 25]
    print_aligned(*titles, spacings=spacings)
    separators = ["-" * max(3, sp - 3) for sp in spacings]
    print_aligned(*separators, spacings=spacings)

    # print rows
    for r in results:
        total_outcomes += 1
        name = r["name"]
        outcome_reason = r["outcome_reason"]
        success = "SUCCESS" if outcome_reason == "success" else "[*FAILURE*]"
        generated_fuzz_targets = r["generated_fuzz_targets"]
        successful_approaches = set()
        bugs_found = 0
        usefuls = 0
        for fuzz_target in generated_fuzz_targets:
            successful_approach = fuzz_target["successful_approach"]
            successful_approaches.add(successful_approach)

            is_useful = fuzz_target["is_useful"]
            bug_found = fuzz_target["bug_found"]

            if bug_found:
                bugs_found += 1
            if is_useful:
                usefuls += 1

        print_aligned(
            name,
            success,
            outcome_reason,
            usefuls,
            bugs_found,
            successful_approaches,
            spacings=spacings,
        )

    print("")

    successful_approaches_building = []
    successful_approaches_useful = []
    successful_approaches_bug_found = []
    usefuls = []
    has_building = []
    has_useful = []
    bugs_found = []
    has_bug_found = []
    for r in results:
        name = r["name"]
        codebase_dir = r["codebase_dir"]

        # outcome reason
        outcome_reason = r["outcome_reason"]
        outcome_reasons.append(outcome_reason)
        if outcome_reason == "no_approach_worked":
            no_approach_worked_targets.append(codebase_dir)

        # successful approaches
        if outcome_reason == "success":
            successes += 1

        # duration
        duration_seconds = round(float(r["duration_seconds"]), 5)
        durations.append(duration_seconds)
        if outcome_reason == "success":
            success_durations.append(duration_seconds)
        projects_with_durations.append((name, duration_seconds))

        # fuzz targets
        generated_fuzz_targets = r["generated_fuzz_targets"]
        contains_building = False
        contains_useful = False
        contains_bug_found = False
        for ft in generated_fuzz_targets:
            contains_building = True
            fuzz_targets.append(ft["fuzz_target_code"])

            # runtime metrics
            useful = ft["is_useful"]
            bug_found = ft["bug_found"]

            if useful:
                contains_useful = True
            if bug_found:
                contains_bug_found = True

            building_targets.append(codebase_dir)

            approach = ft["successful_approach"]
            successful_approaches_building.append(approach)

            if useful:
                useful_targets.append(codebase_dir)
                successful_approaches_useful.append(approach)
                usefuls.append(name)

            if bug_found:
                git_url = r["git_url"]
                bug_found_targets.append((codebase_dir, git_url))
                bugs_found.append(name)
                successful_approaches_bug_found.append(approach)

        has_building.append(contains_building)
        has_useful.append(contains_useful)
        has_bug_found.append(contains_bug_found)

    # build per approach stats
    approach_total_tokens = []
    approach_in_tokens = []
    approach_out_tokens = []
    approach_llm_calls = []
    for approach_name, v in approach_prices.items():
        total_tokens = v["total_tokens"]
        in_tokens = v["in_tokens"]
        out_tokens = v["out_tokens"]
        llm_calls = v["llm_calls"]

        approach_total_tokens.append((approach_name, total_tokens))
        approach_in_tokens.append((approach_name, in_tokens))
        approach_out_tokens.append((approach_name, out_tokens))
        approach_llm_calls.append((approach_name, llm_calls))

    # print results
    print("BUILD METRICS")
    print("=" * 20)

    success_percent = round(100 * successes / total_outcomes, 1)
    print(f"Total outcomes: {total_outcomes}")
    print(f"Successes: {successes}/{total_outcomes} ({success_percent}%)")
    print(f"Failures: {failures}/{total_outcomes}")

    print()
    histogram(outcome_reasons, col1="Outcome reason")

    print()
    histogram(successful_approaches_building, col1="Building approach")

    print()
    histogram(successful_approaches_useful, col1="Useful approach")

    print()
    histogram(successful_approaches_bug_found, col1="Bug found approach")

    print()
    print("Runtime durations (all)")
    show_runtime_duration_stats(durations)
    print()
    print("Runtime durations (successes only)")
    show_runtime_duration_stats(success_durations)

    print()
    rounded_durations_to_minutes = [round(d / 60, 0) for d in durations]
    histogram(rounded_durations_to_minutes, "Build time (rounded to minute)")

    print()
    print("Per project stats")
    print("*" * 60)

    print()
    print_xy(
        projects_with_durations,
        x="Project",
        y="Duration",
        print_transform=lambda x: str(datetime.timedelta(seconds=x)),
    )

    print()
    print()
    print("RUNTIME METRICS")
    print("=" * 20)

    print()
    histogram(has_building, col1="Code bases w/ Building")

    print()
    histogram(has_useful, col1="Code bases w/ Useful")

    print()
    histogram(has_bug_found, col1="Code bases w/ Bugs")

    print()
    print()
    print("Building targets:")
    building_counter = collections.Counter(building_targets)
    for t, count in building_counter.items():
        print(f"{t} ({count})")

    print()
    print("Useful targets:")
    useful_counter = collections.Counter(useful_targets)
    for t, count in useful_counter.items():
        print(f"{t} ({count})")

    print()
    print("Bug found in targets:")
    bug_counter = collections.Counter(bug_found_targets)
    for (codebase_dir, git_url), count in bug_counter.items():
        print(f"{codebase_dir} ({count})")

    print()
    print("Bug found in targets (git URLs):")
    for (codebase_dir, git_url), count in bug_counter.items():
        print(f"{git_url} ({count})")

    print()
    print("Targets where no approach worked:")
    for t in no_approach_worked_targets:
        print(t)

    if args.verbose:
        print()
        print()
        print("FUZZ TARGETS")
        print("=" * 20)

        for i, r in enumerate(results):
            build_success = r["outcome_reason"] == "success"
            name = r["name"]
            has_useful = False
            has_bug_found = False
            has_not_useful = False
            generated_fuzz_targets = r["generated_fuzz_targets"]
            for ft in generated_fuzz_targets:
                useful = ft["is_useful"]
                bug_found = ft["bug_found"]
                if useful:
                    has_useful = True
                if bug_found:
                    has_bug_found = True
                if not useful:
                    has_not_useful = True

            if args.bug_found and not has_bug_found:
                continue
            if args.useful and not has_useful:
                continue
            if args.build_failure and build_success:
                continue
            if args.not_useful and not has_not_useful:
                continue

            # print code base header
            print("*" * 30)
            print(f"CODE BASE {i + 1}/{len(results)}")
            print(f"{name=}")
            print("*" * 30)

            for j, ft in enumerate(generated_fuzz_targets):
                useful = ft["is_useful"]
                bug_found = ft["bug_found"]
                successful_approach = ft["successful_approach"]
                fuzz_target_code = ft["fuzz_target_code"]
                fuzz_target_path = ft["fuzz_target_path"]

                show = True

                if args.bug_found:
                    show = False
                    if bug_found is not None and bug_found:
                        show = True
                elif args.useful:
                    show = False
                    if useful is not None and useful:
                        show = True
                elif args.build_failure:
                    show = False
                    if not build_success:
                        show = True
                elif args.not_useful:
                    show = False
                    if useful is not None and not useful:
                        show = True

                if show:
                    print()
                    print(f"FUZZ TARGET {j + 1}/{len(generated_fuzz_targets)}")
                    print("=" * 10)
                    print(f"{name=}")
                    git_url = r["git_url"]
                    print(f"{git_url=}")
                    print(f"{fuzz_target_path=}")
                    print(f"{successful_approach=}")
                    print(f"{useful=}")
                    print(f"{bug_found=}")
                    print("----")
                    print(fuzz_target_code)
                    print("----")
                    if bug_found:
                        runtime_error = ft["error"]
                        stripped_runtime_error = strip_libfuzzer_error(runtime_error)
                        print(stripped_runtime_error)
                        print("----")

                    print()


if __name__ == "__main__":
    main()
