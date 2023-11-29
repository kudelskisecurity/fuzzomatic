from fuzzomatic.tools import prompts
from fuzzomatic.approaches.common import llm_attempt
from fuzzomatic.tools.constants import DEFAULT_TARGET_NAME
from fuzzomatic.tools.utils import detect_crate_name
from fuzzomatic.tools.semgrep import (
    run_semgrep,
    run_semgrep_rule_file,
    get_code_via_semgrep,
)


def try_unit_tests_with_function_approach(
    codebase_dir, target_name=DEFAULT_TARGET_NAME, **_kwargs
):
    # try unit tests with associated function
    max_unit_tests = 3

    unit_tests_with_function = detect_unit_tests_with_function(
        codebase_dir, max_tests=max_unit_tests
    )
    if unit_tests_with_function is None:
        print("Failed to detect unit tests with function")
        return

    # sort unit tests by their length (use shortest first)
    augmented_unit_tests = sorted(
        unit_tests_with_function,
        key=lambda x: len(x[0]) + len(x[1]) + len(x[2]) + len(x[3]),
    )

    i = 1
    for (
        test_function_source_code,
        additional_function_code,
        additional_function_name,
        use_statements,
    ) in augmented_unit_tests:
        print(f"TRYING UNIT TEST {i}/{max_unit_tests}")
        print("=" * 40)
        i += 1
        print("Using unit test with additional function:")
        print("--- (use statements)")
        for use_stmt in use_statements:
            print(use_stmt)
        print("---")
        print(test_function_source_code)
        print("---")
        print(additional_function_code)
        print("---")

        prompt = prompts.unit_test_prompt_with_additional_function(
            test_function_source_code, additional_function_name, use_statements
        )
        success, fuzz_target_path = llm_attempt(
            codebase_dir,
            prompt,
            target_name,
            remaining_attempts=0,
            additional_code=additional_function_code,
        )
        if success:
            yield fuzz_target_path


def try_unit_tests_approach(codebase_dir, target_name=DEFAULT_TARGET_NAME, **_kwargs):
    max_unit_tests = 3
    unit_tests = detect_unit_tests(codebase_dir, max_tests=max_unit_tests)

    if unit_tests is None:
        print("Failed to detect unit tests with function")
        return

    i = 1
    for test_source_code, use_statements in unit_tests[:max_unit_tests]:
        print(f"USING UNIT TEST {i}/{max_unit_tests}:")
        i += 1
        print("--- (use statements)")
        for use_stmt in use_statements:
            print(use_stmt)
        print("---")
        print(test_source_code)
        print("---")

        prompt = prompts.unit_test_prompt(test_source_code, use_statements)
        success, fuzz_target_path = llm_attempt(
            codebase_dir, prompt, target_name, remaining_attempts=0
        )
        if success:
            yield fuzz_target_path


def detect_use_statements(source_file_path, codebase_dir):
    crate_name = detect_crate_name(codebase_dir)
    ephemeral_rule = "use $USE;"

    output = run_semgrep(ephemeral_rule, source_file_path)
    use_statements = set()
    if output is not None:
        results = output["results"]
        for r in results:
            use_statement = r["extra"]["lines"]
            # replace "crate::" with the actual name of the crate in use statements
            use_statement = use_statement.replace("crate::", f"{crate_name}::")

            use_statements.add(use_statement.strip())

    # remove duplicates
    use_statements = sorted(list(use_statements))

    return use_statements


def detect_unit_tests(codebase_dir, max_tests=3):
    # run semgrep rules to identify unit tests throughout codebase
    output = run_semgrep_rule_file("semgrep/tests.yml", codebase_dir)
    if output is not None:
        results = output["results"]
        detected_tests = []

        unit_test_snippets = []
        for r in results[:max_tests]:
            test_source_code = r["extra"]["lines"]
            source_file_path = r["path"]
            unit_test_snippets.append((test_source_code, source_file_path))

        # use the shortest unit tests
        sorted_results = sorted(unit_test_snippets, key=lambda x: len(x[0]))

        for test_source_code, source_file_path in sorted_results:
            # also detect use statements to be included
            use_statements = detect_use_statements(source_file_path, codebase_dir)
            detected_tests.append((test_source_code, use_statements))

        return detected_tests

    return None


def detect_unit_tests_with_function(codebase_dir, max_tests=3):
    # run semgrep rules to identify unit tests throughout codebase
    output = run_semgrep_rule_file("semgrep/tests_with_functions.yml", codebase_dir)
    if output is not None:
        results = output["results"]

        test_snippets = []
        for r in results[:max_tests]:
            metavars = r["extra"]["metavars"]
            external_function_name = None
            test_function_name = None
            if "$F2" in metavars:
                external_function_name = metavars["$F2"]["abstract_content"]
            if "$TF" in metavars:
                test_function_name = metavars["$TF"]["abstract_content"]

            # get code for both functions
            source_file_path = r["path"]
            ephemeral_rule = (
                f"fn {test_function_name}(...) {{... {external_function_name}(...)}}"
            )
            test_function_code = get_code_via_semgrep(ephemeral_rule, source_file_path)

            ephemeral_rule = f"fn {external_function_name}(...){{...}}"
            external_function_code = get_code_via_semgrep(
                ephemeral_rule, source_file_path
            )

            # also detect use statements to be included
            use_statements = detect_use_statements(source_file_path, codebase_dir)

            if test_function_code is None or external_function_code is None:
                print(
                    "Failed to get function code with external function. "
                    "Moving to next one."
                )
                continue

            test_snippets.append(
                (
                    test_function_code,
                    external_function_code,
                    external_function_name,
                    use_statements,
                )
            )

        return test_snippets

    return None
