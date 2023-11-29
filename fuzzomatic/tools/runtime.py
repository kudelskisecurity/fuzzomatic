#!/usr/bin/env python3
import json
import os.path
import shutil
import subprocess

from fuzzomatic.tools.constants import (
    FUZZOMATIC_RESULTS_FILENAME,
    DEFAULT_MAX_TOTAL_TIME_SECONDS,
    DEFAULT_TARGET_NAME,
)


def run_fuzz_target(
    codebase_dir,
    target_name="auto",
    max_total_time_seconds=DEFAULT_MAX_TOTAL_TIME_SECONDS,
):
    cmd = [
        "cargo",
        "+nightly",
        "fuzz",
        "run",
        target_name,
        "--",
        f"-max_total_time={max_total_time_seconds}",
    ]

    try:
        env = os.environ.copy()
        env["RUSTFLAGS"] = "-A warnings"
        output = subprocess.check_output(
            cmd, cwd=codebase_dir, stderr=subprocess.STDOUT, env=env
        )
        return True, output
    except subprocess.CalledProcessError as e:
        cmd_str = " ".join(cmd)
        print(f"Failed to run command: {cmd_str}")
        return False, e.output


def is_cov_changing(error):
    lines = error.decode("utf-8").split("\n")
    previous_cov = None
    cov_changes = 0
    first_cov = None
    cov = None
    for line in lines:
        if "cov: " in line:
            cov = line.split("cov: ")[1].split(" ")[0]
            if not previous_cov == cov:
                if previous_cov is not None:
                    cov_changes += 1
                else:
                    first_cov = cov
                previous_cov = cov

    last_cov = cov

    # minimum cov change to be considered a useful target
    cov_threshold = 2
    if cov_changes >= cov_threshold:
        return True, first_cov, last_cov

    return False, first_cov, last_cov


def save_runtime_results(codebase_dir, useful, bug_found, error):
    results_file = os.path.join(codebase_dir, FUZZOMATIC_RESULTS_FILENAME)
    print(f"Loading results from json file: {results_file}")
    with open(results_file) as f:
        results_json = json.loads(f.read())

    results_json["runtime_useful"] = useful
    results_json["runtime_bug_found"] = bug_found
    results_json["runtime_error"] = error.decode("utf-8")

    with open(results_file, "w") as fout:
        print(f"Saving results to json file: {results_file}")
        fout.write(json.dumps(results_json))


def evaluate_target(
    fuzz_project_dir,
    max_total_time_seconds=DEFAULT_MAX_TOTAL_TIME_SECONDS,
):
    print(f"Evaluating target: {fuzz_project_dir}")
    success, error = run_fuzz_target(
        fuzz_project_dir, max_total_time_seconds=max_total_time_seconds
    )
    cov_changes, first_cov, last_cov = is_cov_changing(error)
    print(f"Cov changing: {cov_changes}")
    print(f"{first_cov=}")
    print(f"{last_cov=}")

    # determine panic location
    panic_pattern = "panicked at "
    panic_outside_fuzz_target = None
    lines = error.decode("utf-8").split("\n")
    for line in lines:
        if panic_pattern in line:
            if f"fuzz_targets/{DEFAULT_TARGET_NAME}.rs" in line:
                panic_outside_fuzz_target = False
                break
            else:
                panic_outside_fuzz_target = True

    # useful:
    #  * cov changes or panicks outside fuzz target
    is_useful = cov_changes or (
        panic_outside_fuzz_target is not None and panic_outside_fuzz_target
    )

    # found bug:
    #  * crashes and thread panicked not inside fuzz target (not in auto.rs)
    bug_found = not success and (
        panic_outside_fuzz_target is not None and panic_outside_fuzz_target
    )

    return is_useful, bug_found, error


def cleanup_corpus(t):
    corpus_dir = os.path.join(t, "corpus")
    if os.path.exists(corpus_dir):
        print("Cleaning up corpus dir")
        print(corpus_dir)
        shutil.rmtree(corpus_dir, ignore_errors=True)
