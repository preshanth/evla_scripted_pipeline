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
import shutil
from glob import glob

from casatasks import hanningsmooth

from .utils import (runtiming, logprint, pipeline_save)


logfileout = "logs/hanning.log"
logprint("Starting EVLA_pipe_hanning.py", logfileout=logfileout)
time_list = runtiming('hanning', 'start')
QA2_hanning = "Pass"

if do_hanning:
    logprint("Hanning smoothing the data", logfileout=logfileout)
    hanningsmooth(
        vis=msname,
        datacolumn="data",
        outputvis="temphanning.ms",
    )

    logprint("Copying xml files to the output ms")
    for filen in glob(f"{msname}/*.xml"):
        shutil.copy2(filen , "temphanning.ms/")
    logprint(f"Removing original VIS {msname}", logfileout=logfileout)
    shutil.rmtree(msname)

    logprint(f"Renaming temphanning.ms to {msname}", logfileout=logfileout)
    os.rename("temphanning.ms", msname)
else:
    logprint("NOT Hanning smoothing the data", logfileout=logfileout)

# Until we know better the possible failures modes of this script,
# leave set QA2 score set to "Pass".

logprint("Finished EVLA_pipe_hanning.py", logfileout=logfileout)
logprint(f"QA2 score: {QA2_hanning}", logfileout=logfileout)
time_list = runtiming("hanning", "end")

pipeline_save()

