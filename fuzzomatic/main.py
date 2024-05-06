#!/usr/bin/env python3

import argparse
import datetime
import json
import os.path
import subprocess
import sys

import fuzzomatic.tools.utils
from fuzzomatic.tools import utils
from fuzzomatic import discovery
from fuzzomatic.approaches import (
    try_functions_approach,
    try_examples_approach,
    try_readme_approach,
    try_benches_approach,
    try_unit_tests_approach,
    try_unit_tests_with_function_approach,
)
from fuzzomatic.tools.constants import (
    DEFAULT_TARGET_NAME,
    FUZZOMATIC_RESULTS_FILENAME,
    EXIT_NOT_A_CARGO_PROJECT,
    EXIT_PROJECT_ALREADY_FUZZED,
    EXIT_PROJECT_DOES_NOT_BUILD,
    EXIT_OPENAI_API_KEY_ERROR,
)
from fuzzomatic.tools.runtime import evaluate_target, cleanup_corpus
from fuzzomatic.tools.utils import (
    get_codebase_name,
    git_clone,
    init_cargo_fuzz,
    check_virtual_manifest,
    check_has_workspace_members,
    detect_git_url,
)


def get_parser():
    prog_name = "fuzzomatic"
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Automatically generate Rust fuzz targets from scratch",
    )
    parser.add_argument(
        "codebase_dir", help="Path to the codebase to generate a fuzz target for"
    )

    parser = add_parser_shared_arguments(parser)
    return parser


def add_parser_shared_arguments(parser):
    parser.add_argument(
        "--force",
        action="store_true",
        dest="force",
        help="Run Fuzzomatic anyway. Even if project is already covered by oss-fuzz",
    )
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
    parser.add_argument(
        "--approaches",
        nargs="+",
        dest="approaches",
        default=None,
        help="List of approaches to use",
    )
    parser.add_argument(
        "--functions-denylist",
        nargs="+",
        dest="functions_denylist",
        default=None,
        help="List of words that should not appear in target function names. "
        "Such functions will be skipped.",
    )
    parser.add_argument(
        "--workspace-members-allowlist",
        nargs="+",
        dest="workspace_members_allowlist",
        default=None,
        help="List of workspace members to process. "
        "Unspecified workspace members will be skipped.",
    )
    return parser


def save_results(
    args,
    git_url,
    generated_fuzz_targets,
    start_time,
    end_time,
    duration,
    outcome_reason,
):
    name = get_codebase_name(args.codebase_dir)

    # runtime
    duration_seconds = duration.total_seconds()

    # create results
    results_path = os.path.join(args.codebase_dir, FUZZOMATIC_RESULTS_FILENAME)

    results = {
        "codebase_dir": args.codebase_dir,
        "name": name,
        "git_url": git_url,
        "generated_fuzz_targets": generated_fuzz_targets,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "outcome_reason": outcome_reason,
    }

    # save results to file
    with open(results_path, "w+") as fout:
        fout.write(json.dumps(results))

    print(f"Saved fuzzomatic results to: {results_path}")


def get_approaches(requested_approaches):
    approaches = []
    if requested_approaches is not None:
        for name, func in ENABLED_APPROACHES:
            if name in requested_approaches:
                approaches.append((name, func))
    else:
        approaches = ENABLED_APPROACHES
    return approaches


def generate_building_fuzz_targets(
    args, codebase_dir, git_url, approaches, force=False
):
    codebase_name = get_codebase_name(codebase_dir)
    if not force:
        print(f"Checking if {codebase_name} is not already in oss-fuzz")
        if discovery.is_project_to_be_skipped(codebase_dir, git_url):
            yield "message", EXIT_PROJECT_ALREADY_FUZZED

    autofuzz_generator = autofuzz_codebase(args, codebase_dir, approaches=approaches)
    for result in autofuzz_generator:
        yield result


def ensure_dependencies_available():
    required_external_commands = [
        ("semgrep", ["semgrep"]),
        ("cargo fuzz", ["cargo", "fuzz", "help"]),
    ]

    print("Checking external dependencies...")
    for cmd_name, cmd in required_external_commands:
        try:
            subprocess.check_call(
                cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
            )
            print(f"[SUCCESS] {cmd_name}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                f"[FAILURE] {cmd_name} is a required dependency. "
                f"Fuzzomatic won't run without it."
            )
            print(
                "Make sure that the dependency is installed "
                "as explained in the README instructions"
            )
            print("Aborting...")
            sys.exit(-1)


def ensure_env_vars_set():
    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        print(
            "[ERROR] Please make sure to setup OpenAI environment variables and source the env file as explained in "
            "the README"
        )
        sys.exit(-1)


