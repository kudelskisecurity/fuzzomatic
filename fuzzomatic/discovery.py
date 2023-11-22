#!/usr/bin/env python3

import argparse
import json
import math
import os
import time

import requests

from fuzzomatic.tools.constants import FUZZOMATIC_RESULTS_FILENAME
from fuzzomatic.tools.utils import git_clone, get_codebase_name

OSS_FUZZ_PROJECTS = []
if len(OSS_FUZZ_PROJECTS) == 0:
    oss_fuzz_csv_filename = "oss-fuzz-projects.csv"
    here = os.path.dirname(os.path.realpath(__file__))
    oss_fuzz_csv_path = os.path.join(here, os.path.pardir, oss_fuzz_csv_filename)

    with open(oss_fuzz_csv_path) as f:
        for line in f:
            line = line.strip()
            if len(line) > 0:
                name, git_url = line.split(",")
                OSS_FUZZ_PROJECTS.append((name, git_url))


def find_rust_projects_on_github(query, page=1):
    url = "https://api.github.com/search/repositories"
    per_page = 100
    params = {
        "q": f"language:rust {query}",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }

    try:
        # Send a GET request to the GitHub API
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()

        # Extract and return the list of repositories
        repositories = data.get("items", [])

        total_count = data["total_count"]
        total_pages = int(math.ceil(total_count / per_page))
        if page < total_pages:
            print("Sleeping...")
            time.sleep(10)
            print("Getting next page")
            next_repos = find_rust_projects_on_github(query, page=page + 1)
            repositories.extend(next_repos)

        return repositories

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return []


def clone_projects(projects, dest, maxprojects=0):
    total_projects = len(projects)
    for i, repo in enumerate(projects):
        name = repo["name"]
        clone_url = repo["clone_url"]
        clone_dest = os.path.join(dest, name)

        if maxprojects > 0 and (i + 1) > maxprojects:
            break

        print(f"Repo {i + 1}/{total_projects}")
        if os.path.exists(clone_dest):
            # skip this repo because the directory already exists locally
            print(f"Skipping repo: {name}")
            continue

        print(f"Cloning git repo: {clone_url}")
        time.sleep(5)
        _ = git_clone(clone_url, dest)


def is_project_to_be_skipped(codebase_dir, git_url, verbose=False):
    name = get_codebase_name(codebase_dir)
    is_fuzzed = is_project_already_fuzzed(codebase_dir)
    is_in_oss_fuzz = is_project_covered_by_oss_fuzz(name, git_url)

    if is_fuzzed or is_in_oss_fuzz:
        if verbose:
            print("Repo is already being fuzzed or part of oss-fuzz")
            print(f"Fuzzed: {is_fuzzed}")
            print(f"In oss-fuzz: {is_in_oss_fuzz}")
        return True
    return False


def is_project_already_fuzzed(codebase_dir):
    # dir "fuzz" or dir "afl" exists?
    fuzz_dir = os.path.join(codebase_dir, "fuzz")
    afl_dir = os.path.join(codebase_dir, "afl")

    fuzz_dir_exists = os.path.exists(fuzz_dir) and os.path.isdir(fuzz_dir)
    afl_dir_exists = os.path.exists(afl_dir) and os.path.isdir(afl_dir)
    autofuzz_done = False
    results_filepath = os.path.join(codebase_dir, FUZZOMATIC_RESULTS_FILENAME)

    if os.path.exists(results_filepath):
        with open(results_filepath) as f:
            jso = json.loads(f.read())
            if "outcome_reason" in jso:
                outcome_reason = jso["outcome_reason"]
                if outcome_reason != "project_already_fuzzed":
                    # project was autofuzzed previously and not fuzzed before that
                    autofuzz_done = True

    # also check the parent directory for results file
    if not autofuzz_done:
        parent_results_file_path = os.path.join(
            codebase_dir, "..", FUZZOMATIC_RESULTS_FILENAME
        )
        if os.path.exists(parent_results_file_path):
            with open(parent_results_file_path) as f:
                jso = json.loads(f.read())
                if "outcome_reason" in jso:
                    outcome_reason = jso["outcome_reason"]
                    if outcome_reason != "project_already_fuzzed":
                        # project was autofuzzed previously and not fuzzed before that
                        autofuzz_done = True

    if (fuzz_dir_exists and not autofuzz_done) or afl_dir_exists:
        return True

    return False


def is_project_covered_by_oss_fuzz(name, git_url):
    if git_url is not None and git_url.endswith(".git"):
        git_url = git_url.replace(".git", "")

    for project_name, clone_url in OSS_FUZZ_PROJECTS:
        if git_url is not None:
            if clone_url == git_url:
                return True
        elif name == project_name:
            return True

    return False


def load_repos(query):
    projects_json_path = "projects.json"
    if os.path.exists(projects_json_path):
        print("Loading projects from local file")
        with open(projects_json_path) as f:
            projects = json.loads(f.read())
    else:
        print("Getting projects via Github API")
        projects = find_rust_projects_on_github(query)
        with open(projects_json_path, "w+") as fout:
            print("Dumping to file")
            json.dump(projects, fout)

    return projects


def get_parser():
    prog_name = "discovery"
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Discover and git clone projects on Github "
        "for automated fuzzing with fuzzomatic",
    )
    parser.add_argument(
        "--target-dir",
        dest="target_dir",
        default="git-repos",
        help="Directory in which to git clone repositories",
    )
    parser.add_argument(
        "--query",
        dest="query",
        default="parser library",
        help="Github API search query. "
        "Note that 'language:rust' is always prepended to the query.",
    )
    parser.add_argument(
        "--max-projects",
        dest="max_projects",
        type=int,
        default=250,
        help="Maximum number of projects to git clone. 0 means unlimited.",
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    projects = load_repos(args.query)

    for p in projects:
        full_name = p["full_name"]
        clone_url = p["clone_url"]
        print(full_name)
        print(clone_url)
    print(f"Total projects: {len(projects)}")

    print("---")
    print("Cloning projects")
    destination = args.target_dir
    clone_projects(projects, destination, maxprojects=args.max_projects)

    print("Projects available at:")
    print(destination)


if __name__ == "__main__":
    main()
