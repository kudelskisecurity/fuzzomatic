#!/usr/bin/env python3
import copy
import glob
import json
import os
import subprocess

import toml

from fuzzomatic.tools.semgrep import run_semgrep_rule_file


def get_codebase_name(codebase_dir):
    if codebase_dir.endswith("/"):
        return os.path.basename(os.path.dirname(codebase_dir))
    else:
        return os.path.basename(codebase_dir)


def autofix_unwrap_calls(target_path):
    print("Fixing unwrap calls...")
    initial_fuzz_target_code = load_fuzz_target(target_path)

    # workaround replacement for semgrep
    # semgrep currently cannot match expressions inside macro calls
    temp_start_block = "fuzz_target() {"
    temp_end_block = "} // });"
    fuzz_start_block = "fuzz_target!(|data: &[u8]| {"
    fuzz_end_block = "});"

    if (
        fuzz_start_block not in initial_fuzz_target_code
        or fuzz_end_block not in initial_fuzz_target_code
    ):
        print("Aborting unwrap autofix...")
        return

    fuzz_target_code = initial_fuzz_target_code.replace(
        fuzz_start_block, temp_start_block, 1
    )
    fuzz_target_code = fuzz_target_code.replace(fuzz_end_block, temp_end_block, 1)

    with open(target_path, "w+") as fout:
        fout.write(fuzz_target_code)

    run_semgrep_rule_file("semgrep/fix_unwrap.yml", target_path, autofix=True)

    fixed_fuzz_target = load_fuzz_target(target_path)
    fixed_fuzz_target = fixed_fuzz_target.replace(temp_start_block, fuzz_start_block, 1)
    fixed_fuzz_target = fixed_fuzz_target.replace(temp_end_block, fuzz_end_block, 1)

    fixed_fuzz_target = fixed_fuzz_target.replace("let if let", "if let")

    with open(target_path, "w+") as fout:
        fout.write(fixed_fuzz_target)


def load_fuzz_target(target_path):
    with open(target_path) as f:
        initial_fuzz_target_code = f.read()
    return initial_fuzz_target_code


def autofix_fuzz_target(target_path):
    print("Sanitizing fuzz target using semgrep autofix...")
    run_semgrep_rule_file("semgrep/fix_empty_functions.yml", target_path, autofix=True)

    # autofix unwrap() calls
    autofix_unwrap_calls(target_path)
    print("Autofixing done.")


def rustfmt_target(target_path):
    cmd = ["rustfmt", target_path]

    print(f"Running rustfmt on target: {target_path}")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("Failed to run rustfmt")


def build_target(codebase_dir, target_name):
    # sanitize fuzz target
    target_path = os.path.join(
        codebase_dir, "fuzz", "fuzz_targets", f"{target_name}.rs"
    )
    autofix_fuzz_target(target_path)

    # pretty format code
    rustfmt_target(target_path)

    # build target
    cmd = [
        "cargo",
        # force usage of nightly compiler in case there's
        # a rust toolchain override in the project
        "+nightly",
        "fuzz",
        "build",
        target_name,
    ]

    built_code = None
    with open(target_path) as f:
        built_code = f.read()

    try:
        print("Building target...")
        # do not show warnings
        env = os.environ.copy()
        env["RUSTFLAGS"] = "-A warnings"

        subprocess.check_output(
            cmd, cwd=codebase_dir, stderr=subprocess.STDOUT, env=env
        )
        print("Build success.")
        return True, None, built_code
    except subprocess.CalledProcessError as e:
        print("Failed to build fuzz target")
        error = e.output.decode("utf-8")
        print(error)
        return False, error, built_code


