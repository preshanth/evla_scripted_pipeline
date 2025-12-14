"""
Helper functions for compatibility across CASA versions and monolithic/modular
frameworks.
"""

# The `casalog` symbol is a built-in in the monolithic CASA namespace. If it
# doesn't exist, then that means we are using modular CASA in a user's Python
# environment.
try:
    casalog
    running_within_casa = True
except NameError:
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
