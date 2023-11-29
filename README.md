# Fuzzomatic

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-green.svg)](https://docs.python.org/3.11/whatsnew/) [![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)


Automatically fuzz Rust projects from scratch

# Requirements

* Rust (install using [rustup](https://rustup.rs/))
* Cargo fuzz (see below)
* Semgrep (see below)
* An OpenAI API key

```
cargo install cargo-fuzz
rustup toolchain install nightly
rustup default nightly
pipx install semgrep
```

# Installation

Install the dependencies:

```
poetry install
```

Setup your OpenAI API key in `settings.yml`.
The file `settings.yml.sample` can be copied as an example.

```
cp settings.yml.sample settings.yml
```

Now edit `settings.yml` and set your API key in there.

Alternatively, set the `OPENAI_API_KEY` environment variable before running fuzzomatic:

```
export OPENAI_API_KEY=your_key_goes_here
```

# Usage

> [!WARNING]
> Arbitrary code execution may happen when building/running untrusted projects or code output by an LLM. Use at your own risk and make sure you understand the risks of running the following command.
Make sure to run the following command in an isolated environment such as a VM.


```
poetry run fuzzomatic <codebase_dir> --stop-on bug --max-fuzz-targets 2
```

The `--stop-on` parameter can be set to `bug`, `useful` or `building`.
Fuzzomatic will stop when a bug is found, when a useful fuzz target is generated 
or when a building fuzz target is generated, respectively.

The `--max-fuzz-targets` parameter can be set to control how many `bug`s, `useful` or `building` 
fuzz targets must be found to stop.

By default, Fuzzomatic will stop when 1 bug is found for the target code base.

# Tests

To run the tests:

```
./run-tests.sh
```

# Side tools

Fuzzomatic comes with a handful of companion tools

## batch_fuzzomatic

Run Fuzzomatic automatically on all code bases in a given directory

Example:

```
poetry run batch_fuzzomatic /path/to/all/git-repos/ --stop-on bug --max-fuzz-targets 2
```

## eval_results

Print results of fuzzomatic runs. Fuzzomatic writes its results to `.fuzzomatic_results.json`
in each code base it was run on. `eval_results` will read these result files and print them
in a readable way.

`eval_results` can be used on a single code base
as well as on a directory that was used with `batch_fuzzomatic`. In the second case,
it will print aggregate statistics over all projects.

Example:

```
poetry run eval_results /path/to/codebase
```

Show aggregate stats but only show details for projects where a bug was found:

```
poetry run eval_results /path/to/all/git-repos -v --bug-found
```

## discovery

Discover and git clone projects on GitHub for automated fuzzing with fuzzomatic

Example:

```
poetry run discover \
--max-projects 10 \
--target-dir /path/where/to/git/clone/projects \
--query "parser library"
```

## oss_fuzz

Build the list of projects already covered by OSS-fuzz and save it to `oss-fuzz-projects.csv`

Usage:

```
poetry run oss_fuzz
```

# License and Copyright

Copyright(c) 2023 Nagravision SA.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 3 as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see http://www.gnu.org/licenses/.