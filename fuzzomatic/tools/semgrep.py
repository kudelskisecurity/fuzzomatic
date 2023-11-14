import json
import os
import subprocess


def run_semgrep(ephemeral_rule, function_source_code_file_path):
    semgrep_cmd = [
        "semgrep",
        "-e",
        ephemeral_rule,
        "--lang=rust",
        function_source_code_file_path,
        "--json",
    ]
    try:
        print("Running semgrep command (ephemeral):")
        print(" ".join(semgrep_cmd))
        output = subprocess.check_output(semgrep_cmd, stderr=subprocess.DEVNULL)
        decoded_output = output.decode("utf-8")
        jso = json.loads(decoded_output)
        return jso
    except subprocess.CalledProcessError as e:
        print("Failed to run semgrep")
        print(e)
        return None


def run_semgrep_rule_file(rule_file_path, target_path, autofix=False):
    here = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    parent_dir = os.path.join(here, os.path.pardir)
    abs_rule_path = os.path.join(parent_dir, rule_file_path)
    semgrep_cmd = ["semgrep", "--config", abs_rule_path, target_path, "--json"]
    if autofix:
        semgrep_cmd.append("--autofix")

    try:
        print("Running semgrep command:")
        print(" ".join(semgrep_cmd))
        output = subprocess.check_output(semgrep_cmd, stderr=subprocess.DEVNULL)
        decoded_output = output.decode("utf-8")
        jso = json.loads(decoded_output)
        return jso
    except subprocess.CalledProcessError as e:
        print("Failed to run semgrep")
        print(e)
        return None


def get_code_via_semgrep(ephemeral_rule, source_file_path):
    output = run_semgrep(ephemeral_rule, source_file_path)
    if output is not None:
        results = output["results"]
        for r in results:
            function_code = r["extra"]["lines"]
            return function_code
    return None
