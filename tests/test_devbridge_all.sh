#!/bin/bash

# test_devbridge_all.sh
# Script to test DevBridge commands.
# Run this script from Git Bash or similar terminal on Windows.

echo "--- DevBridge Full Test Script ---"

# --- Configuration ---
# Dynamically set to the current working directory from Git Bash (e.g., /d/Repo/Project)
PROJECT_CWD_GITBASH_MSYS=$(pwd) 
echo "--- [Git Bash] Current MSYS Path: $PROJECT_CWD_GITBASH_MSYS ---"

# Get native Windows path (e.g., D:\\Repo\\Project)
PROJECT_CWD_NATIVE_WINDOWS=$(pwd -W) 
echo "--- [Git Bash] Native Windows Path (from pwd -W): $PROJECT_CWD_NATIVE_WINDOWS ---"

# Convert the native Windows path to a WSL path using wsl.exe from Git Bash
# This executes wslpath within the WSL environment but captures its output in Git Bash
PROJECT_ROOT_WSL_CONVERTED=$(wsl wslpath -a "$PROJECT_CWD_NATIVE_WINDOWS")
if [ $? -ne 0 ]; then
    echo "--- [Git Bash] ERROR: 'wsl wslpath -a \"$PROJECT_CWD_NATIVE_WINDOWS\"' failed. WSL path could not be determined."
    exit 1
fi
# Remove potential trailing carriage return characters from wslpath output
PROJECT_ROOT_WSL_FINAL=$(echo "$PROJECT_ROOT_WSL_CONVERTED" | sed 's/\\r$//')
echo "--- [Git Bash] Converted WSL Path (ready for WSL script): $PROJECT_ROOT_WSL_FINAL ---"

REPO1_URL="https://github.com/yamadashy/repomix"
REPO1_NAME="repomix" # This matches the default name from the URL
REPO1_FILE_RELPATH="src/core/output/outputGeneratorTypes.ts" 
REPO1_FILE_WORKSPACE_PATH="$REPO1_NAME/$REPO1_FILE_RELPATH"

REPO2_URL="https://github.com/jquery/jquery-mousewheel"
REPO2_NAME="jquery-mousewheel" 
REPO2_FILE_RELPATH="src/jquery.mousewheel.js"
REPO2_FILE_WORKSPACE_PATH="$REPO2_NAME/$REPO2_FILE_RELPATH" 

# Convert Windows path to WSL path for the cd command inside WSL

