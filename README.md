# DevBridge: AI-Powered Cross-Project Knowledge Bridge

DevBridge is a command-line tool that helps developers transfer knowledge, code patterns, and best practices across different projects and codebases. It features a persistent, normalized knowledge base, advanced code element extraction, and deep Amazon Q Developer CLI integration for adaptation, documentation, and analysis.

## Features

- **Index and Search Across Codebases**: Index multiple repositories and extract code elements.
- **Advanced Content-Aware Search**: Find code elements or text with powerful filtering.
- **Code Transfer with Amazon Q Adaptation**: Copy files between projects with AI-powered adaptation.
- **Amazon Q-Powered Documentation & Analysis**: Generate documentation and analyze code using Amazon Q.
- **Rich Terminal UI**: Colorized, formatted output and tables.
- **Repository Workspace**: Manage local project copies.
- **Guided Setup & Diagnostics**: Includes `devbridge init` and `devbridge check-q`.
- **Learn from Public Documentation**: Fetch and process documentation using the `learn` command.

## <a name="installation"></a>Installation

Getting started with DevBridge is simple.

**Prerequisites:**
- Python 3.8+
- pip (Python package installer)
- Git (for features like `devbridge repo add <url>` and some Amazon Q interactions)

**Install DevBridge:**

If you have the DevBridge source code (e.g., from a Git clone or a source archive provided for a hackathon/demo):
```bash
# Navigate to the project root directory
cd path/to/devbridge-source
# Install DevBridge and its dependencies
pip install .
```

**Install from TestPyPI (for testing/pre-release versions):**

DevBridge might be available on TestPyPI for evaluation. To install it from TestPyPI, you need to tell `pip` to look for its dependencies on the main PyPI as well, because not all dependencies are mirrored on TestPyPI. Use the following command:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ devbridge
```

recent version
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --no-cache-dir devbridge==0.1.4 
```
(Replace `devbridge` with `devbridge==0.1.1` or the specific version you want to test if needed.)

*Once DevBridge is published on the main PyPI (the Python Package Index), installation will be as simple as: `pip install devbridge`*

After installation, the `devbridge` command will be available in your terminal.

**Platform Support:**
- **Windows (with WSL):** DevBridge is currently most extensively tested and optimized for use on Windows with the Windows Subsystem for Linux (WSL). Features involving the Amazon Q CLI (`q`) and Node.js for JavaScript parsing are well-integrated within this environment.
- **Linux/macOS:** The core functionality of DevBridge is expected to work on native Linux and macOS. However, while designed to be cross-platform, these environments have undergone less extensive testing, particularly for features relying on external CLI tools like Amazon Q. The tool attempts to adapt its behavior for non-WSL environments, but users might encounter differences. Community testing and feedback for these platforms are welcome.

