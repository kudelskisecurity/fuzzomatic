#!/usr/bin/env python3

import argparse
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
    outcomes = []
    outcome_reasons = []
    successful_approaches = []
    successful_approaches_no_none = []
    durations = []
    success_durations = []
    total_llm_calls = []
    fuzz_targets = []
    usefuls = []
    bugs_found = []
    total_tokens_counts = []
    approach_prices = {}
    projects_with_total_tokens = []
    projects_with_durations = []
    projects_with_price_estimation = []
    projects_with_price_estimation_all = []
    projects_with_price_estimation_successes = []
    projects_with_most_costly_approach = []
    total_estimated_price = 0

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
        "Successful approach",
        "Useful",
        "Bug found",
    ]
    spacings = [30, 16, 25, 25, 9, 9]
    print_aligned(*titles, spacings=spacings)
    separators = ["-" * max(3, sp - 3) for sp in spacings]
    print_aligned(*separators, spacings=spacings)

    # print rows
    for r in results:
        name = r["name"]
        outcome = r["outcome"]
        success = "SUCCESS" if outcome is True else "[*FAILURE*]"
        outcome_reason = r["outcome_reason"]
        successful_approach = r["successful_approach"]
        useful = None
        bug_found = None
        if "runtime_useful" in r:
            useful = r["runtime_useful"]
        if "runtime_bug_found" in r:
            bug_found = r["runtime_bug_found"]
        print_aligned(
            name,
            success,
            outcome_reason,
            successful_approach,
            useful,
            bug_found,
            spacings=spacings,
        )

    print("")

    for r in results:
        name = r["name"]
        codebase_dir = r["codebase_dir"]
        # outcome
        outcome = r["outcome"]
        outcomes.append(outcome)
        total_outcomes += 1
        if outcome is True:
            successes += 1
        else:
            failures += 1

        # outcome reason
        outcome_reason = r["outcome_reason"]
        outcome_reasons.append(outcome_reason)
        if outcome is not True and outcome_reason == "no_approach_worked":
            no_approach_worked_targets.append(codebase_dir)

        # successful approaches
        successful_approach = r["successful_approach"]
        successful_approaches.append(successful_approach)
        if outcome is True:
            successful_approaches_no_none.append(successful_approach)

        # duration
        duration_seconds = round(float(r["duration_seconds"]), 5)
        durations.append(duration_seconds)
        if outcome is True:
            success_durations.append(duration_seconds)
        projects_with_durations.append((name, duration_seconds))

        # llm calls
        total_llm_calls.append(r["total_llm_calls"])

        # total tokens
        total_tokens = r["total_tokens"]
        total_tokens_counts.append(total_tokens)
        projects_with_total_tokens.append((name, total_tokens))

        tried_approaches = r["tried_approaches"]
        project_total_price = 0
        approach_with_highest_cost = None
        max_cost = 0
        for approach_name, outcome, usage in tried_approaches:
            in_tokens = usage["prompt_tokens"]
            out_tokens = usage["completion_tokens"]
            total_tokens = usage["total_tokens"]
            llm_calls = usage["llm_calls"]

            # estimated pricing
            # pricing for 4K context GPT-3.5 Turbo per 1K tokens (in and out)
            gpt_35_turbo_input_per_1k = 0.0015
            gpt_35_turbo_output_per_1k = 0.002
            in_tokens_price = gpt_35_turbo_input_per_1k * in_tokens / 1000
            out_tokens_price = gpt_35_turbo_output_per_1k * out_tokens / 1000
            approach_price = in_tokens_price + out_tokens_price
            project_total_price += approach_price

            if approach_price > max_cost:
                max_cost = approach_price
                approach_with_highest_cost = approach_name

            if approach_name not in approach_prices:
                approach_stats = {
                    "in_tokens": in_tokens,
                    "out_tokens": out_tokens,
                    "total_tokens": total_tokens,
                    "llm_calls": llm_calls,
                }
                approach_prices[approach_name] = approach_stats
            else:
                approach_stats = approach_prices[approach_name]
                approach_stats["in_tokens"] += in_tokens
                approach_stats["out_tokens"] += out_tokens
                approach_stats["total_tokens"] += total_tokens
                approach_stats["llm_calls"] += llm_calls
                approach_prices[approach_name] = approach_stats

        total_estimated_price += project_total_price
        projects_with_price_estimation.append((name, round(project_total_price, 2)))
        projects_with_price_estimation_all.append(round(project_total_price, 2))

        if outcome is True:
            projects_with_price_estimation_successes.append(
                round(project_total_price, 2)
            )
        projects_with_most_costly_approach.append((name, approach_with_highest_cost))

        # fuzz targets
        fuzz_targets.append(r["fuzz_target_code"])

        # runtime metrics
        if "runtime_useful" in r:
            useful = r["runtime_useful"]
            usefuls.append(useful)
            bug_found = r["runtime_bug_found"]
            bugs_found.append(bug_found)

            if useful:
                useful_targets.append(codebase_dir)
            if bug_found:
                git_url = r["git_url"]
                bug_found_targets.append((codebase_dir, git_url))

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
    histogram(successful_approaches, col1="Successful approach")

    print()
    histogram(successful_approaches_no_none, col1="Successful approach (No None)")

    print()
    print("Costs stats (all)")
    min_max_stats(projects_with_price_estimation_all)

    print()
    print("Costs stats (successes only)")
    min_max_stats(projects_with_price_estimation_successes)

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
    avg_llm_calls = round(statistics.mean(total_llm_calls), 2)
    print(f"Average LLM calls per codebase: {avg_llm_calls}")

    print()
    print("Per approach stats")
    print("*" * 60)

    print()
    print_xy(approach_total_tokens, x="Approach", y="Total tokens")
    print()
    print_xy(approach_in_tokens, x="Approach", y="In tokens")
    print()
    print_xy(approach_out_tokens, x="Approach", y="Out tokens")
    print()
    print_xy(approach_llm_calls, x="Approach", y="LLM calls")

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
    print_xy(projects_with_total_tokens, x="Project", y="Total tokens")

    print()
    print_xy(projects_with_price_estimation, x="Project", y="Costs (USD)")

    print()
    print_category(
        projects_with_most_costly_approach, x="Project", y="Most costly approach"
    )

    print()
    print()
    print("RUNTIME METRICS")
    print("=" * 20)
    print()
    histogram(usefuls, col1="Useful fuzz targets")

    print()
    histogram(bugs_found, col1="Bug found")

    print()
    print()
    print("Useful targets:")
    for t in useful_targets:
        print(t)

    print()
    print("Bug found in targets:")
    for codebase_dir, git_url in bug_found_targets:
        print(codebase_dir)

    print()
    print("Bug found in targets (git URLs):")
    for codebase_dir, git_url in bug_found_targets:
        print(git_url)

    print()
    print("Targets where no approach worked:")
    for t in no_approach_worked_targets:
        print(t)

    print()
    print(f"Total estimated price: {round(total_estimated_price, 2)} USD")

    if args.verbose:
        print()
        print()
        print("FUZZ TARGETS")
        print("=" * 20)

        for i, r in enumerate(results):
            fuzz_target = r["fuzz_target_code"]
            build_success = r["outcome"] is True
            name = r["name"]
            successful_approach = r["successful_approach"]
            useful = None
            bug_found = None

            if "runtime_useful" in r:
                useful = r["runtime_useful"]
                bug_found = r["runtime_bug_found"]

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
                print(f"TARGET {i + 1}/{len(results)}")
                print("=" * 10)
                print(name)
                git_url = r["git_url"]
                print(git_url)
                print(f"{successful_approach=}")
                print(f"{useful=}")
                print(f"{bug_found=}")
                print("----")
                print(fuzz_target)
                print("----")
                if bug_found:
                    runtime_error = r["runtime_error"]
                    stripped_runtime_error = strip_libfuzzer_error(runtime_error)
                    print(stripped_runtime_error)
                    print("----")

                print()


if __name__ == "__main__":
    main()
