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


