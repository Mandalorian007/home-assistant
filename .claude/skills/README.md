# Authoring Skills

## Progressive Disclosure Pattern

Skills use **progressive disclosure** to manage context efficiently. The SKILL.md file should be minimal—point to `--help` for discovery rather than documenting every command.

### Why?

SKILL.md is loaded into Claude's context when the skill is invoked. Large documentation wastes tokens. The CLI's `--help` is only loaded when explicitly run.

### Pattern

**SKILL.md** - Minimal, points to CLI:
```markdown
## Instructions

Run from CLI_PATH:
```bash
cd <path>
uv run <cmd> --help                # Discover all commands
uv run <cmd> <subcommand> --help   # Detailed usage
```

**Rules:**
- Key gotcha #1
- Key gotcha #2
```

**CLI** - Contains examples in help text:
```python
@click.command()
def cli():
    """
    Short description.

    \b
    EXAMPLES
    --------
    uv run cmd "example 1"
    uv run cmd "example 2"
    """
```

### Structure

```
skills/
└── my-skill/
    ├── SKILL.md              # Minimal - loaded into context
    └── my_cli/
        ├── pyproject.toml
        ├── src/
        │   └── main.py       # Help text lives here
        └── .python-version
```

### Checklist

- [ ] SKILL.md < 50 lines
- [ ] Points to `--help` for discovery
- [ ] Rules section for critical gotchas only
- [ ] CLI help includes examples
- [ ] Troubleshooting for common errors