def git_clone(url, path):
    os.makedirs(path, exist_ok=True)

    cmd = ["git", "clone", "--recurse-submodules", url]
    try:
        env_copy = os.environ.copy()
        env_copy["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.check_output(cmd, cwd=path, stderr=subprocess.STDOUT, env=env_copy)
    except subprocess.CalledProcessError as e:
        cmd_str = " ".join(cmd)
        print(f"Failed to run command: {cmd_str}")
        print(e.output.decode("utf-8"))
        print("Failed to run git clone")
    splits = url.split("/")
    for s in splits[::-1]:  # walk in reverse
        piece = s.strip()
        if len(piece) > 0:
            codebase_name = piece
            break
    if codebase_name.endswith(".git"):
        codebase_name = codebase_name.replace(".git", "")

    print(f"codebase_name: {codebase_name}")
    codebase_dir = os.path.join(path, codebase_name)
    print(f"codebase dir: {codebase_dir}")
    return codebase_dir


def add_fuzz_dependency(codebase_dir, dependency, features=[]):
    print(f"Adding dependency {dependency}")
    cargo_toml_path = os.path.join(codebase_dir, "fuzz", "Cargo.toml")

    cmd = ["cargo", "add", "--manifest-path", cargo_toml_path, dependency]
    if len(features) > 0:
        cmd.append("--features")
        cmd.append(",".join(features))
    try:
        subprocess.check_output(cmd)
        return True
    except subprocess.CalledProcessError:
        cmd_str = " ".join(cmd)
        print(f"Failed to run command: {cmd_str}")
        return False


def remove_fuzz_dependency(codebase_dir, dependency):
    print(f"Removing dependency {dependency}")
    cargo_toml_path = os.path.join(codebase_dir, "fuzz", "Cargo.toml")

    cmd = ["cargo", "remove", "--manifest-path", cargo_toml_path, dependency]
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        cmd_str = " ".join(cmd)
        print(f"Failed to run command: {cmd_str}")


def write_fuzz_target(code_snippet, codebase_dir, target_name):
    # write snippet to file
    fuzz_target_path = build_fuzz_target_path(codebase_dir, target_name)
    with open(fuzz_target_path, "w") as fout:
        fout.write(code_snippet)

    return fuzz_target_path


def build_fuzz_target_path(codebase_dir, target_name):
    return os.path.join(codebase_dir, "fuzz", "fuzz_targets", f"{target_name}.rs")


def init_cargo_fuzz(codebase_dir, target_name):
    cmd_init = ["cargo", "fuzz", "init"]
    try:
        subprocess.check_output(cmd_init, cwd=codebase_dir, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        cmd_str = " ".join(cmd_init)
        print(f"Warning: failed to run {cmd_str}")
        error = e.output.decode("utf-8")
        if "could not read the manifest file" in error:
            print(error)
            return False
        if "is malformed" in error:
            print(error)
            return False
        if "could not find a cargo project" in error:
            print(error)
            return False

    # try to create target with cargo fuzz, in case it's the first time
    cmd_add = ["cargo", "fuzz", "add", target_name]
    try:
        subprocess.check_output(cmd_add, cwd=codebase_dir, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        pass

    return True


def expand_workspace_member(codebase_dir, member):
    members = []
    path = os.path.join(codebase_dir, member)
    for x in glob.glob(path):
        if os.path.isdir(x):
            members.append(x)
    return members


def read_workspace_members(codebase_dir):
    cargo_file = os.path.join(codebase_dir, "Cargo.toml")
    members = []
    if os.path.exists(cargo_file):
        contents = load_toml(cargo_file)
        if "workspace" in contents:
            workspace = contents["workspace"]
            if "members" in workspace:
                members = workspace["members"]
                exclude = []
                if "exclude" in workspace:
                    exclude = workspace["exclude"]

    members = expand_members(codebase_dir, members)
    exclude = expand_members(codebase_dir, exclude)

    # remove excluded members
    final_members = set(members)
    final_exclude = set(exclude)
    final = final_members - final_exclude
    final = sorted(list(final))

    return final


def expand_members(codebase_dir, members):
    expanded_members = []
    for member in members:
        if "*" in member:
            expanded = expand_workspace_member(codebase_dir, member)
            expanded_members.extend(expanded)
        else:
            expanded_members.append(os.path.join(codebase_dir, member))
    return expanded_members


def check_has_workspace_members(codebase_dir):
    cargo_file = os.path.join(codebase_dir, "Cargo.toml")
    if os.path.exists(cargo_file):
        with open(cargo_file) as f:
            workspace_found = False
            for line in f:
                line = line.strip()
                if line == "[workspace]":
                    workspace_found = True
        has_members = workspace_found
        return has_members

    return False


def check_virtual_manifest(codebase_dir):
    cargo_file = os.path.join(codebase_dir, "Cargo.toml")
    if os.path.exists(cargo_file):
        with open(cargo_file) as f:
            workspace_found = False
            package_found = False
            for line in f:
                line = line.strip()
                if line == "[workspace]":
                    workspace_found = True
                if line == "[package]":
                    package_found = True
        virtual_manifest = workspace_found and not package_found
        return virtual_manifest

    return False


def detect_git_url(codebase_dir, remote_name="origin"):
    cmd = ["git", "remote", "get-url", remote_name]
    try:
        output = subprocess.check_output(cmd, cwd=codebase_dir)
        git_url = output.decode("utf-8").strip()
        return git_url
    except subprocess.CalledProcessError:
        print("Failed to detect git URL")
        return None


def detect_crate_name(codebase_dir):
    name = os.path.basename(codebase_dir)
    cargo_toml_path = os.path.join(codebase_dir, "Cargo.toml")

    # check if the library is exported under a different name
    manifest_cmd = [
        "cargo",
        "read-manifest",
        "--manifest-path",
        cargo_toml_path,
    ]

    try:
        output = subprocess.check_output(manifest_cmd)
        jso = json.loads(output.decode("utf-8"))
        targets = jso["targets"]
        for target in targets:
            kind = target["kind"]
            src_path = target["src_path"]
            expected_ending = f"{name}/src/lib.rs"
            if "lib" in kind and src_path.endswith(expected_ending):
                exported_name = target["name"]
                exported_name = exported_name.replace("-", "_")
                return exported_name
    except subprocess.CalledProcessError:
        cmd_str = " ".join(manifest_cmd)
        print(f"Failed to run command: {cmd_str}")
        name = name.replace("-", "_")
        return name

    # should never happen
    return None


def load_toml(file_path):
    with open(file_path) as f:
        return toml.loads(f.read())


def write_toml(file_path, contents):
    with open(file_path, "w+") as fout:
        fout.write(toml.dumps(contents))


def add_parent_dependencies(codebase_dir, root_codebase_dir):
    parent_cargo_path = os.path.join(codebase_dir, "Cargo.toml")

    workspace_cargo_path = None
    if root_codebase_dir is not None:
        workspace_cargo_path = os.path.join(root_codebase_dir, "Cargo.toml")

    fuzz_cargo_path = os.path.join(codebase_dir, "fuzz", "Cargo.toml")

    parent_dependencies = {}

    # get dependencies from parent Cargo.toml
    if os.path.exists(parent_cargo_path):
        print("Reading parent Cargo.toml")
        parent_cargo = load_toml(parent_cargo_path)

        if "dependencies" in parent_cargo:
            parent_dependencies = parent_cargo["dependencies"]

            # also add dev dependencies as they may be required to run unit tests
            if "dev-dependencies" in parent_cargo:
                dev_dependencies = parent_cargo["dev-dependencies"]
                parent_dependencies.update(dev_dependencies)

            # check if grandparent workspace.dependencies exist
            if workspace_cargo_path is not None and os.path.exists(
                workspace_cargo_path
            ):
                grandparent_cargo = load_toml(workspace_cargo_path)
                if "workspace" in grandparent_cargo:
                    workspace = grandparent_cargo["workspace"]
                    if "dependencies" in workspace:
                        wdeps = workspace["dependencies"]

        # fix parent dependencies relative paths
        for k, v in parent_dependencies.items():
            if "path" in v:
                print(f"Fixing parent Cargo.toml relative path for {k}")
                path = v["path"]
                path = f"../{path}"
                v["path"] = path

        for k, v in parent_dependencies.items():
            if "workspace" in v and v["workspace"] is True:
                # update using workspace Cargo.toml
                wdep = copy.deepcopy(wdeps[k])

                if type(wdep) == str:
                    wdep = {"version": wdep}
                    wdep.update(parent_dependencies[k])
                else:
                    wdep.update(parent_dependencies[k])

                parent_dependencies[k] = wdep
                del parent_dependencies[k]["workspace"]

                # fix path if needed
                if "path" in wdep:
                    # fix workspace dependency path relative to fuzz Cargo.toml
                    wpath = wdep["path"]
                    rel_path = os.path.relpath(root_codebase_dir, codebase_dir)
                    fixed_wpath = os.path.join(rel_path, os.path.pardir, wpath)
                    parent_dependencies[k]["path"] = fixed_wpath

    else:
        print("Parent Cargo.toml does not exist")

    # add dependencies to fuzz Cargo.toml
    empty_dependencies = len(parent_dependencies) == 0
    if not empty_dependencies and os.path.exists(fuzz_cargo_path):
        fuzz_cargo = load_toml(fuzz_cargo_path)
        fuzz_cargo["dependencies"].update(parent_dependencies)
        fuzz_cargo["workspace"] = {
            "members": []
        }  # to avoid "current package believes it's in a workspace" error
        print("Writing new fuzz Cargo.toml")
        write_toml(fuzz_cargo_path, fuzz_cargo)