def main(args=None):
    if args is None:
        parser = get_parser()
        args = parser.parse_args()

    # check required dependencies are available
    ensure_dependencies_available()

    # check env vars set
    ensure_env_vars_set()

    very_start = datetime.datetime.utcnow()

    # if git URL, clone the repository
    git_url = None
    if args.codebase_dir.startswith("https://"):
        git_url = args.codebase_dir
        path = os.path.abspath(os.path.join(".", "git"))
        print("Code base appears to be a git URL. Trying to git clone...")
        codebase_dir = git_clone(args.codebase_dir, path)
        args.codebase_dir = codebase_dir
    else:
        git_url = detect_git_url(args.codebase_dir)

    process_codebase(args, git_url)

    very_end = datetime.datetime.utcnow()
    total_duration = very_end - very_start
    print(f"Code base total duration: {total_duration}")


def current_stats(generated_fuzz_targets):
    building = 0
    useful = 0
    bug_found = 0

    for fuzz_target in generated_fuzz_targets:
        is_useful = fuzz_target["is_useful"]
        is_bug_found = fuzz_target["bug_found"]
        building += 1
        if is_useful:
            useful += 1
        if is_bug_found:
            bug_found += 1

    return building, useful, bug_found


def process_codebase(args, git_url):
    start_time = datetime.datetime.utcnow()

    # check if results file already exists
    target_results = read_codebase_results(args.codebase_dir)
    if target_results is not None:
        print("Code base already processed by fuzzomatic. Skipping...")
        return

    approaches = get_approaches(args.approaches)

    generator = generate_building_fuzz_targets(
        args, args.codebase_dir, git_url, approaches, force=args.force
    )

    generated_fuzz_targets = []
    outcome_reason = "success"
    for building_target in generator:
        result_type, contents = building_target

        if result_type == "fuzz_target":
            fuzz_target_code, fuzz_target_path, successful_approach = contents

            fuzz_project_dir = os.path.realpath(
                os.path.join(os.path.dirname(fuzz_target_path), os.path.pardir)
            )

            # Try to run the target and evaluate it
            cleanup_corpus(fuzz_project_dir)

            is_useful, bug_found, error = evaluate_target(
                fuzz_project_dir, max_total_time_seconds=10
            )
            if bug_found:
                error = error.decode("utf-8")
            else:
                # do not store output if no bug is found
                error = None
            print(f"{is_useful=}")
            print(f"{bug_found=}")

            fuzz_target_result = {
                "fuzz_target_code": fuzz_target_code,
                "fuzz_target_path": fuzz_target_path,
                "successful_approach": successful_approach,
                "is_useful": is_useful,
                "bug_found": bug_found,
                "error": error,
            }
            generated_fuzz_targets.append(fuzz_target_result)

            # print current stats
            building, useful, bug_found = current_stats(generated_fuzz_targets)
            print()
            print("Generated fuzz targets so far for this codebase:")
            print_current_stats(args, bug_found, building, useful)

            # check stop conditions
            if args.stop_on == "building":
                if building >= args.max_fuzz_targets:
                    print("Stopping condition reached. Stopping.")
                    print(f"{building=} >= {args.max_fuzz_targets}")
                    break
            if args.stop_on == "useful":
                if useful >= args.max_fuzz_targets:
                    print("Stopping condition reached. Stopping.")
                    print(f"{useful=} >= {args.max_fuzz_targets}")
                    break
            if args.stop_on == "bug":
                if bug_found >= args.max_fuzz_targets:
                    print("Stopping condition reached. Stopping.")
                    print(f"{bug_found=} >= {args.max_fuzz_targets}")
                    break
        elif result_type == "message":
            exit_code = contents
            outcome_reason = "unknown"
            if exit_code == EXIT_NOT_A_CARGO_PROJECT:
                outcome_reason = "not_a_cargo_project"
            elif exit_code == EXIT_PROJECT_ALREADY_FUZZED:
                outcome_reason = "project_already_fuzzed"
                print(
                    "[WARNING] project is already covered "
                    "by oss-fuzz or fuzzing is in place. "
                    "Pass --force to overwrite."
                )
                print("Aborting")
            elif exit_code == EXIT_PROJECT_DOES_NOT_BUILD:
                outcome_reason = "project_does_not_build"
            elif exit_code == EXIT_OPENAI_API_KEY_ERROR:
                print("OpenAI API key not set. Aborting.")
                sys.exit(-1)
            break

    end_time = datetime.datetime.utcnow()
    duration = end_time - start_time

    if len(generated_fuzz_targets) == 0 and outcome_reason == "success":
        outcome_reason = "no_approach_worked"

    # save results to disk
    save_results(
        args,
        git_url,
        generated_fuzz_targets,
        start_time,
        end_time,
        duration,
        outcome_reason,
    )
    building, useful, bug_found = current_stats(generated_fuzz_targets)
    print()
    print("Final fuzz targets generated for this codebase:")
    print_current_stats(args, bug_found, building, useful)


