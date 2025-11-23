#!/usr/bin/env python3
"""
Add wrapper functions and @register_step decorators to remaining scripts.

For scripts where main function is not named EVLA_pipe_*, adds wrapper.
"""

import re
from pathlib import Path

# Map of script names to their main function names
FUNCTION_MAP = {
    'EVLA_pipe_applycals': 'applycals',
    'EVLA_pipe_calprep': 'calprep',
    'EVLA_pipe_solint': 'solint',
    'EVLA_pipe_fluxboot': 'fluxboot',
    'EVLA_pipe_polcal': 'polcal',
    'EVLA_pipe_semiFinalBPdcals1': 'semifinalbpdcals1',  # lowercase in actual code
    'EVLA_pipe_checkflag_semiFinal': 'checkflag_semifinal',  # no underscore
    'EVLA_pipe_fluxflag': 'fluxflag',
    'EVLA_pipe_testBPdcals': 'testbpdcals',  # lowercase
}


def add_wrapper(filepath, step_name, func_name):
    """Add wrapper function and decorator."""
    content = filepath.read_text()

    # Check if already has wrapper
    if f"def {step_name}(" in content:
        return False, "Already has wrapper"

    # Check if already has register_step import
    has_import = 'from evla_pipe.pipeline_steps import register_step' in content

    # Check if main function exists
    if f"def {func_name}(" not in content:
        return False, f"No {func_name}() function found"

    lines = content.split('\n')

    # Add import if needed
    if not has_import:
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i
        lines.insert(last_import_idx + 1, "from evla_pipe.pipeline_steps import register_step")

    # Find end of file (or last function)
    wrapper = f'''

@register_step("{step_name}")
def {step_name}(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper for {func_name}() to match expected step name.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context dictionary

    Returns
    -------
    dict
        Updated pipeline context
    """
    return {func_name}(pipeline_context)
'''

    # Append wrapper at end
    lines.append(wrapper)

    new_content = '\n'.join(lines)
    filepath.write_text(new_content)

    return True, f"Added wrapper for {func_name}()"


if __name__ == '__main__':
    pipeline_dir = Path('evla_pipe')

    migrated = 0
    skipped = 0

    for step_name, func_name in FUNCTION_MAP.items():
        filepath = pipeline_dir / f"{step_name}.py"

        if not filepath.exists():
            print(f"⊗ {step_name}.py: File not found")
            skipped += 1
            continue

        success, msg = add_wrapper(filepath, step_name, func_name)
        status = "✓" if success else "⊗"
        print(f"{status} {step_name}.py: {msg}")

        if success:
            migrated += 1
        else:
            skipped += 1

    print(f"\n{migrated} migrated, {skipped} skipped")
