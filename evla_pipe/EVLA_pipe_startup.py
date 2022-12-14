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

# The pipeline assumes all files for a single dataset are located in
# the current directory, and that this directory contains only files
# relating to this dataset.

from .utils import runtiming

logprint("Starting EVLA_pipe_startup.py", logfileout='logs/startup.log')
runtiming('startup', 'start')


import os
import sys
import time
import copy
import pickle
import shutil
import shelve
import string
from time import gmtime, strftime
from math import sin, cos, acos, fabs, pi, e, log10

import numpy as np
import scipy as scp
import scipy.optimize as scpo


logprint(f"Running from path: {os.getcwd()}", 'logs/startup.log')

# File names
#
# if SDM_name is already defined, then assume it holds the SDM directory
# name, otherwise, read it in from stdin
#

SDM_name_already_defined = 1
try:
    SDM_name
except NameError:
    SDM_name_already_defined = 0
    SDM_name = input("Enter SDM file name: ")
    if SDM_name == "":
        raise RuntimeError("SDM name must be given.")

# Trap for '.ms', just in case, also for directory slash if present:

SDM_name=SDM_name.rstrip('/')
if SDM_name.endswith('.ms'):
    SDM_name = SDM_name[:-3]

msname=SDM_name+'.ms'
# this is terribly non-robust.  should really trap all the inputs from
# the automatic pipeline (the root directory and the relative paths).
# and also make sure that 'rawdata' only occurs once in the string.
# but for now, take the quick and easy route.
if SDM_name_already_defined:
    msname = msname.replace('rawdata', 'working')

if not os.path.isdir(msname):
    while not os.path.isdir(SDM_name) and not os.path.isdir(msname):
        print(f"{SDM_name} is not a valid SDM directory")
        SDM_name = input("Re-enter a valid SDM directory (without '.ms'): ")
        SDM_name = SDM_name.rstrip('/')
        if SDM_name.endswith('.ms'):
            SDM_name = SDM_name[:-3]
        msname = SDM_name+'.ms'

mshsmooth = SDM_name+'.hsmooth.ms'
if SDM_name_already_defined:
    mshsmooth = mshsmooth.replace('rawdata', 'working')
ms_spave = SDM_name + '.spave.ms'
if SDM_name_already_defined:
    ms_spave = ms_spave.replace('rawdata', 'working')

logprint("SDM used is: " + SDM_name, logfileout='logs/startup.log')

# Other inputs:

# Ask if a a real model column should be created, or the virtual model should
# be used.
mymodel_already_set = 1
try:
    mymodel
except NameError:
    mymodel_already_set = 0
    mymodel = input("Create the real model column (y/[n]): ").lower()
    mymodel = "n" if mymodel != "y" else mymodel
    scratch = mymodel == "y"

myHanning_already_set = 1
try:
    myHanning
except NameError:
    myHanning_already_set = 0
    hanning_input_results = input("Hanning smooth the data (y/[n]): ").lower()
    do_hanning = hanning_input_results not in ("", "n")

ms_active = msname

# And ask for auxiliary information.
try:
    projectCode
except NameError:
    projectCode = 'Unknown'
try:
    piName
except NameError:
    piName = 'Unknown'
try:
    piGlobalId
except NameError:
    piGlobalId = 'Unknown'
try:
    observeDateString
except NameError:
    observeDateString = 'Unknown'
try:
    pipelineDateString
except NameError:
    pipelineDateString = 'Unknown'


# For now, use same ms name for Hanning smoothed data, for speed.
# However, we only want to smooth the data the first time around, we do
# not want to do more smoothing on restarts, so note that this parameter
# is reset to "n" after doing the smoothing in EVLA_pipe_hanning.py.

logprint("Finished EVLA_pipe_startup.py", logfileout='logs/startup.log')
runtiming('startup', 'end')

pipeline_save()