**Required External Tools (for specific features):**
- **Amazon Q Developer CLI (`q`):** Required for features like code transfer (`transfer`), documentation generation (`document`), code analysis (`analyze`), and checking the Q setup (`check-q`). Please install and configure it separately from the official Amazon Q documentation. DevBridge will notify you if `q` is needed but not found for a command.
- **Node.js (and `npm` for Tree-sitter parsers, optional):** While not strictly required for basic operation, Node.js is needed by the `devbridge index` command to perform detailed parsing of JavaScript and TypeScript code elements (e.g., functions, classes). If Node.js is not found in your `PATH`, indexing will still work for other languages and basic file information, but detailed JS/TS parsing will be skipped. You might see messages like `[extract_js_elements] Error: [Errno 2] No such file or directory: 'node'` in the debug output; this is expected if Node.js is not available and simply means that fine-grained JS/TS element extraction could not be performed. Basic indexing of these files will still occur. Some advanced language parsing features might implicitly use `npm` to manage Tree-sitter parsers.
- To install:  [The essential guide to installing Amazon Q Developer CLI on Windows](https://dev.to/aws/the-essential-guide-to-installing-amazon-q-developer-cli-on-windows-lmh) 

## <a name="usage"></a>Usage

1.  **Initialize DevBridge (Recommended for first-time users):**
    ```bash
    devbridge init
    ```
2.  **Check Amazon Q CLI setup (if you plan to use Q-dependent features):**
    ```bash
    devbridge check-q
    ```
3.  **Add your projects to the DevBridge workspace (Optional, direct paths also work):**
    ```bash
    devbridge repo add /path/to/your/local/projectA
    devbridge repo add https://github.com/example/projectB.git
    ```
4.  **Index your repositories:**
    ```bash
    devbridge index --repo projectA # Index 'projectA' from workspace
    devbridge index --repo /path/to/another/projectC # Index a project by direct path
    ```
5.  **Find code elements or text:**
    ```bash
    devbridge find "api_key_handler" --repo projectA
    ```
6.  **Learn about a topic or repository:**
    ```bash
    devbridge learn https://github.com/someuser/some-repo
    devbridge learn https://github.com/aws/amazon-q-developer-cli
    ```
For more commands and options, run `devbridge --help` or `devbridge <command> --help`.

## Running Comprehensive Tests

A shell script is provided to test all core `devbridge` commands in a WSL environment. This script automates:
- Setting up the WSL environment.
- Activating the Python virtual environment.
- Cleaning up previous test data.
- Adding test repositories.
- Running each `devbridge` command with appropriate arguments.
- Cleaning up test repositories afterwards.

**To run the comprehensive test suite:**

1.  Ensure you have WSL installed and configured.
2.  Ensure the project's Python virtual environment (`.venv`) has been created and populated (`pip install -r requirements.txt`).
3.  Open a terminal that can execute shell scripts (like Git Bash on Windows).
4.  Navigate to the project root directory.
5.  Execute the script:
    ```bash
    ./tests/test_devbridge_all.sh
    ```
    Or, if you are already in the `tests` directory:
    ```bash
    ./test_devbridge_all.sh
    ```

The script will output detailed logs of its progress, including the commands being run and their results. This is the recommended way to verify the functionality of DevBridge after making changes.

**Note on Amazon Q CLI (`q`) and Node.js:**
- The test script is designed to run even if the Amazon Q CLI (`q`) is not fully configured or if Node.js is not installed. Commands that depend on these tools will gracefully report that the tool is missing or not configured, which is the expected behavior in such cases. For full end-to-end testing of Q-dependent features (analyze, transfer, document, chat), ensure `q` is installed, configured, and accessible in your WSL `PATH`. The script attempts to add a common user local bin path (`/home/your_wsl_user/.local/bin`) to the `PATH` within its execution scope, but you may need to adjust `Q_CLI_DIR` in the script if `q` is installed elsewhere.
- For complete JavaScript/TypeScript indexing tests, ensure Node.js is installed and available in your WSL `PATH`.

## <a name="commands"></a>Available Commands

- `devbridge init`: Onboard and configure DevBridge.
- `devbridge check-q`: Verify Amazon Q CLI setup.
- `devbridge repo add/list/remove`: Manage repositories in the DevBridge workspace.
- `devbridge index`: Index repositories to build the knowledge base.
- `devbridge find`: Search for patterns and code elements.
- `devbridge learn`: Fetch and process documentation from public URLs.
- `devbridge transfer`: Adapt and transfer code patterns (requires Amazon Q CLI).
- `devbridge document`: Generate documentation for code (requires Amazon Q CLI).
- `devbridge analyze`: Analyze code for best practices (requires Amazon Q CLI).
- `devbridge chat`: Start an interactive chat session (requires Amazon Q CLI, experimental).
- `devbridge demo`: Showcase core features.

(Refer to `devbridge --help` for a full list and details.)

## Development & Contribution

If you want to contribute to DevBridge or run it from source for development purposes, follow these steps.

**Development Prerequisites:**
- Python 3.8+ (Python 3.10+ recommended)
- pip (Python package installer)
- Git
- For Windows developers: WSL (Windows Subsystem for Linux) is strongly recommended for a smoother development experience, especially for testing interactions with external tools like the Amazon Q CLI.
- **For specific features requiring Amazon Q:** Amazon Q Developer CLI (`q`) - `devbridge` will notify if this is missing for a command.
- Internet access for the `learn` command and other features that might fetch external resources.

**Setting up a Development Environment:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/bO-05/devbridge.git
    cd devbridge
    ```

2.  **Create and Activate a Virtual Environment:**
    It's highly recommended to use a virtual environment to manage project dependencies.
    ```bash
    # Using Python's built-in venv module
    python3 -m venv .venv
    ```
    Activate the environment:
    -   Linux/macOS (bash/zsh):
        ```bash
        source .venv/bin/activate
        ```
    -   Windows (PowerShell):
        ```ps1
        .venv\Scripts\Activate.ps1
        ```
    -   Windows (CMD):
        ```bat
        .venv\Scripts\activate.bat
        ```

3.  **Install in Editable Mode with Development Dependencies:**
    This command installs DevBridge such that changes to your source code are immediately reflected when you run the `devbridge` command. It also installs testing tools.
    ```bash
    pip install -e ".[dev]"
    ```

**Running Tests:**

Ensure your virtual environment is activated.
```bash
# Run the full test suite
pytest

# Run tests for a specific file with more verbose output
pytest tests/test_learn_cmd.py -s -v
```

**Running from Source (Alternative for Development):**

After an editable install (`pip install -e ".[dev]"`), the `devbridge` command in your activated virtual environment will directly use your local source code. This is the recommended way to run during development.

If you choose not to use an editable install, you can set `PYTHONPATH` (less common for typical development):
```bash
# Ensure your virtual environment is activated and you are in the project root.
# On Linux/macOS:
export PYTHONPATH=$(pwd)
python -m devbridge.cli <command> <args>

# On Windows PowerShell:
$env:PYTHONPATH = (Get-Location).Path
python -m devbridge.cli <command> <args>
```

## Building the Package

To create distributable package files (wheel and sdist) for DevBridge:

1.  **Install the `build` package:**
    ```bash
    pip install build
    ```

2.  **Run the build command from the project root:**
    ```bash
    python -m build
    ```
    This will generate a `dist/` directory containing the packaged files (e.g., `devbridge-0.1.0-py3-none-any.whl` and `devbridge-0.1.0.tar.gz`). These files can be used for distribution, for example, by uploading to PyPI or sharing directly.

## License

MIT

## Project Structure (For Contributors)

(The project structure diagram can remain here or be moved to a separate CONTRIBUTING.md if preferred)
```bash
├── .gitignore
├── LICENSE
├── MANIFEST.in
├── README.md
├── devbridge
    ├── __init__.py
    ├── cli.py
    ├── commands
    │   ├── __init__.py
    │   ├── analyze_cmd.py
    │   ├── chat_cmd.py
    │   ├── document_cmd.py
    │   ├── find_cmd.py
    │   ├── index_cmd.py
    │   ├── init_cmd.py
    │   ├── learn_cmd.py
    │   └── transfer_cmd.py
    ├── config.py
    ├── devbridge.db
    ├── models
    │   ├── pattern.py
    │   └── repository.py
    └── utils
    │   ├── __init__.py
    │   ├── cli_utils.py
    │   ├── config.py
    │   ├── deepwiki_helpers.py
    │   ├── html_to_markdown.py
    │   ├── http_crawler.py
    │   ├── js_parser.js
    │   ├── js_parser.py
    │   ├── storage.py
    │   ├── test_path_resolve.py
    │   └── wsl_utils.py
├── requirements.txt
├── setup.py
```