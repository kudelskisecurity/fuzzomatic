import copy
import glob
import json
import os
import subprocess


def parse_item(index, it, path):
    functions = []

    if it["visibility"] != "public":
        return []

    if "module" in it["inner"]:
        module = it["inner"]["module"]
        module_name = it["name"]
        path.append(module_name)
        funcs = parse_module(index, module, path)
        functions.extend(funcs)
    elif "import" in it["inner"]:
        imp = it["inner"]["import"]
        funcs = parse_import(index, imp, path)
        functions.extend(funcs)
    elif "struct" in it["inner"]:
        struct = it["inner"]["struct"]
        struct_name = it["name"]
        path.append(struct_name)
        funcs = parse_struct(index, struct, path)
        functions.extend(funcs)
    elif "function" in it["inner"]:
        funcs = parse_function(index, it, path)
        functions.extend(funcs)

    return functions


def parse_function(index, it, path):
    functions = []
    if "function" in it["inner"] and it["visibility"] == "public":
        function_name = it["name"]
        function_decl = it["inner"]["function"]["decl"]
        inputs = function_decl["inputs"]

        args = []
        for arg in inputs:
            argument_name = arg[0]
            extra = arg[1]
            if argument_name != "self":
                arg_type = determine_arg_type(index, extra)
                args.append(arg_type)
            else:
                args.append("self")
        functions.append((path, function_name, args))
    return functions


def determine_arg_type(index, extra):
    arg_type = "unknown"

    if "borrowed_ref" in extra:
        borrowed_ref = extra["borrowed_ref"]
        typ = borrowed_ref["type"]
        if "primitive" in typ:
            primitive_type = typ["primitive"]
            arg_type = f"&{primitive_type}"
        elif "array" in typ:
            array = typ["array"]
            if "type" in array:
                array_type = array["type"]
                if "len" in array:
                    array_length = array["len"]
                    if "primitive" in array_type:
                        array_primitive_type = array_type["primitive"]
                        arg_type = ("&array", array_primitive_type, array_length)
        elif "slice" in typ:
            slice = typ["slice"]
            if "primitive" in slice:
                primitive_type = slice["primitive"]
                arg_type = f"&[{primitive_type}]"
    elif "primitive" in extra:
        arg_type = extra["primitive"]
    if "resolved_path" in extra:
        resolved_path = extra["resolved_path"]
        path_id = resolved_path["id"]
        name = resolved_path["name"]
        try:
            _ = index[path_id]
        except KeyError:
            if name == "String":
                # Arg of type String, but not a custom String type
                arg_type = "String"

    return arg_type


def parse_struct(index, struct, path):
    functions = []
    impls = struct["impls"]
    for impl in impls:
        impl = index[impl]
        items = impl["inner"]["impl"]["items"]
        for item in items:
            item = index[item]
            funcs = parse_item(index, item, copy.deepcopy(path))
            functions.extend(funcs)

    return functions


def parse_module(index, module, path):
    functions = []
    for item in module["items"]:
        it = index[item]
        funcs = parse_item(index, it, copy.deepcopy(path))
        functions.extend(funcs)
    return functions


def parse_import(index, imp, path):
    functions = []
    ref = imp["id"]
    try:
        child_elem = index[ref]
        funcs = parse_item(index, child_elem, path)
    except KeyError:
        funcs = []
    functions.extend(funcs)
    return functions


def parse_cargo_doc_json(path):
    with open(path) as f:
        jso = json.loads(f.read())

    # get functions that take only one parameter and that are public
    root = jso["root"]
    index = jso["index"]
    root_elem = index[root]
    root_inner_items = root_elem["inner"]["module"]["items"]

    functions = []

    for elem in root_inner_items:
        path = []
        e = index[elem]
        funcs = parse_item(index, e, path)
        functions.extend(funcs)

    return functions


def generate_cargo_doc_json(codebase_dir):
    cmd = [
        "cargo",
        "+nightly",
        "rustdoc",
        "--lib",
        "--",
        "--output-format",
        "json",
        "-Z",
        "unstable-options",
        "-A",
        "rustdoc::all",
    ]

    json_file_path = None

    try:
        subprocess.check_call(cmd, cwd=codebase_dir)
        target = os.path.join(codebase_dir, "target", "doc")
        for f in glob.glob(f"{target}/*.json"):
            json_file_path = f
    except subprocess.CalledProcessError:
        print("Error: failed to generate cargo doc json")

    return json_file_path
