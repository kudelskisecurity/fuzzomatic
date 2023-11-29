import os

from fuzzomatic.tools import prompts
from fuzzomatic.approaches.common import llm_attempt
from fuzzomatic.tools.constants import DEFAULT_TARGET_NAME, PARENT_README_ENABLED


def try_readme_approach(
    codebase_dir, target_name=DEFAULT_TARGET_NAME, virtual_manifest=False, **_kwargs
):
    readme_paths = detect_readme_paths(codebase_dir, parent_readme=virtual_manifest)
    if len(readme_paths) == 0:
        print("Failed to detect README")
        return

    for readme_path in readme_paths:
        print(f"README detected: {readme_path}")
        readme_contents = prompts.load_file_contents(readme_path)

        # if the readme does not contain any code snippets, skip it
        if "```" not in readme_contents:
            print(
                "Skipping readme because it does not appear "
                "to contain any code snippets"
            )
            continue

        prompt = prompts.readme_prompt(readme_contents)

        build_success, fuzz_target_path = llm_attempt(codebase_dir, prompt, target_name)

        if build_success:
            yield fuzz_target_path


def detect_readme_paths(codebase_dir, parent_readme=False):
    # search for README files in there
    paths = [
        "README.md",
        "README",
        "README.txt",
        "readme.txt",
        "README.MD",
        "BUILDING",
        "USAGE",
    ]

    # if a parent virtual manifest was detected, also try to use the parent README file
    if parent_readme and PARENT_README_ENABLED:
        paths.append("../README.md")

    readmes = []
    for path in paths:
        full_path = os.path.join(codebase_dir, path)
        if os.path.exists(full_path):
            readmes.append(full_path)

    return readmes
