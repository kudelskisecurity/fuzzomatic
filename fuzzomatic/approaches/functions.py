from jinja2 import Template

import fuzzomatic.tools.utils
from fuzzomatic.tools import prompts
from fuzzomatic.approaches.common import llm_attempt_fix_error
from fuzzomatic.tools.cargo_doc import parse_cargo_doc_json, generate_cargo_doc_json
from fuzzomatic.tools.constants import DEFAULT_TARGET_NAME
from fuzzomatic.tools.utils import write_fuzz_target, build_target


def try_functions_approach(
    codebase_dir,
    target_name=DEFAULT_TARGET_NAME,
    root_codebase_dir=None,
    args=None,
    **_kwargs,
):
    functions = find_target_functions_via_cargo_doc(
        codebase_dir, root_codebase_dir=root_codebase_dir
    )

    if functions is None:
        print("Failed to detect functions")
        return

    ordered_functions = score_functions(functions)

    print(f"{len(ordered_functions)} functions detected")
    print("Detected target functions:")
    for f in ordered_functions:
        print(f)

    max_functions = 8  # try max N functions
    max_negative_score_functions = 2
    negative_score_functions = 0
    for f in ordered_functions[:max_functions]:
        path = f[0]
        function_name = f[1]
        score = f[3]

        # skip functions matching deny list
        if args is not None and args.functions_denylist is not None:
            skip_function = False
            fully_qualified_function_name = "::".join(path)
            if len(fully_qualified_function_name) > 0:
                fully_qualified_function_name += "::"
            fully_qualified_function_name += function_name
            for word in args.functions_denylist:
                if word in fully_qualified_function_name:
                    skip_function = True
            if skip_function:
                print(
                    f"Skipping function {fully_qualified_function_name} "
                    f"because of deny list: {args.functions_denylist}"
                )
                continue

        print("Attempting function:")
        print(f)

        if score <= 0:
            negative_score_functions += 1

        success, fuzz_target_path = try_function(f, codebase_dir, target_name)

        if success:
            yield fuzz_target_path

        if negative_score_functions >= max_negative_score_functions:
            break


def score_functions(functions):
    interesting_function_names = ["parse", "load", "read", "str", "eval"]
    # order functions by most interesting first
    ordered_functions = []
    for f in functions:
        function_name = f[1]
        args = f[2]
        priority = 0

        is_name_interesting = False
        for pattern in interesting_function_names:
            if pattern in function_name:
                is_name_interesting = True

        if len(args) == 1:
            arg_type = args[0]

            if arg_type == "&str":
                priority = 100
            elif arg_type == "&[u8]":
                priority = 100
            elif arg_type == "String":
                priority = 100
            elif arg_type == "bool":
                priority = 0
            elif arg_type == "unknown":
                priority = 10
            elif type(arg_type) == tuple and arg_type[0] == "&array":
                priority = 100
            elif is_name_interesting:
                priority = 100

                if args[0] == "self":
                    priority = -15
            elif args[0] == "self":
                # functions with "self" as first argument
                priority = -50
            else:
                priority = 50
        elif len(args) > 1:
            known_types = 0
            for arg in args:
                if arg != "unknown":
                    known_types += 1
            if known_types == len(args):
                priority = 30
                if "&str" in args or "&[u8]" in args or "String" in args:
                    priority = 75
                if any(type(arg) == tuple and arg[0] == "&array" for arg in args):
                    priority = 75
            else:
                # functions with multiple arguments where not all types are known
                priority = -10

            if args[0] == "self":
                # functions with "self" as first argument
                priority = -50
        else:
            # skip functions with no arguments
            priority = -100

        # give low priority to functions that are likely to load something by filename
        if "file" in function_name and arg_type == "&str":
            priority = 0

        augmented_function = [*f, priority]
        ordered_functions.append(augmented_function)
    ordered_functions = sorted(ordered_functions, key=lambda x: x[3], reverse=True)
    return ordered_functions


