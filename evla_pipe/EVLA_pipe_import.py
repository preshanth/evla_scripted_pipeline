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
import glob
import shutil

from casatasks import importasdm

from .utils import (runtiming, logprint, pipeline_save)


logprint("Starting EVLA_pipe_import.py", logfileout="logs/import.log")
time_list = runtiming("import", "start")
QA2_import = "Pass"

if not os.path.exists(msname):
    logprint("Creating measurement set", logfileout="logs/import.log")
    importasdm(
        asdm=SDM_name,
        vis=msname,
        ocorr_mode="co",
        compression=False,
        asis="",
        process_flags=True,
            applyflags=False,
            savecmds=True,
            outfile="onlineFlags.txt",
        flagbackup=False,
        overwrite=False,
        verbose=True,
        # FIXME keyword arguments in latest versions of CASA
        #with_pointing_correction=True,
        #process_pointing=True,
        #process_caldevice=True,
    )
    logprint(f"Measurement set '{msname}' created", logfileout="logs/import.log")
    logprint("Copying xml files to the output ms")
    for xml_file in ("Flag", "Antenna", "SpectralWindow"):
        shutil.copy2(f"{SDM_name}/{xml_file}.xml", f"{msname}/")
else:
    logprint(
            f"Measurement set already exists, will use '{msname}'",
            logfileout="logs/import.log",
    )

# Until we understand better the possible failure modes to look for
# in this script, leave QA2 set to "Pass".

logprint("Finished EVLA_pipe_import.py", logfileout="logs/import.log")
logprint(f"QA2 score: {QA2_import}", logfileout="logs/import.log")
time_list = runtiming("import", "end")

pipeline_save()

