import glob
import os

from fuzzomatic.tools import prompts
from fuzzomatic.approaches.common import llm_attempt
from fuzzomatic.tools.constants import DEFAULT_TARGET_NAME


def try_examples_approach(
    codebase_dir,
    target_name=DEFAULT_TARGET_NAME,
    examples_dirname="examples",
    **_kwargs,
):
    example_paths = detect_example_paths(codebase_dir, examples_dirname)

    if example_paths is None:
        print("Failed to detect examples")
        return

    if examples_dirname == "examples":
        print("Examples detected.")
    elif examples_dirname == "benches":
        print("Benches detected")

    max_examples = 5
    example_snippets = []
    for example_path in example_paths[:max_examples]:
        print(f"Using example {example_path}")
        with open(example_path) as f:
            example_code = f.read()
            example_snippets.append(example_code)

    # use shortest examples first
    example_snippets = sorted(example_snippets, key=lambda x: len(x))

    for example_code in example_snippets:
        prompt = prompts.example_prompt(example_code)
        success, fuzz_target_path = llm_attempt(
            codebase_dir, prompt, target_name, remaining_attempts=1
        )
        if success:
            yield fuzz_target_path


def detect_example_paths(codebase_dir, examples_dirname):
    examples_dir = os.path.join(codebase_dir, examples_dirname)
    if os.path.exists(examples_dir):
        pattern = f"{examples_dir}/**.rs"
        examples = glob.glob(pattern)
        print(examples)
        if len(examples) > 0:
            return examples
    return None
