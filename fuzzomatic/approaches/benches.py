from fuzzomatic.approaches.examples import try_examples_approach
from fuzzomatic.tools.constants import DEFAULT_TARGET_NAME


def try_benches_approach(codebase_dir, target_name=DEFAULT_TARGET_NAME, **kwargs):
    return try_examples_approach(
        codebase_dir, target_name=target_name, examples_dirname="benches", **kwargs
    )
