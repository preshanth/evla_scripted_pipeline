"""
Check the flagging of all calibrated data, including target using the `rflag`
mode of `flagdata`.
"""

logprint ("Starting EVLA_pipe_targetflag.py", logfileout='logs/targetflag.log')
time_list=runtiming('checkflag', 'start')
QA2_targetflag='Pass'

logprint ("Checking RFI flagging of all targets", logfileout='logs/targetflag.log')

# Run on all calibrator scans

default('flagdata')
vis=ms_active
mode='rflag'
field=''
correlation='ABS_'+corrstring
scan=''
intent='*CALIBRATE*'
ntime='scan'
combinescans=False
datacolumn='corrected'
winsize=3
timedevscale=4.0
freqdevscale=4.0
extendflags=False
action='apply'
display=''
flagbackup=True
savepars=True
flagdata()

# Run on all target scans
# Comment out if science target has strong spectral lines
# or set spw to exclude these strong science spectral lines

default('flagdata')
vis=ms_active
mode='rflag'
field=''
correlation='ABS_'+corrstring
scan=''
intent='*TARGET*'
ntime='scan'
combinescans=False
datacolumn='corrected'
winsize=3
timedevscale=4.0
freqdevscale=4.0
extendflags=False
action='apply'
display=''
flagbackup=True
savepars=True
flagdata()



#clearstat()

# Save final version of flags

default('flagmanager')
vis=ms_active
mode='save'
versionname='finalflags'
comment='Final flags saved after calibrations and rflag'
merge='replace'
flagmanager()
logprint ("Flag column saved to "+versionname, logfileout='logs/targetflag.log')

# calculate final flag statistics

default('flagdata')
vis=ms_active
mode='summary'
spwchan=True
spwcorr=True
basecnt=True
action='calculate'
savepars=False
final_flags = flagdata()

frac_flagged_on_source2 = 1.0-((start_total-final_flags['flagged'])/init_on_source_vis)

logprint ("Final fraction of on-source data flagged = "+str(frac_flagged_on_source2), logfileout='logs/targetflag.log')

if (frac_flagged_on_source2 >= 0.6):
    QA2_targetflag='Fail'

logprint ("QA2 score: "+QA2_targetflag, logfileout='logs/targetflag.log')
logprint ("Finished EVLA_pipe_targetflag.py", logfileout='logs/targetflag.log')
time_list=runtiming('targetflag', 'end')

pipeline_save()


######################################################################