def print_current_stats(args, bug_found, building, useful):
    print("*" * 50)
    print(f"{args.codebase_dir=}")
    print(f"{building=}")
    print(f"{useful=}")
    print(f"{bug_found=}")
    print("*" * 50)
    print()


def read_codebase_results(codebase_dir):
    results_file_path = os.path.join(codebase_dir, FUZZOMATIC_RESULTS_FILENAME)
    target_results = None
    if os.path.exists(results_file_path):
        with open(results_file_path) as f:
            target_results = json.loads(f.read())
    return target_results


def autofuzz_workspace(args, codebase_dir, target_name, approaches=[]):
    # identify workspace members
    members = fuzzomatic.tools.utils.read_workspace_members(codebase_dir)

    if args.workspace_members_allowlist is not None:
        final_members = []
        for member in members:
            if any([member.endswith(m) for m in args.workspace_members_allowlist]):
                final_members.append(member)
        members = final_members

    print("About to autofuzz workspace members:")
    for m in members:
        print(m)
    print()

    # run autofuzz on each workspace member
    build_failure_count = 0

    for f in members:
        # check that the subdir is not fuzzed
        is_fuzzed = discovery.is_project_already_fuzzed(f)
        if os.path.isdir(f) and not is_fuzzed:
            print(f"Retrying with workspace member: {f}")
            generator = autofuzz_codebase(
                args,
                f,
                target_name=target_name,
                virtual_manifest=True,
                approaches=approaches,
                root_codebase_dir=codebase_dir,
            )

            for result in generator:
                result_type, contents = result
                if result_type == "message" and contents == EXIT_PROJECT_DOES_NOT_BUILD:
                    build_failure_count += 1

                    if build_failure_count == len(members):
                        # all members failed to build, consider this a build failure
                        yield "message", EXIT_PROJECT_DOES_NOT_BUILD

                    continue
                else:
                    yield result


def is_project_building_by_default(codebase_dir):
    cmd = ["cargo", "check"]

    try:
        subprocess.check_call(cmd, cwd=codebase_dir)
        return True
    except subprocess.CalledProcessError as e:
        print("Project does not build by default")
        print(e)
        return False


def autofuzz_codebase(
    args,
    codebase_dir,
    target_name=DEFAULT_TARGET_NAME,
    virtual_manifest=False,
    approaches=[],
    root_codebase_dir=None,
):
    # cargo fuzz init
    cargo_fuzz_init_success = init_cargo_fuzz(codebase_dir, target_name)

    # check whether it's a virtual manifest
    is_virtual_manifest = check_virtual_manifest(codebase_dir)
    is_workspace = check_has_workspace_members(codebase_dir)

    if not cargo_fuzz_init_success and not is_virtual_manifest:
        print("Aborting... could not cargo fuzz init, and not a virtual manifest")
        # raise SystemExit(EXIT_NOT_A_CARGO_PROJECT)
        yield "message", EXIT_NOT_A_CARGO_PROJECT

    if cargo_fuzz_init_success and not is_workspace:
        project_builds = check_project_builds(codebase_dir)
        if not project_builds:
            # if the project does not build by default, don't bother
            yield "message", EXIT_PROJECT_DOES_NOT_BUILD

    if is_workspace:
        workspace_generator = autofuzz_workspace(
            args, codebase_dir, target_name=target_name, approaches=approaches
        )
        for result in workspace_generator:
            yield result

    if cargo_fuzz_init_success:
        # add dependencies from the parent Cargo.toml file to the fuzz Cargo project
        fuzzomatic.tools.utils.add_parent_dependencies(codebase_dir, root_codebase_dir)
        # also add the arbitrary crate for target functions with multiple arguments
        utils.add_fuzz_dependency(codebase_dir, "arbitrary@1", features=["derive"])

        for approach_name, approach_function in approaches:
            print("=" * 40)
            print(f"ATTEMPTING APPROACH: {approach_name}")
            print("=" * 40)

            # attempt approach
            approach_function_generator = approach_function(
                codebase_dir,
                target_name=target_name,
                virtual_manifest=virtual_manifest,
                root_codebase_dir=root_codebase_dir,
                args=args,
            )

            for result in approach_function_generator:
                fuzz_target_path = result
                with open(fuzz_target_path, "r") as f:
                    fuzz_target_code = f.read()
                yield "fuzz_target", (fuzz_target_code, fuzz_target_path, approach_name)


def check_project_builds(codebase_dir):
    print("Checking if project builds by default...")
    default_builds = is_project_building_by_default(codebase_dir)
    print(f"{default_builds=}")
    return default_builds


ENABLED_APPROACHES = [
    ("functions", try_functions_approach),
    ("readme", try_readme_approach),
    ("examples", try_examples_approach),
    ("unit_tests", try_unit_tests_approach),
    ("unit_tests_with_function", try_unit_tests_with_function_approach),
    ("benches", try_benches_approach),
]

if __name__ == "__main__":
    main()
