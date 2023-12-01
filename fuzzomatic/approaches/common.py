import fuzzomatic.tools.utils
from fuzzomatic.tools import llm, prompts
from fuzzomatic.tools.utils import (
    write_fuzz_target,
    build_target,
    remove_fuzz_dependency,
    add_fuzz_dependency,
)


def llm_attempt(
    codebase_dir, prompt, target_name, remaining_attempts=2, additional_code=None
):
    # read the example and feed it to the LLM
    response = llm.ask_llm(prompt)
    code_snippet = llm.extract_fuzz_target(response, codebase_dir)

    # append additional code (used in unit tests with additional code approach)
    if additional_code is not None and code_snippet is not None:
        if additional_code not in code_snippet:
            code_snippet += "\n\n"
            code_snippet += additional_code

    print("Extracted code snippet")
    print("======")
    print(code_snippet)
    fix = True

    if code_snippet is not None and "library_function(" in code_snippet:
        print("Generated call to library_function(). Moving on...")
        return False, None

    if code_snippet is not None:
        fuzz_target_path = write_fuzz_target(code_snippet, codebase_dir, target_name)
        # try to build the target
        build_success, error, built_code = build_target(codebase_dir, target_name)
    else:
        build_success = False
        fix = False
    if build_success:
        return build_success, fuzz_target_path
    else:
        # try to fix the code using the error message
        if fix:
            fix_success, error = llm_attempt_fix_error(
                codebase_dir, target_name, built_code, error, remaining_attempts=2
            )
        else:
            fix_success = False

        if fix_success:
            return fix_success, fuzz_target_path
        elif remaining_attempts > 0:
            return llm_attempt(
                codebase_dir,
                prompt,
                target_name,
                remaining_attempts - 1,
                additional_code=additional_code,
            )
        else:
            # no more remaining attempts
            return False, None


def llm_attempt_fix_error(
    codebase_dir, target_name, code_snippet, error, remaining_attempts=2
):
    # try to fix missing cargo dependencies deterministically
    build_success, error, code_snippet = add_missing_cargo_dependencies(
        codebase_dir, error, code_snippet, target_name
    )
    if build_success:
        fuzz_target_path = write_fuzz_target(code_snippet, codebase_dir, target_name)
        return True, fuzz_target_path
    else:
        print("Failed to fix cargo dependencies. Resuming...")

    fix_prompt = prompts.fix_prompt(code_snippet, error)
    print("Asking LLM to fix the code...")
    response = llm.ask_llm(fix_prompt)
    print("Response:")
    print(response)
    code_snippet = llm.extract_fuzz_target(response, codebase_dir)
    print("Extracted code snippet")
    print("======")
    print(code_snippet)
    fix = True

    if code_snippet is not None:
        fuzz_target_path = write_fuzz_target(code_snippet, codebase_dir, target_name)
        # try to build the target
        build_success, error, built_code = build_target(codebase_dir, target_name)
    else:
        build_success = False
        error = None
        remaining_attempts = 0
        fix = False

    if build_success:
        return build_success, fuzz_target_path
    elif remaining_attempts > 0:
        if fix:
            print("Failed to fix the code. Retrying...")
            return llm_attempt_fix_error(
                codebase_dir,
                target_name,
                built_code,
                error,
                remaining_attempts=remaining_attempts - 1,
            )
        else:
            print("None snippet detected")
            return False, None
    else:
        print("Failed to fix the code and no more remaining attempts")
        return False, None


def add_missing_cargo_dependencies(codebase_dir, error, code_snippet, target_name):
    cant_find_crate_pattern = "can't find crate for `"
    unresolved_import_pattern = "unresolved import `"
    no_matching_package_found = "no matching package found"
    searched_package_name = "searched package name: `"

    crate_name = fuzzomatic.tools.utils.detect_crate_name(codebase_dir)

    expected_modules = ["libfuzzer_sys", crate_name]

    if no_matching_package_found in error:
        print("Trying to remove dependency to causes build failure")
        lines = error.split("\n")
        for line in lines:
            if searched_package_name in line:
                splits = line.split("`")
                module_name = splits[1].strip()
                print("Detected module name: ", module_name)

                if module_name not in expected_modules:
                    remove_fuzz_dependency(codebase_dir, module_name)

    if cant_find_crate_pattern in error:
        print("Trying to fix can't find crate for error")
        lines = error.split("\n")
        for line in lines:
            if cant_find_crate_pattern in line:
                # extract unresolved import name
                splits = line.split("`")
                module_name = splits[1].strip()
                print("Detected module name: ", module_name)

                if module_name not in expected_modules:
                    source_line = f"extern crate {module_name};"
                    code_snippet = code_snippet.replace(source_line, "")
                    print(f"Rewriting fuzz target without {source_line}")
                    write_fuzz_target(code_snippet, codebase_dir, target_name)

                    # try to build with fix
                    build_success, error, built_code = build_target(
                        codebase_dir, target_name
                    )
                    if build_success:
                        return build_success, error, built_code
    else:
        print("Could not detect any superfluous extern crate statements")

    if unresolved_import_pattern in error:
        print("Trying to fix cargo dependencies")
        lines = error.split("\n")
        for line in lines:
            if unresolved_import_pattern in line:
                # extract unresolved import name
                splits = line.split("`")
                module_name = splits[1].strip()

                # remove anything after "::"
                if "::" in module_name:
                    module_name = module_name.split("::")[0]
                # check whether missing dependency is different
                # from libfuzzer_sys and the module's name
                if module_name not in expected_modules:
                    dependency = f"{module_name}@*"
                    module_add_success = add_fuzz_dependency(codebase_dir, dependency)
                    if not module_add_success:
                        # retry with underscore change:
                        # if module name contains "_", replace them with "-"
                        module_name = module_name.replace("_", "-")
                        dependency = f"{module_name}@*"
                        _ = add_fuzz_dependency(codebase_dir, dependency)
    else:
        print("Could not detect any fixable cargo dependencies")

    # build target again and check output
    build_success, error, built_code = build_target(codebase_dir, target_name)

    return build_success, error, built_code
