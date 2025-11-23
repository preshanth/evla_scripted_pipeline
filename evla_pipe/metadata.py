"""
Recipe generation for pipeline reproducibility.

Generates executable scripts that reproduce pipeline calibration state
by recording applycal commands and calibration table verification.
"""

from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from evla_pipe.logging_config import get_logger

logger = get_logger(__name__)

# Global recipe accumulator
_RECIPE_STEPS = []


def add_recipe_step(step_type: str, command: str, description: str, caltables: List[str] = None) -> None:
    """
    Add a step to the pipeline recipe.

    Parameters
    ----------
    step_type : str
        Type of step: 'applycal', 'verification', 'info'
    command : str
        Command to execute (Python or CASA syntax)
    description : str
        Human-readable description of step
    caltables : list of str, optional
        Calibration tables required for this step
    """
    step = {
        'type': step_type,
        'command': command,
        'description': description,
        'timestamp': datetime.now().isoformat(),
        'caltables': caltables or []
    }
    _RECIPE_STEPS.append(step)
    logger.debug(f"Added recipe step: {description}")


def generate_recipe_script(
    pipeline_context: Dict[str, Any],
    output_path: Path = None,
    format: str = 'python'
) -> str:
    """
    Generate executable script to reproduce pipeline state.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context with all parameters and paths
    output_path : Path, optional
        Path to save recipe script. If None, returns script as string
    format : str
        Script format: 'python' or 'casa'

    Returns
    -------
    str
        Generated script content
    """
    if not output_path:
        output_path = Path("pipeline_recipe.py")

    msname = pipeline_context.get('msname', 'unknown.ms')
    timestamp = datetime.now().isoformat()

    # Build script
    if format == 'python':
        script = _generate_python_recipe(pipeline_context, timestamp)
    else:
        script = _generate_casa_recipe(pipeline_context, timestamp)

    # Save to file
    with open(output_path, 'w') as f:
        f.write(script)

    logger.info(f"Generated recipe script: {output_path}")
    return script


def _generate_python_recipe(context: Dict[str, Any], timestamp: str) -> str:
    """Generate Python/CASA script."""
    msname = context.get('msname', 'unknown.ms')
    refant = context.get('refant', 'ea01')

    script_lines = [
        '#!/usr/bin/env python',
        '"""',
        'EVLA Pipeline Calibration Recipe',
        f'Generated: {timestamp}',
        f'MS: {msname}',
        '',
        'This script reproduces the pipeline calibration state by applying',
        'calibration tables with verification that all tables exist.',
        '"""',
        '',
        'from pathlib import Path',
        'import sys',
        '',
        'try:',
        '    from casatasks import applycal',
        'except ImportError:',
        '    print("ERROR: casatasks not available")',
        '    sys.exit(1)',
        '',
        f'# Configuration',
        f'msname = "{msname}"',
        f'refant = "{refant}"',
        '',
        '# Verify MS exists',
        'if not Path(msname).exists():',
        '    print(f"ERROR: Measurement set not found: {msname}")',
        '    sys.exit(1)',
        '',
        'print(f"Applying calibration to {msname}")',
        'print(f"Reference antenna: {refant}")',
        '',
    ]

    # Extract applycal commands from recipe steps
    applycal_steps = [s for s in _RECIPE_STEPS if s['type'] == 'applycal']

    if applycal_steps:
        script_lines.append('# Calibration tables to apply')
        script_lines.append('caltables = [')

        all_caltables = []
        for step in applycal_steps:
            for table in step.get('caltables', []):
                if table not in all_caltables:
                    all_caltables.append(table)
                    script_lines.append(f'    "{table}",')

        script_lines.append(']')
        script_lines.append('')

        # Add verification
        script_lines.extend([
            '# Verify all calibration tables exist',
            'missing_tables = []',
            'for table in caltables:',
            '    if not Path(table).exists():',
            '        missing_tables.append(table)',
            '        print(f"WARNING: Calibration table not found: {table}")',
            '',
            'if missing_tables:',
            '    print(f"ERROR: {len(missing_tables)} calibration tables missing")',
            '    print("Cannot apply calibration without all tables")',
            '    sys.exit(1)',
            '',
            'print(f"Verified {len(caltables)} calibration tables exist")',
            '',
        ])

        # Add applycal commands
        for i, step in enumerate(applycal_steps):
            script_lines.append(f'# Step {i+1}: {step["description"]}')
            script_lines.append('print(f"' + f'Step {i+1}: {step["description"]}' + '")')
            script_lines.append(step['command'])
            script_lines.append('')

        script_lines.extend([
            'print("Calibration successfully applied")',
            'print(f"Calibrated MS: {msname}")',
        ])
    else:
        script_lines.append('# No applycal steps recorded in this pipeline run')

    return '\n'.join(script_lines)


def _generate_casa_recipe(context: Dict[str, Any], timestamp: str) -> str:
    """Generate CASA script format."""
    msname = context.get('msname', 'unknown.ms')

    script_lines = [
        f'# EVLA Pipeline Calibration Recipe',
        f'# Generated: {timestamp}',
        f'# MS: {msname}',
        '',
        f'msname = "{msname}"',
        '',
    ]

    # Add applycal commands
    applycal_steps = [s for s in _RECIPE_STEPS if s['type'] == 'applycal']
    for i, step in enumerate(applycal_steps):
        script_lines.append(f'# {step["description"]}')
        script_lines.append(step['command'])
        script_lines.append('')

    return '\n'.join(script_lines)


def save_recipe_metadata(pipeline_context: Dict[str, Any], output_path: Path = None) -> None:
    """
    Save complete recipe metadata as JSON.

    Parameters
    ----------
    pipeline_context : dict
        Pipeline context
    output_path : Path, optional
        Path to save metadata JSON
    """
    if not output_path:
        output_path = Path("pipeline_recipe_metadata.json")

    metadata = {
        'pipeline_version': '2.0.0',
        'timestamp': datetime.now().isoformat(),
        'msname': pipeline_context.get('msname'),
        'refant': pipeline_context.get('refant'),
        'do_hanning': pipeline_context.get('do_hanning', False),
        'do_polarization': pipeline_context.get('do_pol', False),
        'steps': _RECIPE_STEPS,
        'qa_scores': {k: v for k, v in pipeline_context.items() if k.startswith('QA2_')}
    }

    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved recipe metadata: {output_path}")


def clear_recipe() -> None:
    """Clear accumulated recipe steps."""
    global _RECIPE_STEPS
    _RECIPE_STEPS = []
