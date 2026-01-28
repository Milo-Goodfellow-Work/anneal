# Anneal - Universal Verification Agent

Generate verified C code from natural language prompts using Lean 4 formal verification.

## Quick Start

### Build and Run Container

```bash
# Build the image (includes Lean + pre-built Mathlib cache)
docker build -t anneal-dev .

# Run long-lived container
docker run -d --name anneal-work anneal-dev

# Attach VS Code
# 1. Install Docker extension in VS Code
# 2. Right-click 'anneal-work' container → "Attach Visual Studio Code"
# 3. Open folder: /app
```

### Run Generation

Inside the container:
```bash
python main.py --prompt "Create a memory arena"
```

### Reset Between Runs

**The critical step:** Before each new generation, reset the workspace to a clean state:

```bash
# Restore spec/ to clean state and remove all generated files
git checkout spec/
git clean -fdx generated/

# Now run your next generation
python main.py --prompt "Create a hash table"
```

**Why this is needed:** 
- Anneal modifies `spec/` during code generation (adds Lean modules)
- `git checkout spec/` restores `spec/` to its clean template state from git
- `git clean -fdx generated/` removes all untracked files in `generated/`
- `spec/` and `generated/` are **intentionally tracked** in git so you can reset them

## Git Workflow

You can commit from inside the container:
```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"

# Make changes to source code
git add stages/ main.py helpers.py
git commit -m "Added feature"
git push
```

**Notes:** 
- `spec/` and `generated/` are tracked in git, so after running generation you'll see them as modified
- **Don't commit** modifications to `spec/` or `generated/` - reset them instead (see above)
- Only commit changes to source code (Python files, Dockerfiles, etc.)

## Rebuilding

After pushing code changes, rebuild the image to get the latest:
```bash
docker build -t anneal-dev .
docker stop anneal-work && docker rm anneal-work
docker run -d --name anneal-work anneal-dev
```
