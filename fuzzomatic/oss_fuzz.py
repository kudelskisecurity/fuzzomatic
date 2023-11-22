#!/usr/bin/env python3

import glob
import os
import tempfile

from fuzzomatic.tools.utils import git_clone


def main():
    url = "https://github.com/google/oss-fuzz.git"
    with tempfile.TemporaryDirectory() as t:
        print("Cloning oss-fuzz...")
        git_clone(url, t)
        print("Building list...")
        build_oss_fuzz_list(os.path.join(t, "oss-fuzz"))
        print("Done.")


def build_oss_fuzz_list(oss_fuzz_dir):
    projects_dir = os.path.join(oss_fuzz_dir, "projects")

    with open("oss-fuzz-projects.csv", "w+") as fout:
        for directory in glob.glob(f"{projects_dir}/*"):
            project_name = os.path.basename(directory)
            project_yaml_file = os.path.join(directory, "project.yaml")
            with open(project_yaml_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("main_repo:"):
                        main_repo = line.replace("main_repo: ", "")
                        main_repo = main_repo.replace('"', "")
                        main_repo = main_repo.replace("'", "")
                        main_repo = main_repo.replace(
                            "http://github.com", "https://github.com"
                        )

            print(f"{project_name},{main_repo}", file=fout)


if __name__ == "__main__":
    main()
