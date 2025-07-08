# Fuzzomatic

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-green.svg)](https://docs.python.org/3.11/whatsnew/) [![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)


Automatically fuzz Rust projects from scratch with AI assistance

<img src="https://github.com/kudelskisecurity/fuzzomatic/assets/11460141/0c38ab05-9a42-41a1-b150-390f4810be8a" alt="Fuzzomatic Werewolf" width=50% />

Read our introductory blog post here. 

https://research.kudelskisecurity.com/2023/12/07/introducing-fuzzomatic-using-ai-to-automatically-fuzz-rust-projects-from-scratch/ 

# Requirements

* Rust (install using [rustup](https://rustup.rs/))
* Cargo fuzz (see below)
* Semgrep (see below)
* Poetry (see below)
* An OpenAI API key (see [instructions](https://platform.openai.com/docs/quickstart/account-setup?context=python))

```
cargo install cargo-fuzz
rustup toolchain install nightly
rustup default nightly
pipx install semgrep
pipx install poetry
```

# Installation

Install the dependencies:

```
poetry install
```

Setup your OpenAI API settings (key, endpoint, etc.) `settings.env`.
The file `settings.env.sample` can be copied as an example.

```
cp settings.env.sample settings.env
```

Now edit `settings.env` and set the environment variables in that file according to your environment.
OpenAI and Azure OpenAI are both supported.

Before running Fuzzomatic, make sure to source the env file:

```
source settings.env
```

# Usage

> [!WARNING]
> Arbitrary code execution may happen when building/running untrusted projects or code output by an LLM. Use at your own risk and make sure you understand the risks of running the following command.
> **Make sure to run the following command in an isolated environment such as a VM.**


```
poetry run fz <codebase_dir> --stop-on bug --max-fuzz-targets 2
```

The `--stop-on` parameter can be set to `bug`, `useful` or `building`.
Fuzzomatic will stop when a bug is found, when a useful fuzz target is generated 
or when a building fuzz target is generated, respectively.

The `--max-fuzz-targets` parameter can be set to control how many `bug`s, `useful` or `building` 
fuzz targets must be found to stop.

By default, Fuzzomatic will stop when 1 bug is found for the target code base.

When Fuzzomatic completes, use `fz-results` (see below) to display detailed information about what Fuzzomatic found.

# Tests

To run the tests:

```
./run-tests.sh
```

# Side tools

Fuzzomatic comes with a handful of companion tools

## fz-batch

Run Fuzzomatic automatically on all code bases in a given directory

Example:

```
poetry run fz-batch /path/to/all/git-repos/ --stop-on bug --max-fuzz-targets 2
```

## fz-results

Print results of fuzzomatic runs. Fuzzomatic writes its results to `.fuzzomatic_results.json`
in each code base it was run on. `fz-results` will read these result files and print them
in a readable way.

`fz-results` can be used on a single code base
as well as on a directory that was used with `fz-batch`. In the second case,
it will print aggregate statistics over all projects.

Example:

```
poetry run fz-results /path/to/codebase
```

Show aggregate stats but only show details for projects where a bug was found:

```
poetry run fz-results /path/to/all/git-repos -v --bug-found
```

## fz-discover

Discover and git clone projects on GitHub for automated fuzzing with fuzzomatic

Example:

```
poetry run fz-discover \
--max-projects 10 \
--target-dir /path/where/to/git/clone/projects \
--query "parser library"
```

## fz-oss-fuzz

Build the list of projects already covered by OSS-fuzz and save it to `oss-fuzz-projects.csv`

Usage:

```
poetry run fz-oss-fuzz
```

# Project Goals 
The primary goal of the project is to decrease the effort for developers to get started with fuzzing. For many projects, fuzzing isn’t done because it is viewed as taking too much time or potentially too complex. With Fuzzomatic, we use Large Language Models to assist in the setup and execution of fuzz testing for Rust applications. It's our hope that with continued development and experimentation, more developers will implement fuzzing into their development process and catch more vulnerabilities and issues before they make it into production.     

# License and Copyright

Copyright(c) 2023 Nagravision SA.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 3 as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see http://www.gnu.org/licenses/.
