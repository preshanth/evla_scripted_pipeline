'''
Restore all variables needed by the pipeline into the global namespace.
'''

import shelve

# This is the default time-stamped casa log file, in case we need to return to
# it at any point in the script.
log_dir='logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

maincasalog = casalogger.func_globals['casa']['files']['logfile']

def logprint(msg, logfileout=maincasalog):
    print (msg)
    casalog.setlogfile(logfileout)
    casalog.post(msg)
    casalog.setlogfile(maincasalog)
    casalog.post(msg)
    return

#Create timing profile list and file if they don't already exist
if 'time_list' not in globals():
    time_list = []

timing_file='logs/timing.log'

if not os.path.exists(timing_file):
    timelog=open(timing_file,'w')
else:
    timelog=open(timing_file,'a')
    
def runtiming(pipestate, status):
    '''Determine profile for a given state/stage of the pipeline
    '''
    time_list.append({'pipestate':pipestate, 'time':time.time(), 'status':status})
    
    if (status == "end"):
        timelog=open(timing_file,'a')
        timelog.write(pipestate+': '+str(time_list[-1]['time'] - time_list[-2]['time'])+' sec \n')
        timelog.flush()
        timelog.close()
        #with open(maincasalog, 'a') as casalogfile:
        #    tempfile = open('logs/'+pipestate+'.log','r')
        #    casalogfile.write(tempfile.read())
        #    tempfile.close()
        #casalogfile.close()
        
    
    return time_list


def pipeline_restore(shelf_filename='pipeline_shelf.restore'):
    '''Restore the state of the pipeline from shelf file 
    '''
    if os.path.exists(shelf_filename):
        try:
            pipe_shelf = shelve.open(shelf_filename)
        except Exception, e:
            logprint ("Restore point does not exist: "+str(e))

        for key in pipe_shelf:
            try:
                globals()[key] = pipe_shelf[key]
                key_status = True
            except:
                key_status = False

        pipe_shelf.close()

#Restore all variables to the global namespace and then run 'startup'
#  to load all functions and modules needed for the pipeline
try:

    pipeline_restore()
    maincasalog = casalogger.func_globals['casa']['files']['logfile']
    execfile(pipepath+'EVLA_pipe_startup.py')
    

except Exception, e:
    logprint ("Exiting script: "+str(e))
