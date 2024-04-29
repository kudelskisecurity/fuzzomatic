#!/usr/bin/env python3
import os
import sys
import time

import openai

import fuzzomatic.tools.utils
from fuzzomatic.tools.constants import EXIT_OPENAI_API_KEY_ERROR

DEFAULT_CLIENT = "azure_openai"
OPENAI_CLIENT = os.environ.get("OPENAI_CLIENT", DEFAULT_CLIENT)

if OPENAI_CLIENT == "azure_openai":
    DEFAULT_MODEL = os.environ.get("AZURE_OPENAI_MODEL")
    DEFAULT_MODEL_LONG = os.environ.get("AZURE_OPENAI_MODEL_LONG")
else:
    DEFAULT_MODEL = os.environ.get("OPENAI_MODEL")
    DEFAULT_MODEL_LONG = os.environ.get("OPENAI_MODEL_LONG")


def ask_llm(
    prompt,
    model=DEFAULT_MODEL,
    long_model=DEFAULT_MODEL_LONG,
    long_model_retry=True,
    retry=2,
):
    print("Asking LLM...")

    try:
        response = get_llm_response_raw(model, prompt)
    except openai.BadRequestError:
        if long_model_retry:
            print("LLM call failed")
            print(f"Retrying with model {long_model}")
            return ask_llm(
                prompt, model=long_model, long_model_retry=False, retry=retry
            )
        else:
            return None
    except openai.APITimeoutError:
        print("LLM call timeout")
        if retry > 0:
            print("Retrying...")
            return ask_llm(prompt, model=model, long_model=long_model, retry=retry - 1)
        return None
    except openai.RateLimitError as e:
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
    except openai.ServiceUnavailableError as e:
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
    except openai.APIError as e:
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
    except openai.AuthenticationError as e:
        print("OpenAI authentication error. Is the OpenAI API key set and correct?")
        print(e)
        sys.exit(EXIT_OPENAI_API_KEY_ERROR)

    # Extract the generated text from the API response
    generated_text = response.choices[0].message.content
    print("Got LLM response.")
    return generated_text


def get_llm_response_raw(model, prompt, timeout=35, temperature=0):
    if OPENAI_CLIENT == "azure_openai":
        client = openai.AzureOpenAI()  # use Azure OpenAI client
    else:
        client = openai.OpenAI()  # use OpenAI client

    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        messages=messages,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )
    return response


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
