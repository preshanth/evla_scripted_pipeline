######################################################################
#
# Copyright (C) 2013
# Associated Universities, Inc. Washington DC, USA,
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Library General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Library General Public
# License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; if not, write to the Free Software Foundation,
# Inc., 675 Massachusetts Ave, Cambridge, MA 02139, USA.
#
# Correspondence concerning VLA Pipelines should be addressed as follows:
#    Please register and submit helpdesk tickets via: https://help.nrao.edu
#    Postal address:
#              National Radio Astronomy Observatory
#              VLA Pipeline Support Office
#              PO Box O
#              Socorro, NM,  USA
#
######################################################################

import os
import shelve
import warnings
from pathlib import Path

from casatasks import version


__version__ = (2, 0, 0)
__version_str__ = ".".join(str(i) for i in __version__)
print(f":: EVLA scripted pipeline v{__version_str__} tested on CASA 6.1.0-118.")

casa_version = tuple(version())
assert len(casa_version) == 4
if casa_version[0] != 6:
    raise RuntimeError("This scripted pipeline is built for use with CASA 6.")
if casa_version[:-1] > (6, 1, 0):
    warnings.warn("The scripted pipeline has only been tested up to CASA v6.1.0.")


PIPE_PATH = Path(__file__).parent


def pipeline_save(filen="pipeline_shelf.restore"):
    with shelve.open(filen, "c") as shelf:
        with open(PIPE_PATH / "EVLA_pipe_restore.list") as f:
            lines = f.read().split("\n")
        for key in lines:
            if key == "":
                continue
            try:
                shelf[key] = globals()[key]
            except KeyError:
                pass


def pipeline_restore(filen="pipeline_shelf.restore"):
    if not os.path.exists(filen):
        raise ValueError(f"Restore point does not exist: {filen}")
    else:
        with shelve.open(filen) as shelf:
            globals().update(shelf)


def execfile(filepath, global_vars=None):
    if global_vars is None:
        global_vars = {}
    global_vars.update({
        "__file__": filepath,
        "__name__": "__main__",
    })
    with open(filepath, "rb") as f:
        source = compile(f.read(), filepath, "exec")
    exec(source, global_vars, global_vars)


def exec_script(name, context):
    script_path = str(PIPE_PATH / f"{name}.py")
    execfile(script_path, global_vars=context)


def run_pipeline(context=None):
    if context is None:
        context = globals()
    try:
        # The following script includes all the definitions and functions and
        # prior inputs needed by a run of the pipeline.
        #exec_script("EVLA_pipe_startup", context)

        # Import the data to CASA.
        #exec_script("EVLA_pipe_import", context)

        # Hanning smooth.
        # NOTE: This step is optional and likely unwanted for spectral line
        # projects, but Hanning may be important if there is strong, narrowband RFI.
        #exec_script("EVLA_pipe_hanning", context)

        # Get information from the MS that will be needed later, list the data, and
        # write generic diagnostic plots.
        #exec_script("EVLA_pipe_msinfo", context)

        # Deterministic flagging: (1) time-based for online flags, shadowed data,
        # zeroes, pointing scans, quacking, and (2) channel-based for end 5% of
        # channels of each SpW, 10 end channels at edges of basebands.
        #exec_script("EVLA_pipe_flagall", context)

        # Prepare for calibrations. Fill model columns for primary calibrators.
        #exec_script("EVLA_pipe_calprep", context)

        # Apply "prior" calibrations (gain curves, opacities, antenna position
        # corrections, and requantizer gains). Plot switched power tables,
        # although not currently used in calibration.
        #exec_script("EVLA_pipe_priorcals", context)

        # Initial test calibrations using bandpass and delay calibrators.
        #exec_script("EVLA_pipe_testBPdcals", context)

        # Identify and flag basebands with bad deformatters or RFI based on
        # the bandpass table amplitudes and phases.
        #exec_script("EVLA_pipe_flag_baddeformatters", context)

        # Flag possible RFI on the bandpass calibrator using `rflag`.
        #exec_script("EVLA_pipe_checkflag", context)

        # Do semi-final delay and bandpass calibrations. This step is "semi-final"
        # because we have not yet determined the spectral index of the bandpass
        # calibrator.
        #exec_script("EVLA_pipe_semiFinalBPdcals1", context)

        # Use flagdata again on calibrators
        exec_script("EVLA_pipe_checkflag_semiFinal", context)
        return context  # XXX

        # Re-run semiFinalBPdcals following flagging with `rflag` above.
        exec_script("EVLA_pipe_semiFinalBPdcals1", context)

        # Determine solution interval (solint) for scan-average equivalent.
        exec_script("EVLA_pipe_solint", context)

        # Do test gain calibrations to establish short solution interval.
        exec_script("EVLA_pipe_testgains", context)

        # Make gain table for flux density bootstrapping. Create gain table with
        # gain and opacity corrections for final amplitude calibration for flux
        # density bootstrapping.
        exec_script("EVLA_pipe_fluxgains", context)

        # Flag gain table prior to flux density bootstrapping.
        # NOTE: Break here to flag the gain table interatively, if desired; this
        # step is not included in real-time pipeline otherwise.
        #exec_script("EVLA_pipe_fluxflag", context)

        # Perform the flux density bootstrapping. This fits spectral index of
        # calibrators with a power-law and writes values into the model column.
        exec_script("EVLA_pipe_fluxboot", context)

        # Make final calibration tables.
        exec_script("EVLA_pipe_finalcals", context)

        # Apply all calibrations and check calibrated data.
        exec_script("EVLA_pipe_applycals", context)

        # Now run all calibrated data (including target) through `rflag`.
        exec_script("EVLA_pipe_targetflag", context)

        # Calculate data weights based on standard deviation within each SpW.
        exec_script("EVLA_pipe_statwt", context)

        # Make final uv plots.
        exec_script("EVLA_pipe_plotsummary", context)

        # Collect relevant plots and tables.
        exec_script("EVLA_pipe_filecollect", context)

        # Write weblog.
        exec_script("EVLA_pipe_weblog", context)
    except KeyboardInterrupt as e:
        logprint(f"Keyboard Interrupt: {e}")
    return context

