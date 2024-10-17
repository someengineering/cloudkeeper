#!/bin/bash
set -euo pipefail

# Debian packages:
#   curl bash python3-minimal python3-venv python3-dev git make gcc g++
# CentOS packages:
#   curl bash python39 python39-devel git make gcc gcc-c++
# Fedora packages:
#   curl bash python3 python3-devel git make gcc gcc-c++
# Alpine packages:
#   curl bash python3 python3-dev git make gcc g++ linux-headers libffi-dev

declare -a supported_versions=(python3.12 python3.11 python3.10 python3.9)
declare -a debian_packages=(curl bash python3-minimal python3-venv python3-dev git make gcc g++)
declare -a centos_packages=(curl bash python39 python39-devel git make gcc gcc-c++)
declare -a fedora_packages=(curl bash python3 python3-devel git make gcc gcc-c++ findutils)
declare -a alpine_packages=(curl bash python3 python3-dev git make gcc g++ linux-headers libffi-dev)
declare install_path="$HOME/fixinventory"
declare python_cmd
declare git_install=false
declare dev_mode=false
declare unattended=false
declare venv=true
declare install_plugins=true
declare branch=main

main() {
    echo "fixinventory bootstrapper"

    if [ -f .git/config -a -d fixcore ]; then
        install_path="$PWD"
    fi
    local end_of_opt
    local positional=()
    while [[ $# -gt 0 ]]; do
        case "${end_of_opt:-}${1}" in
            -h|--help)      usage 0 ;;
            --python)       shift; python_cmd="${1:-}" ;;
            --path)         shift; install_path="${1:-}" ;;
            --branch)       shift; branch="${1:-}" ;;
            --no-venv)      venv=false ;;
            --no-plugins)   install_plugins=false ;;
            --dev)          dev_mode=true ;;
            --git)          git_install=true ;;
            --yes)          unattended=true ;;
            --)             end_of_opt=1 ;;
            -*)             invalid "$1" ;;
            *)              positional+=("$1") ;;
        esac
        if [ $# -gt 0 ]; then
            shift
        fi
    done
    if [ ${#positional[@]} -gt 0 ]; then
       set -- "${positional[@]}"
    fi

    install_path=${install_path%%+(/)}
    if [ -z "${install_path:-}" ]; then
        echo "Invalid install path $install_path"
        exit 1
    fi

    if [ -z "${branch:-}" ]; then
        echo "Invalid branch"
        exit 1
    fi

    if [ -z "${python_cmd:-}" ]; then
        python_cmd="$(find_python)"
    fi
    if [ -z "${python_cmd:-}" ]; then
        echo -e "Could not find a compatible Python interpreter!\nSupported versions are" "${supported_versions[@]}"
        exit 1
    fi
    if ! type "$python_cmd" > /dev/null 2>&1; then
        echo -e "Unable to use Python interpreter $python_cmd"
        exit 1
    fi

    CWD=$(pwd)
    echo "Using $python_cmd"
    ensure_install_path
    if [ "$venv" = true ]; then
        activate_venv "$python_cmd"
    fi
    cd "$CWD"
    ensure_pip
    if [ "$dev_mode" = true ]; then
        install_dev
    fi
    install_fixinventory
    if [ "$install_plugins" = true ]; then
        install_plugins
    fi
    echo -e "Install/Update completed.\nRun\n\tsource ${install_path}/venv/bin/activate\nto activate venv."
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Valid options:
  -h, --help        show this help message and exit
  --path <path>     install directory (default: . if in fixinventory git repo else ~/fixinventory/)
  --python <path>   Python binary to use (default: search for best match)
  --branch <branch> Git branch/tag to use (default: main)
  --dev             install development dependencies (default: false)
  --yes             unattended mode - assume yes for all questions (default: false)
  --no-venv         do not create a Python venv for package installation (default: false)
  --git             install from remote Git instead of local repo (default: false)
EOF

  if [ -n "$1" ]; then
    exit "$1"
  fi
}

invalid() {
  echo "ERROR: Unrecognized argument: $1" >&2
  usage 1
}

ensure_install_path() {
    echo "Using install path $install_path"
    mkdir -p "$install_path"
    cd "$install_path"
}

find_python() {
    local version
    for version in "${supported_versions[@]}"; do
        if type "$version" > /dev/null 2>&1; then
            echo "$version"
            return 0
        fi
    done
}

activate_venv() {
    local python_cmd=$1
    if [ -d "venv/" ]; then
        echo -e "Virtual Python env already exists!\nRun\n\trm -rf venv/\nif you want to recreate it."
    else
        echo "Creating virtual Python env in venv/ using $python_cmd"
        "$python_cmd" -m venv venv --prompt "fixinventory venv"
    fi
    echo "Activating venv"
    source venv/bin/activate
}

ensure_pip() {
    echo "Ensuring Python pip is available and up to date."
    if ! python -m pip help > /dev/null 2>&1; then
        python -m ensurepip -q -U
    fi
    pip install -q -U pip wheel
}

install_dev() {
    echo "Installing development dependencies"
    if [ -f "requirements-all.txt" ]; then
        pip install -q -r "requirements-all.txt"
    else
        pip install -q -r "https://raw.githubusercontent.com/someengineering/fixinventory/main/requirements-all.txt"
    fi
}

install_fixinventory() {
    echo "Installing fixinventory"
    if [ -f "requirements-extra.txt" ]; then
        pip install -q -r "requirements-extra.txt"
    else
        pip install -q -r "https://raw.githubusercontent.com/someengineering/fixinventory/main/requirements-extra.txt"
    fi
    local fixinventory_components=(fixlib fixcore fixshell fixworker fixmetrics)
    for component in "${fixinventory_components[@]}"; do
        pip_install "$component"
    done
}

install_plugins() {
    local collector_plugins=(aws azure digitalocean dockerhub example_collector gcp github k8s onelogin posthog random scarf slack)
    for plugin in "${collector_plugins[@]}"; do
        pip_install "$plugin" true
    done
}

ensure_git() {
    if ! type git > /dev/null 2>&1; then
        echo "Git is not available in PATH - aborting install"
        exit 1
    fi
}

pip_install() {
    local package=$1
    local plugin=${2:-false}
    local egg_prefix=""
    local path_prefix=""
    if [ "$plugin" = true ]; then
        path_prefix="plugins/"
        egg_prefix="fix-plugin-"
    fi
    local package_name="${egg_prefix}${package}"
    package_name=${package_name//_/-}
    local relative_path="${path_prefix}${package}/"
    if [ -d "$relative_path" ] && [ "$git_install" = false ]; then
        echo "Installing $package_name editable from local path $relative_path"
        # until this is fixed: https://github.com/pypa/setuptools/issues/3518
        pip install -q --editable "$relative_path" --config-settings editable_mode=compat
    else
        ensure_git
        local git_repo="git+https://github.com/someengineering/fixinventory.git@${branch}#egg=${package_name}&subdirectory=${relative_path}"
        echo "Installing $package_name from remote $git_repo"
        pip install -q -U "$git_repo"
    fi
}

main "$@"
