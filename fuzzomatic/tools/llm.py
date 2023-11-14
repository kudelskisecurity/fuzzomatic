#!/usr/bin/env python3
import os
import sys
import time

import openai
import yaml

import fuzzomatic.tools.utils
from fuzzomatic.tools.constants import EXIT_OPENAI_API_KEY_ERROR


def reset_ask_llm_counts():
    ask_llm.counter = 0
    ask_llm.prompt_tokens = 0
    ask_llm.completion_tokens = 0
    ask_llm.total_tokens = 0


def update_tokens(prompt_tokens, completion_tokens, total_tokens):
    if not hasattr(ask_llm, "prompt_tokens"):
        ask_llm.prompt_tokens = 0
    if not hasattr(ask_llm, "completion_tokens"):
        ask_llm.completion_tokens = 0
    if not hasattr(ask_llm, "prompt_tokens"):
        ask_llm.prompt_tokens = 0

    ask_llm.prompt_tokens += prompt_tokens
    ask_llm.completion_tokens += completion_tokens
    ask_llm.total_tokens += total_tokens


def ask_llm(
    prompt,
    model="gpt-3.5-turbo",
    long_model="gpt-3.5-turbo-16k",
    long_model_retry=True,
    retry=2,
):
    print("Asking LLM...")
    # Make a request to the API to generate text
    messages = [{"role": "user", "content": prompt}]

    try:
        if not hasattr(ask_llm, "counter"):
            ask_llm.counter = 0
        ask_llm.counter += 1
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=0,
            timeout=35,
        )
    except openai.error.InvalidRequestError:
        if long_model_retry:
            print("LLM call failed")
            print(f"Retrying with model {long_model}")
            return ask_llm(
                prompt, model=long_model, long_model_retry=False, retry=retry
            )
        else:
            return None
    except openai.error.Timeout:
        print("LLM call timeout")
        if retry > 0:
            print("Retrying...")
            return ask_llm(prompt, model=model, long_model=long_model, retry=retry - 1)
        return None
    except openai.error.RateLimitError as e:
        print("OpenAI API rate limit reached")
        print(e)
        sleep_seconds = 60
        print(f"Sleeping for {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
        print("Retrying")
        return ask_llm(
            prompt,
            model=model,
            long_model=long_model,
            long_model_retry=long_model_retry,
            retry=retry,
        )
    except openai.error.ServiceUnavailableError as e:
        print("OpenAI service unavailable")
        print(e)
        sleep_seconds = 60
        print(f"Sleeping for {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
        print("Retrying")
        return ask_llm(
            prompt,
            model=model,
            long_model=long_model,
            long_model_retry=long_model_retry,
            retry=retry,
        )
    except openai.error.APIError as e:
        print("OpenAI API Error")
        print(e)
        sleep_seconds = 60
        print(f"Sleeping for {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)
        print("Retrying")
        return ask_llm(
            prompt,
            model=model,
            long_model=long_model,
            long_model_retry=long_model_retry,
            retry=retry,
        )
    except openai.error.AuthenticationError as e:
        print("OpenAI authentication error. Is the OpenAI API key set and correct?")
        print(e)
        sys.exit(EXIT_OPENAI_API_KEY_ERROR)

    # extract usage information (tokens in/out)
    usage = response.usage
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens
    update_tokens(prompt_tokens, completion_tokens, total_tokens)

    # Extract the generated text from the API response
    generated_text = response.choices[0].message.content
    print("Got LLM response.")
    return generated_text


def extract_fuzz_target(response, codebase_dir):
    if response is None:
        return None

    splits = response.split("```")
    candidate_splits = []
    for split in splits:
        if "fuzz_target!(" in split:
            if split.startswith("rust"):
                split = split.replace("rust", "", 1)  # only replace first occurence
            candidate_splits.append(split)

    max_length = 0
    snippet = None
    for cs in candidate_splits:
        length = len(cs)
        if length > max_length:
            max_length = length
            snippet = cs

    if snippet is None:
        return None

    # remove print statements
    lines = snippet.split("\n")
    lines = [x for x in lines if filter_print_statements(x)]
    snippet = "\n".join(lines)

    # automatically add import if no import added
    lines = snippet.split("\n")
    imports = []
    for line in lines:
        if line.startswith("use "):
            imports.append(line.strip())

    if len(imports) == 0:
        print("[WARNING] adding imports")
        crate_name = fuzzomatic.tools.utils.detect_crate_name(codebase_dir)
        pre_imports = f"""
use libfuzzer_sys::fuzz_target;
use {crate_name};
"""
        print(pre_imports)
        snippet = pre_imports + "\n" + snippet

    return snippet


def filter_print_statements(line):
    if "eprintln!(" in line:
        return False
    if "println!(" in line:
        return False
    if "dbg!(" in line:
        return False
    return True


def get_available_models():
    response = openai.Model.list()
    models = response["data"]

    model_names = []
    for model in models:
        name = model["id"]
        model_names.append(name)

    model_names = sorted(model_names)
    return model_names


def load_openai_api_key():
    varname = "OPENAI_API_KEY"
    if varname in os.environ:
        # environment variable is set, nothing to do
        print("API key is set in env var")
    else:
        # env var not set, try to load from settings file
        here = os.path.dirname(os.path.realpath(__file__))
        project_root = os.path.join(here, os.pardir, os.pardir)
        settings_filename = "settings.yml"
        settings_path = os.path.join(project_root, settings_filename)
        error_message = (
            f"OpenAI API key not set. "
            f"Please set it in {settings_filename} "
            f"or set the {varname} environment variable."
        )
        if not os.path.exists(settings_path):
            sys.exit(error_message)
        else:
            with open(settings_path) as f:
                blob = yaml.safe_load(f)
                found = False
                if "settings" in blob:
                    settings = blob["settings"]
                    if "openai_api_key" in settings:
                        found = True
                        openai_api_key = settings["openai_api_key"]
                        print("setting openai.api_key")
                        openai.api_key = openai_api_key

                        # check that all is good with this key
                        _models = get_available_models()

                if not found:
                    sys.exit(error_message)