def try_function(f, codebase_dir, target_name):
    crate_name = fuzzomatic.tools.utils.detect_crate_name(codebase_dir)

    str_template_path = "templates/fuzz_target/fuzz_target_str.j2"
    string_template_path = "templates/fuzz_target/fuzz_target_string.j2"
    byte_slice_template_path = "templates/fuzz_target/fuzz_target_byte_array.j2"
    primitive_template_path = "templates/fuzz_target/fuzz_target_primitive.j2"
    bool_template_path = "templates/fuzz_target/fuzz_target_bool.j2"
    template_paths = {
        "&str": str_template_path,
        "String": string_template_path,
        "&[u8]": byte_slice_template_path,
        "bool": bool_template_path,
        "unknown": str_template_path,
    }

    function_args = f[2]

    template_path = str_template_path
    extra_args = {}
    if len(function_args) == 1:
        try:
            function_arg_type = function_args[0]
            template_path = template_paths[function_arg_type]
        except KeyError:
            byte_array_length_template_path = (
                "templates/fuzz_target/fuzz_target_byte_array_length.j2"
            )
            if type(function_arg_type) == tuple:
                if function_arg_type[0] == "&array":
                    primitive_type = function_arg_type[1]
                    size = function_arg_type[2]
                    if primitive_type == "u8":
                        template_path = byte_array_length_template_path
                        extra_args = dict(array_length=size)
            elif function_arg_type != "unknown":
                # try the primitive type template
                template_path = primitive_template_path
    elif len(function_args) > 1:
        template_path = "templates/fuzz_target/multiple_args/base.j2"
        literal_args = []
        struct_lifetime_needed = False
        for arg in function_args:
            if type(arg) == tuple and arg[0] == "&array":
                primitive_type = arg[1]
                size = arg[2]
                struct_type = f"[{primitive_type}; {size}]"
                call_prefix = "&"
                literal_args.append((struct_type, call_prefix))
            else:
                if arg.startswith("&"):
                    struct_lifetime_needed = True
                struct_type = arg.replace("&", "&'a ")
                call_prefix = ""
                literal_args.append((struct_type, call_prefix))
        print("Literal args:")
        print(literal_args)
        extra_args = dict(
            args=literal_args, struct_lifetime_needed=struct_lifetime_needed
        )

    success, fuzz_target_path = try_with_template(
        template_path, codebase_dir, target_name, f, crate_name, extra_args
    )
    if success:
        return True, fuzz_target_path

    return False, None


def try_with_template(
    template_path, codebase_dir, target_name, f, crate_name, extra_args
):
    path = f[0]
    function_name = f[1]
    arg_type = f[2]
    print(f"{arg_type=}")
    if len(arg_type) == 1:
        arg_type = arg_type[0]
    import_path = ""
    if len(path) > 0:
        import_path += "::"
        import_path += "::".join(path)
    elif len(path) == 0:
        import_path += f"::{function_name}"
    usage_path = ""
    if len(path) > 0:
        usage_path = path[-1] + "::"
    usage_path += function_name

    print(f"{import_path=}")
    print(f"{usage_path=}")

    t = Template(prompts.load_file_contents(template_path))
    fuzz_target_code = t.render(
        crate_name=crate_name,
        function_name=function_name,
        import_path=import_path,
        usage_path=usage_path,
        arg_type=arg_type,
        **extra_args,
    )
    fuzz_target_path = write_fuzz_target(fuzz_target_code, codebase_dir, target_name)
    success, error, built_code = build_target(codebase_dir, target_name)

    print("Generated code:")
    print("-" * 10)
    print(built_code)
    print("-" * 10)

    if success:
        return True, fuzz_target_path
    else:
        print("Failed to build target")
        print("Error:")
        print(error)

        # ask LLM to fix the code
        fix_success, error = llm_attempt_fix_error(
            codebase_dir, target_name, built_code, error
        )

        if fix_success:
            return True, fuzz_target_path

    return False, None


def find_target_functions_via_cargo_doc(codebase_dir, root_codebase_dir=None):
    json_path = generate_cargo_doc_json(
        codebase_dir, root_codebase_dir=root_codebase_dir
    )
    if json_path is not None:
        print(f"Using cargo doc file: {json_path}")
        functions = parse_cargo_doc_json(json_path)
        return functions
    else:
        return []
