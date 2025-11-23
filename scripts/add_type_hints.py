#!/usr/bin/env python3
"""
Add type hints to all pipeline scripts.
"""

import re
from pathlib import Path

# All pipeline scripts that need type hints
SCRIPTS = [
    "EVLA_pipe_import.py",
    "EVLA_pipe_msmd.py",
    "EVLA_pipe_startup.py",
    "EVLA_pipe_filecollect.py",
    "EVLA_pipe_fluxgains.py",
    "EVLA_pipe_testgains.py",
    "EVLA_pipe_flag_baddeformatters.py",
    "EVLA_pipe_flagall.py",
    "EVLA_pipe_priorcals.py",
    "EVLA_pipe_checkflag.py",
    "EVLA_pipe_statwt.py",
    "EVLA_pipe_finalcals.py",
    "EVLA_pipe_targetflag.py",
    "EVLA_pipe_polcal.py",
    "EVLA_pipe_applycals.py",
    "EVLA_pipe_fluxflag.py",
    "EVLA_pipe_solint.py",
    "EVLA_pipe_calprep.py",
    "EVLA_pipe_fluxboot.py",
    "EVLA_pipe_semiFinalBPdcals1.py",
    "EVLA_pipe_checkflag_semiFinal.py",
    "EVLA_pipe_testBPdcals.py",
    "EVLA_pipe_plotsummary.py",
]

def add_type_hints(file_path):
    """Add type hints to a pipeline script."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if typing import already exists
    has_typing_import = re.search(r'^from typing import', content, re.MULTILINE)

    if not has_typing_import:
        # Find the last import line
        import_lines = list(re.finditer(r'^(?:from|import)\s+\S+', content, re.MULTILINE))
        if import_lines:
            last_import = import_lines[-1]
            insert_pos = last_import.end()
            # Insert after the last import
            content = (
                content[:insert_pos] +
                "\nfrom typing import Dict, Any" +
                content[insert_pos:]
            )
        else:
            # No imports found, add after shebang/docstring
            # Find end of module docstring or first non-comment line
            lines = content.split('\n')
            insert_line = 0
            in_docstring = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if in_docstring:
                        insert_line = i + 1
                        break
                    else:
                        in_docstring = True
                elif not in_docstring and stripped and not stripped.startswith('#'):
                    insert_line = i
                    break

            lines.insert(insert_line, "from typing import Dict, Any")
            lines.insert(insert_line, "")
            content = '\n'.join(lines)

    # Add type hints to function definitions
    # Pattern: def function_name(pipeline_context):
    # Replace with: def function_name(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:

    # Find all function definitions with pipeline_context parameter
    def add_hints_to_func(match):
        indent = match.group(1)
        func_name = match.group(2)
        # Check if already has type hints
        if ':' in match.group(3) or '->' in match.group(0):
            return match.group(0)  # Already has type hints
        return f"{indent}def {func_name}(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:"

    content = re.sub(
        r'^(\s*)def (\w+)\((pipeline_context)\):',
        add_hints_to_func,
        content,
        flags=re.MULTILINE
    )

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✓ Added type hints to {file_path.name}")

def main():
    evla_pipe_dir = Path(__file__).parent.parent / "evla_pipe"

    for script_name in SCRIPTS:
        script_path = evla_pipe_dir / script_name
        if script_path.exists():
            add_type_hints(script_path)
        else:
            print(f"✗ Script not found: {script_name}")

    print(f"\n✅ Processed {len(SCRIPTS)} scripts")

if __name__ == "__main__":
    main()