# --- WSL Command Block ---
# This entire block will be executed by WSL.
WSL_COMMANDS=$(cat <<HEREDOC_WSL_COMMANDS
set -e  # Exit immediately if a command exits with a non-zero status.
set -x  # Print commands and their arguments as they are executed.

# The project root is now passed directly as a WSL-compatible path.
# The value of "$PROJECT_ROOT_WSL_FINAL" from the Git Bash script is embedded here.
TARGET_DIR_IN_WSL="$PROJECT_ROOT_WSL_FINAL"

echo "--- [WSL] Target directory in WSL (received from Git Bash): \$TARGET_DIR_IN_WSL ---"
cd "\$TARGET_DIR_IN_WSL"

echo "--- [WSL] Activating virtual environment ---"
source .venv/bin/activate
echo "--- [WSL] PATH after venv activation: \$PATH ---" # DEBUG

# Ensure q CLI is in PATH if installed in a non-standard location for non-interactive shells
echo "--- [WSL] Ensuring q CLI directory is in PATH ---"
# Replace /home/adam/.local/bin with the actual directory if 'which q' shows something else in your interactive WSL
Q_CLI_DIR="/home/adam/.local/bin"
if [[ ":\$PATH:" != *":\${Q_CLI_DIR}:"* ]]; then
    export PATH="\${Q_CLI_DIR}:\$PATH"
fi
echo "--- [WSL] PATH after adding Q_CLI_DIR: \$PATH ---" # DEBUG

# --- Initial Cleanup (in case of previous failed runs) ---
echo "--- [WSL] Initial cleanup: Removing test repositories if they exist ---"
# MODIFIED: Use yes | for initial repo remove
yes | devbridge repo remove $REPO1_NAME || echo "[WSL] Repo $REPO1_NAME not found or already removed."
yes | devbridge repo remove $REPO2_NAME || echo "[WSL] Repo $REPO2_NAME not found or already removed."
# Consider more aggressive cleanup if needed, e.g.:
# rm -rf ~/.devbridge/repos/$REPO1_NAME ~/.devbridge/repos/$REPO2_NAME ~/.devbridge/db/devbridge.db

echo "--- [WSL] Testing devbridge init ---"
# MODIFIED: Try to answer 'n' to the demo prompt and the 'index now' prompt
printf 'n\nn\n' | devbridge init

echo "--- [WSL] Testing devbridge check-q ---"
devbridge check-q

echo "--- [WSL] Testing devbridge repo add (Repo 1: $REPO1_NAME from $REPO1_URL) ---"
devbridge repo add $REPO1_URL # MODIFIED: Removed --name, use default name
# The name will be 'repomix' by default

echo "--- [WSL] Testing devbridge repo add (Repo 2: $REPO2_NAME from $REPO2_URL) ---"
devbridge repo add $REPO2_URL # MODIFIED: Removed --name, use default name
# The name will be 'jquery-mousewheel' by default

echo "--- [WSL] Testing devbridge repo list ---"
devbridge repo list
sleep 1 # Brief pause

echo "--- [WSL] Testing devbridge index (Repo 1: $REPO1_NAME) ---"
devbridge index $REPO1_NAME # Uses REPO1_NAME which is "repomix"
sleep 1

echo "--- [WSL] Testing devbridge index (Repo 2: $REPO2_NAME) ---"
devbridge index $REPO2_NAME # Uses REPO2_NAME which is "jquery-mousewheel"
sleep 1

echo "--- [WSL] Testing devbridge find in $REPO1_NAME ---"
# Using "interface" as it's a common keyword in TypeScript files like the one in repomix
devbridge find "interface" --repo $REPO1_NAME

echo "--- [WSL] Testing devbridge analyze $REPO1_FILE_WORKSPACE_PATH ---"
# Analyze the specific file from repomix. $REPO1_FILE_WORKSPACE_PATH uses $REPO1_NAME="repomix"
# MODIFIED: Use repeated --check option for multiple checks
devbridge analyze "$REPO1_FILE_WORKSPACE_PATH" --check security --check performance --check style --fix --auto-approve

echo "--- [WSL] Testing devbridge learn $REPO1_URL ---"
devbridge learn $REPO1_URL --max-depth 0

echo "--- [WSL] Testing devbridge transfer (from $REPO2_NAME to $REPO1_NAME) ---"
# Transferring the JS file from jquery-mousewheel to repomix
# REPO2_FILE_RELPATH is "jquery.mousewheel.js"
devbridge transfer --from $REPO2_NAME --to $REPO1_NAME --pattern "$REPO2_FILE_RELPATH"

echo "--- [WSL] Testing devbridge document $REPO1_FILE_WORKSPACE_PATH ---"
devbridge document "$REPO1_FILE_WORKSPACE_PATH"

echo "--- [WSL] Testing devbridge chat ---"
devbridge chat --message "What is the main purpose of the file $REPO1_FILE_RELPATH in the $REPO1_NAME repository?"

echo "--- [WSL] Testing devbridge demo ---"
devbridge demo
sleep 2 # Demo involves multiple operations

# --- Final Cleanup ---
echo "--- [WSL] Final cleanup: Removing test repositories ---"
yes | devbridge repo remove $REPO1_NAME || echo "[WSL] Repo $REPO1_NAME not found or already removed during final cleanup."
yes | devbridge repo remove $REPO2_NAME || echo "[WSL] Repo $REPO2_NAME not found or already removed during final cleanup."

echo "--- [WSL] Deactivating virtual environment ---"
deactivate

echo "--- [WSL] All DevBridge tests within WSL complete ---"
HEREDOC_WSL_COMMANDS
)

# Execute the commands in WSL
echo "--- Executing test sequence in WSL ---"
echo "--- This may take some time. Output from WSL will follow. ---"
wsl -e bash -c "$WSL_COMMANDS"

echo "--- DevBridge Full Test Script finished ---" 