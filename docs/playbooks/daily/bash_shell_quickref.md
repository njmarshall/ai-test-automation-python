# Bash / Shell Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Covers daily terminal use, file ops, text processing, CI debugging, and scripting patterns

---

## Table of Contents
- [Navigation & Files](#navigation--files)
- [File Operations](#file-operations)
- [Viewing & Searching Files](#viewing--searching-files)
- [grep](#grep)
- [awk](#awk)
- [sed](#sed)
- [find](#find)
- [xargs](#xargs)
- [Pipes & Redirection](#pipes--redirection)
- [Variables & Environment](#variables--environment)
- [Conditionals](#conditionals)
- [Loops](#loops)
- [Functions](#functions)
- [Process Management](#process-management)
- [Networking](#networking)
- [Archives & Compression](#archives--compression)
- [Permissions](#permissions)
- [Script Patterns](#script-patterns)
- [CI Debugging Patterns](#ci-debugging-patterns)
- [Gotchas](#gotchas)
- [Quick Reference Card](#quick-reference-card)

---

## Navigation & Files

```bash
pwd                        # print working directory
cd ~                       # home directory
cd -                       # previous directory
ls -la                     # list all with permissions
ls -lh                     # human-readable sizes
ls -lt                     # sort by modified time

# Directory shortcuts
dirs -v                    # directory stack
pushd /path/to/dir         # push to stack
popd                       # pop back

# Disk usage
du -sh *                   # size of each item in current dir
du -sh ./projects          # size of specific directory
df -h                      # disk space on all mounts
```

---

## File Operations

```bash
# Create
touch file.txt
mkdir -p docs/playbooks/daily      # create nested dirs

# Copy
cp file.txt backup.txt
cp -r src/ dest/                   # recursive copy
cp -p file.txt backup.txt          # preserve metadata

# Move / rename
mv old.txt new.txt
mv file.txt /path/to/dir/

# Delete
rm file.txt
rm -rf build/                      # recursive force (DESTRUCTIVE)
rmdir empty_dir/                   # remove empty dir only

# Links
ln -s /path/to/target link_name    # symbolic link
ln /path/to/target hard_link       # hard link

# File info
file script.sh                     # type of file
stat file.txt                      # full metadata
wc -l file.txt                     # line count
wc -w file.txt                     # word count
```

---

## Viewing & Searching Files

```bash
cat file.txt                       # print whole file
less file.txt                      # paginate (q to quit)
head -20 file.txt                  # first 20 lines
tail -20 file.txt                  # last 20 lines
tail -f app.log                    # follow live (great for logs)
tail -f app.log | grep ERROR       # live filter

# Side-by-side diff
diff file1.txt file2.txt
diff -u file1.txt file2.txt        # unified format
diff -r dir1/ dir2/                # recursive directory diff

# Search in files
grep "pattern" file.txt
grep -r "pattern" ./src            # recursive
grep -i "pattern" file.txt         # case-insensitive
grep -n "pattern" file.txt         # show line numbers
grep -l "pattern" ./tests          # list matching files only
grep -v "pattern" file.txt         # invert match (exclude)
grep -c "pattern" file.txt         # count matches
```

---

## grep

```bash
# Basic
grep "ERROR" app.log
grep -r "def test_" tests/          # find all test functions

# Regex
grep -E "^[0-9]{3}-[0-9]{4}$" file.txt    # extended regex
grep -P "\d{4}-\d{2}-\d{2}" file.txt      # Perl regex (dates)

# Context lines
grep -A 3 "ERROR" app.log           # 3 lines After
grep -B 3 "ERROR" app.log           # 3 lines Before
grep -C 3 "ERROR" app.log           # 3 lines Context (both)

# Multiple patterns
grep -e "ERROR" -e "WARN" app.log
grep -E "ERROR|WARN" app.log

# Exclude
grep -v "DEBUG" app.log
grep --include="*.py" -r "import pytest" .
grep --exclude="*.pyc" -r "TODO" .
grep --exclude-dir=".git" -r "TODO" .

# Count failures in CI log
grep -c "FAILED" pytest_output.log

# Find test files not following naming convention
grep -rL "def test_" tests/         # files WITHOUT test functions
```

---

## awk

```bash
# Print specific columns (tab/space separated)
awk '{print $1}' file.txt          # first column
awk '{print $1, $3}' file.txt      # first and third
awk -F',' '{print $2}' data.csv    # CSV, second column
awk -F':' '{print $1}' /etc/passwd # colon-delimited

# Filter rows
awk '$3 > 100' data.txt            # rows where col 3 > 100
awk '/ERROR/' app.log              # rows matching pattern
awk '!/DEBUG/' app.log             # rows NOT matching

# Arithmetic
awk '{sum += $1} END {print sum}' numbers.txt
awk '{sum += $1} END {print "Average:", sum/NR}' numbers.txt

# Print line numbers
awk '{print NR, $0}' file.txt

# Extract test durations from pytest output
awk '/PASSED|FAILED/ {print $1, $NF}' pytest_output.log

# Summarize HTTP status codes from access log
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# Print lines between two patterns
awk '/START/,/END/' file.txt
```

---

## sed

```bash
# Substitute (in-place with -i)
sed 's/old/new/' file.txt           # first occurrence per line
sed 's/old/new/g' file.txt          # all occurrences
sed -i 's/old/new/g' file.txt       # in-place edit
sed -i.bak 's/old/new/g' file.txt   # in-place with backup

# Delete lines
sed '/pattern/d' file.txt           # delete matching lines
sed '5d' file.txt                   # delete line 5
sed '5,10d' file.txt                # delete lines 5-10

# Print specific lines
sed -n '5,10p' file.txt             # print lines 5-10
sed -n '/START/,/END/p' file.txt    # print between patterns

# Insert / append
sed '3i\new line here' file.txt     # insert before line 3
sed '3a\new line here' file.txt     # append after line 3

# Strip blank lines
sed '/^$/d' file.txt

# Strip comments
sed '/^#/d' config.txt

# Replace in multiple files
sed -i 's/http:/https:/g' configs/*.conf

# Update version in pyproject.toml
sed -i 's/version = "1.0.0"/version = "1.1.0"/' pyproject.toml
```

---

## find

```bash
# By name
find . -name "*.py"
find . -name "test_*.py"
find . -iname "readme*"             # case-insensitive

# By type
find . -type f                      # files only
find . -type d                      # directories only
find . -type l                      # symlinks only

# By time
find . -mtime -7                    # modified in last 7 days
find . -mtime +30                   # modified more than 30 days ago
find . -newer reference.txt         # newer than a file

# By size
find . -size +1M                    # larger than 1MB
find . -size -100k                  # smaller than 100KB
find . -empty                       # empty files/dirs

# Exclude directories
find . -not -path "./.git/*" -name "*.py"
find . -name "*.py" ! -path "*/node_modules/*"

# Execute on results
find . -name "*.pyc" -delete
find . -name "*.log" -exec rm {} \;
find . -name "*.py" -exec grep -l "TODO" {} \;

# Useful combos
find . -name "conftest.py"          # locate all conftest files
find . -name "*.py" | xargs grep -l "import requests"
find build/ -name "*.xml" -newer src/ -delete    # stale CI artifacts
```

---

## xargs

```bash
# Pass find results as arguments
find . -name "*.pyc" | xargs rm
find . -name "*.py" | xargs grep -l "TODO"

# Parallel execution (-P)
find . -name "test_*.py" | xargs -P 4 -I {} pytest {}

# Handle spaces in filenames (-0 / -print0)
find . -name "*.txt" -print0 | xargs -0 rm

# Batch size
echo "a b c d e" | xargs -n 2 echo   # process 2 at a time

# With placeholder (-I)
cat ids.txt | xargs -I {} curl https://api.example.com/patient/{}

# Confirm before executing (-p)
find . -name "*.bak" | xargs -p rm
```

---

## Pipes & Redirection

```bash
# Pipe stdout to next command
cat app.log | grep ERROR | wc -l

# Redirect stdout to file
pytest > results.txt 2>&1          # stdout + stderr to file
pytest >> results.txt              # append

# Redirect stderr only
pytest 2> errors.txt

# Discard output
command > /dev/null 2>&1

# tee — write to file AND stdout
pytest | tee results.txt

# Process substitution
diff <(sort file1.txt) <(sort file2.txt)

# Here string
grep "pattern" <<< "string to search"

# Here document
cat <<EOF > config.yaml
baseUrl: https://example.com
timeout: 30
EOF
```

---

## Variables & Environment

```bash
# Set variable
NAME="Neil"
echo $NAME
echo "${NAME}_suffix"              # use braces for clarity

# Export (visible to child processes)
export BASE_URL="https://hapi.fhir.org/baseR4"

# Default value
URL=${BASE_URL:-"http://localhost:3000"}

# Required variable (exit if unset)
: "${TEST_USER:?TEST_USER is required}"

# Read from .env file
export $(grep -v '^#' .env | xargs)

# Array
BROWSERS=("chromium" "firefox" "webkit")
echo "${BROWSERS[0]}"              # chromium
echo "${#BROWSERS[@]}"             # length: 3
for b in "${BROWSERS[@]}"; do echo "$b"; done

# Command substitution
CURRENT_DATE=$(date +%Y-%m-%d)
COMMIT_HASH=$(git rev-parse --short HEAD)

# Arithmetic
COUNT=$((COUNT + 1))
TOTAL=$((10 * 5))

# String operations
STR="playwright_quickref.md"
echo "${STR%.md}"                  # strip .md suffix
echo "${STR#playwright_}"          # strip prefix
echo "${STR^^}"                    # uppercase
echo "${#STR}"                     # length
```

---

## Conditionals

```bash
# if / elif / else
if [ -f "pytest.ini" ]; then
    echo "Found pytest config"
elif [ -f "pyproject.toml" ]; then
    echo "Found pyproject.toml"
else
    echo "No config found"
fi

# File tests
[ -f file ]        # file exists
[ -d dir ]         # directory exists
[ -e path ]        # path exists (file or dir)
[ -s file ]        # file exists and is non-empty
[ -r file ]        # file is readable
[ -x file ]        # file is executable

# String tests
[ -z "$VAR" ]      # string is empty
[ -n "$VAR" ]      # string is non-empty
[ "$A" = "$B" ]    # strings equal
[ "$A" != "$B" ]   # strings not equal

# Numeric tests
[ $A -eq $B ]      # equal
[ $A -ne $B ]      # not equal
[ $A -lt $B ]      # less than
[ $A -gt $B ]      # greater than

# Logical
[ $A -gt 0 ] && [ $B -gt 0 ]   # AND
[ $A -gt 0 ] || [ $B -gt 0 ]   # OR

# Modern syntax (preferred)
[[ -f "file" && -r "file" ]]
[[ "$VAR" =~ ^[0-9]+$ ]]        # regex match
```

---

## Loops

```bash
# For loop
for file in tests/test_*.py; do
    echo "Running: $file"
    pytest "$file"
done

# For loop over array
for browser in chromium firefox webkit; do
    pytest --browser "$browser" -m smoke
done

# C-style for loop
for ((i=0; i<5; i++)); do
    echo "Attempt $i"
done

# While loop
while IFS= read -r line; do
    echo "Processing: $line"
done < input.txt

# While with counter
COUNT=0
while [ $COUNT -lt 3 ]; do
    pytest tests/ && break
    COUNT=$((COUNT + 1))
    sleep 5
done

# Until loop
until curl -s https://api.example.com/health | grep -q "ok"; do
    echo "Waiting for API..."
    sleep 2
done
```

---

## Functions

```bash
# Define function
run_tests() {
    local suite="$1"
    local env="$2"
    echo "Running $suite on $env"
    pytest "tests/$suite" --env "$env"
}

# Call function
run_tests "smoke" "staging"

# Return value
get_status_code() {
    local url="$1"
    curl -s -o /dev/null -w "%{http_code}" "$url"
}

STATUS=$(get_status_code "https://hapi.fhir.org/baseR4/metadata")
echo "Status: $STATUS"

# Exit on failure
set -e             # exit on any error
set -u             # treat unset vars as errors
set -o pipefail    # catch errors in pipes

# Script header best practice
#!/usr/bin/env bash
set -euo pipefail
```

---

## Process Management

```bash
# Run in background
pytest tests/ &
PID=$!

# Wait for background job
wait $PID
echo "Exit code: $?"

# Kill process
kill $PID
kill -9 $PID           # force kill

# Find process by name
ps aux | grep pytest
pgrep -l pytest
pkill pytest

# Port usage
lsof -i :8080
lsof -i :3000

# Kill process on port
kill -9 $(lsof -t -i:8080)

# Run with timeout
timeout 60 pytest tests/slow_test.py

# Background + log
nohup pytest tests/ > test_output.log 2>&1 &
```

---

## Networking

```bash
# curl — the daily workhorse
curl https://hapi.fhir.org/baseR4/metadata

# with headers
curl -H "Accept: application/json" https://api.example.com/Patient

# POST JSON
curl -X POST https://api.example.com/Patient \
     -H "Content-Type: application/json" \
     -d '{"resourceType":"Patient","name":[{"family":"Doe"}]}'

# with auth
curl -u user:pass https://api.example.com
curl -H "Authorization: Bearer $TOKEN" https://api.example.com

# Follow redirects, show status
curl -L -o /dev/null -s -w "%{http_code}" https://example.com

# Download file
curl -O https://example.com/file.zip
curl -o output.zip https://example.com/file.zip

# Test connectivity
ping -c 3 google.com
traceroute google.com
nc -zv api.example.com 443           # check port open

# DNS
nslookup api.example.com
dig api.example.com
```

---

## Archives & Compression

```bash
# tar
tar -czf archive.tar.gz ./reports/          # create gzip archive
tar -xzf archive.tar.gz                     # extract
tar -tzf archive.tar.gz                     # list contents
tar -czf archive.tar.gz --exclude="*.pyc" ./src

# zip
zip -r reports.zip ./reports/
unzip reports.zip
unzip -l reports.zip                        # list contents

# gzip single file
gzip file.txt                               # creates file.txt.gz
gunzip file.txt.gz
```

---

## Permissions

```bash
# chmod
chmod +x script.sh                 # make executable
chmod 755 script.sh                # rwxr-xr-x
chmod 644 config.yaml              # rw-r--r--
chmod -R 755 ./scripts/            # recursive

# chown
chown user:group file.txt
chown -R user:group ./project/

# Check permissions
ls -la file.txt
stat file.txt

# Umask
umask 022                          # default new file permissions
```

---

## Script Patterns

### Robust script header

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

### Logging helper

```bash
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO  $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN  $*" >&2; }
err()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR $*" >&2; exit 1; }

log "Starting test run..."
warn "Retrying failed tests..."
err "Required env var TEST_USER not set"
```

### Wait for service

```bash
wait_for_service() {
    local url="$1"
    local max_attempts="${2:-30}"
    local attempt=0
    until curl -sf "$url" > /dev/null; do
        attempt=$((attempt + 1))
        [ $attempt -ge $max_attempts ] && err "Service never ready: $url"
        echo "Waiting for $url... ($attempt/$max_attempts)"
        sleep 2
    done
    log "Service ready: $url"
}

wait_for_service "http://localhost:3000/health"
```

### Parse CLI arguments

```bash
#!/usr/bin/env bash
BROWSER="chromium"
ENV="staging"
MARKER="smoke"

while [[ $# -gt 0 ]]; do
    case $1 in
        --browser) BROWSER="$2"; shift 2 ;;
        --env)     ENV="$2";     shift 2 ;;
        --marker)  MARKER="$2";  shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

pytest --browser "$BROWSER" -m "$MARKER" --env "$ENV"
```

---

## CI Debugging Patterns

```bash
# Find failing test in large log
grep -A 5 "FAILED" pytest_output.log

# Count test results
grep -c "PASSED" pytest_output.log
grep -c "FAILED" pytest_output.log
grep -c "ERROR"  pytest_output.log

# Extract slow tests
grep "slow" pytest_output.log | sort -t'.' -k2 -rn | head -10

# Check env vars are set in CI
printenv | grep -E "BASE_URL|TEST_USER|CI" | sort

# Inspect Docker network
docker network ls
docker network inspect bridge

# Check what's listening on a port
ss -tlnp | grep 8080
lsof -i :8080

# Tail multiple log files
tail -f logs/app.log logs/test.log

# Compare two CI run outputs
diff <(grep "FAILED" run1.log) <(grep "FAILED" run2.log)

# Check exit codes
pytest tests/ ; echo "Exit code: $?"
```

---

## Gotchas

### Quote your variables

```bash
# WRONG — breaks on spaces
rm -rf $BUILD_DIR

# RIGHT
rm -rf "$BUILD_DIR"
```

### Use `[[` not `[` for string tests

```bash
# WRONG — can break with empty vars
if [ $VAR == "value" ]; then ...

# RIGHT
if [[ "$VAR" == "value" ]]; then ...
```

### `set -e` and pipelines

```bash
# set -e won't catch this without pipefail
grep "pattern" file.txt | wc -l

# RIGHT — add at top of script
set -euo pipefail
```

### `cd` in subshell

```bash
# WRONG — changes dir only inside subshell
(cd /tmp && do_something)
echo $PWD    # still original dir — OK actually, use this pattern!

# Use pushd/popd for explicit stack management
pushd /tmp
do_something
popd
```

---

## Quick Reference Card

| Command | Purpose |
|---|---|
| `grep -rn "pattern" .` | Recursive search with line numbers |
| `grep -C 3 "ERROR" log` | 3 lines of context around match |
| `awk -F',' '{print $2}' file` | Print column 2 of CSV |
| `sed -i 's/old/new/g' file` | In-place find/replace |
| `find . -name "*.py" -mtime -7` | Python files changed in 7 days |
| `find . -name "*.pyc" -delete` | Delete all .pyc files |
| `xargs -P 4` | Run 4 processes in parallel |
| `tail -f app.log \| grep ERROR` | Live log filtering |
| `curl -s -o /dev/null -w "%{http_code}" URL` | Get HTTP status code |
| `set -euo pipefail` | Strict mode script header |
| `timeout 60 command` | Kill command after 60s |
| `lsof -i :8080` | What's using port 8080 |
| `export $(grep -v '^#' .env \| xargs)` | Load .env file |
| `diff <(cmd1) <(cmd2)` | Diff two command outputs |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) daily playbooks*
