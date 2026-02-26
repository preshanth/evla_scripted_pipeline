"""
Helper functions for compatibility across CASA versions and monolithic/modular
frameworks.
"""

# `casalog` is a built-in name only in monolithic CASA.
# In modular CASA (casatools pip package) it must be imported.
# We treat both cases as "running within CASA" so utils.py initialises
# its module-level tool instances (me, tb, qa, ...) correctly.
try:
    casalog  # monolithic CASA: casalog is a builtin
    running_within_casa = True
except NameError:
    try:
        from casatools import measures as _  # modular CASA available
        running_within_casa = True
    except ImportError:
        running_within_casa = False


def import_casa_modules():
    """
    Import CASA modules with proper error handling.

    Returns:
        dict: Dictionary containing imported CASA modules or None if not available
    """
    casa_modules = {}

    try:
        from casatasks import applycal, gaincal, polcal, setjy
        from casatools import msmetadata

        casa_modules.update(
            {
                "setjy": setjy,
                "gaincal": gaincal,
                "polcal": polcal,
                "applycal": applycal,
                "msmetadata": msmetadata,
                "available": True,
            }
        )

    except ImportError as e:
        casa_modules.update(
            {
                "setjy": None,
                "gaincal": None,
                "polcal": None,
                "applycal": None,
                "msmetadata": None,
                "available": False,
                "error": str(e),
            }
        )

    return casa_modules
