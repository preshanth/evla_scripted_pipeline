#!/usr/bin/env python3
"""
Bulk migrate legacy EVLA_pipe_* scripts to registry pattern.

Adds:
1. Import for register_step
2. @register_step decorator to main function
"""

import re
from pathlib import Path

def migrate_script(filepath):
    """Migrate a single script file."""
    content = filepath.read_text()

    # Extract function name from filename
    step_name = filepath.stem  # e.g., "EVLA_pipe_hanning"

    # Check if already has register_step import
    if 'from evla_pipe.pipeline_steps import register_step' in content:
        return False, "Already migrated"

    # Check if file has the expected function (with any parameter)
    func_pattern = f"def {step_name}\\("
    if not re.search(func_pattern, content):
        return False, f"No function {step_name}() found"

    # Add import after existing imports
    import_line = "from evla_pipe.pipeline_steps import register_step\n"

    # Find last import line
    lines = content.split('\n')
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_idx = i

    # Insert register_step import
    lines.insert(last_import_idx + 1, import_line.rstrip())

    # Add decorator before function definition
    decorator = f"@register_step(\"{step_name}\")\n"
    new_lines = []
    for i, line in enumerate(lines):
        if re.match(func_pattern, line):
            # Add decorator before function
            new_lines.append(decorator.rstrip())
        new_lines.append(line)

    new_content = '\n'.join(new_lines)
    filepath.write_text(new_content)

    return True, "Migrated"


if __name__ == '__main__':
    pipeline_dir = Path('evla_pipe')

    # Find all EVLA_pipe_*.py files (exclude legacy, testing, refactored)
    scripts = []
    for f in pipeline_dir.glob('EVLA_pipe_*.py'):
        if 'legacy' in f.name or 'testing' in f.name or 'refactored' in f.name:
            continue
        scripts.append(f)

    print(f"Found {len(scripts)} scripts to migrate\n")

    migrated = 0
    skipped = 0

    for script in sorted(scripts):
        success, msg = migrate_script(script)
        status = "✓" if success else "⊗"
        print(f"{status} {script.name}: {msg}")

        if success:
            migrated += 1
        else:
            skipped += 1

    print(f"\n{migrated} migrated, {skipped} skipped")
