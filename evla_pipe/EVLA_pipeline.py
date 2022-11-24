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


# The following script includes all the definitions and functions and
# prior inputs needed by a run of the pipeline.
runtiming('startup', 'start')
execfile(pipepath+'EVLA_pipe_startup.py')
runtiming('startup', 'end')
pipeline_save()


try:
    # Import the data to CASA.
    execfile(pipepath+'EVLA_pipe_import.py')

    # Hanning smooth.
    # NOTE: This step is optional and likely unwanted for spectral line
    # projects, but Hanning may be important if there is strong narrowband RFI.
    execfile(pipepath+'EVLA_pipe_hanning.py')

    # Get information from the MS that will be needed later, list the data, and
    # write generic diagnostic plots.
    execfile(pipepath+'EVLA_pipe_msinfo.py')

    # Deterministic flagging: (1) time-based for online flags, shadowed data,
    # zeroes, pointing scans, quacking, and (2) channel-based for end 5% of
    # channels of each SpW, 10 end channels at edges of basebands.
    execfile(pipepath+'EVLA_pipe_flagall.py')

    # Prepare for calibrations. Fill model columns for primary calibrators.
    execfile(pipepath+'EVLA_pipe_calprep.py')

    # Apply "prior" calibrations (gain curves, opacities, antenna position
    # corrections, and requantizer gains). Plot switched power tables,
    # although not currently used in calibration.
    execfile(pipepath+'EVLA_pipe_priorcals.py')

    # Initial test calibrations using bandpass and delay calibrators.
    execfile(pipepath+'EVLA_pipe_testBPdcals.py')

    # Identify and flag basebands with bad deformatters or RFI based on
    # the bandpass table amplitudes.
    execfile(pipepath+'EVLA_pipe_flag_baddeformatters.py')

    # Identify and flag basebands with bad deformatters or RFI based on
    # bandpass table phases.
    execfile(pipepath+'EVLA_pipe_flag_baddeformattersphase.py')

    # Flag possible RFI on the bandpass calibrator using `rflag`.
    execfile(pipepath+'EVLA_pipe_checkflag.py')

    # Do semi-final delay and bandpass calibrations. This step is "semi-final"
    # because we have not yet determined the spectral index of the bandpass
    # calibrator.
    execfile(pipepath+'EVLA_pipe_semiFinalBPdcals1.py')

    # Use flagdata again on calibrators
    execfile(pipepath+'EVLA_pipe_checkflag_semiFinal.py')

    # Re-run semiFinalBPdcals.py following flagging with `rflag`.
    execfile(pipepath+'EVLA_pipe_semiFinalBPdcals2.py')

    # Determine solution interval (solint) for scan-average equivalent.
    execfile(pipepath+'EVLA_pipe_solint.py')

    # Do test gain calibrations to establish short solution interval.
    execfile(pipepath+'EVLA_pipe_testgains.py')

    # Make gain table for flux density bootstrapping. Create gain table with
    # gain and opacity corrections for final amplitude calibration for flux
    # density bootstrapping.
    execfile(pipepath+'EVLA_pipe_fluxgains.py')

    # Flag gain table prior to flux density bootstrapping.
    # NOTE: Break here to flag the gain table interatively, if desired; this
    # step is not included in real-time pipeline otherwise.
    #execfile(pipepath+'EVLA_pipe_fluxflag.py')

    # Perform the flux density bootstrapping. This fits spectral index of
    # calibrators with a power-law and writes values into the model column.
    execfile(pipepath+'EVLA_pipe_fluxboot.py')

    # Make final calibration tables.
    execfile(pipepath+'EVLA_pipe_finalcals.py')

    # Apply all calibrations and check calibrated data.
    execfile(pipepath+'EVLA_pipe_applycals.py')

    # Now run all calibrated data (including target) through `rflag`.
    execfile(pipepath+'EVLA_pipe_targetflag.py')

    # Calculate data weights based on standard deviation within each SpW.
    execfile(pipepath+'EVLA_pipe_statwt.py')

    # Make final uv plots.
    execfile(pipepath+'EVLA_pipe_plotsummary.py')

    # Collect relevant plots and tables.
    execfile(pipepath+'EVLA_pipe_filecollect.py')

    # Write weblog.
    execfile(pipepath+'EVLA_pipe_weblog.py')
except KeyboardInterrupt as keyboardException:
    logprint("Keyboard Interrupt: " + str(keyboardException))
except Exception as generalException:
    logprint("Exiting script: " + str(generalException))

