import os

from jinja2 import Template


def load_file_contents(path):
    here = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    parent_dir = os.path.join(here, os.path.pardir)

    with open(os.path.join(parent_dir, path)) as f:
        return f.read()


def readme_prompt(readme):
    t = Template(load_file_contents("templates/prompts/readme.j2"))
    prompt = t.render(readme=readme)
    return prompt


def fix_prompt(code_snippet, error):
    t = Template(load_file_contents("templates/prompts/fix_code_error.j2"))
    prompt = t.render(code_snippet=code_snippet, error=error)
    return prompt


def example_prompt(example_code):
    t = Template(load_file_contents("templates/prompts/example_code.j2"))
    prompt = t.render(example_code=example_code)
    return prompt


def unit_test_prompt(test_source_code, use_statements):
    t = Template(load_file_contents("templates/prompts/unit_test_code.j2"))
    prompt = t.render(code=test_source_code, use_statements=use_statements)
    return prompt


def unit_test_prompt_with_additional_function(
    test_function_code, additional_function_code, use_statements
):
    t = Template(
        load_file_contents(
            "templates/prompts/unit_test_code_with_additional_function.j2"
        )
    )
    prompt = t.render(
        test_function_code=test_function_code,
        additional_function_code=additional_function_code,
        use_statements=use_statements,
    )
    return prompt
