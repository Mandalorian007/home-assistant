# Prime

Validate environment and understand the codebase.

## Step 1: Validate Environment

Run `uv run .claude/scripts/check_env.py` to check required variables.

If anything is missing, help the user fix it:
- `E2B_API_KEY`: Get from https://e2b.dev/dashboard/keys
- `GH_TOKEN`: GitHub PAT with repo scope
- `PERPLEXITY_API_KEY`: Get from https://www.perplexity.ai/settings/api

Stop here if environment is not valid.

## Step 2: Understand Codebase

@README.md
@.claude/skills/*/SKILL.md
@docs/
!`git ls-files`

## Report

1. Environment status
2. Your understanding of the codebase and instructions

## Optional

If the user asks to create a new skill, read `.claude/skills/README.md` for authoring guidelines.
