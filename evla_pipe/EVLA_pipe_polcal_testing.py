"""
Prepare for calibrations
========================

Fill models for all primary calibrators.
NB: in CASA 3.4.0 can only set models based on field ID and spw, not
by intents or scans
"""

from casatasks import setjy, split
import numpy as np
import scipy as sp
import math

from . import pipeline_save
from .utils import runtiming, logprint, find_standards, find_EVLA_band

pi = np.pi

def task_logprint(msg):
    logprint(msg, logfileout="logs/calprep.log")

def fitterI(freqI_band,a,b):
    '''
    fitterI fits flux I to the setjy equation, to get an alpha and beta
    (i.e. spix[0] and spix[1], respectively)
    '''
    I = np.array([])
    for i in range(len(freqI_band)):
            I = np.append(I, i_ref*(freqI_band[i]/refFreqI)**(a + (b*np.log10(freqI_band[i]/refFreqI))))
    return I

def fitter3(x,a,b,c,d):
     
    '''
    fitter4 is a 4th order polynomial that is used to fit polarization
    fraction (p)
    '''
    return a + b*x + c*(x**2) + d*(x**3) 


def fitter4(x,a,b,c,d,e):
    '''
    fitter4 is a 4th order polynomial that is used to fit polarization
    fraction (p)
    '''
    return a + b*x + c*(x**2) + d*(x**3) + e*(x**4)

'''
def polyFit(polAngleSource, band, refFreq, order=4):
    
    polyFit fits a polynomial of order 4 (default) for the polarization index
    (polindex) input for CASA command setjy dependent on flux density calibrator
    and band.  The polarization index is a list of coefficients for frequency-dep.
    linear polarization fraction, as similarly stated in CASA setjy documentation.

    Inputs:
            polAngleSource - one of 4 flux density calibrator source 
                ('3C48', '3C138', '3C147', or '3C286')
            band - receiver band used in observation scan for polAngleSource
                   ('L', 'S', 'C', 'X', 'Ku', 'K', 'Ka', 'Q')
            refFreq - reference frequency in band from frequency Stokes I array
            order - degree of fit (it is 4); 
                    this is for fitting the polynomial

    Outputs:
            coeffs - list of freq. dep. coefficients for linear pol. frac.
            p_ref - polarization fraction based on fit
            RM - rotation measure, already defined for each source
            X_0 - intrinsic polarization angle, already defined as well

    
    # known polarization percentages (given by 
    # Table 3. Polarization Properties of 3C48, 3C138, 3C147, and 3C286 
    # from 2013 Perley, Butler paper)
    p48 = np.array([0.3, 0.5, 0.7, 0.9, # L 
                    1.4, 2.0, 2.5, 3.2, # S
                    3.8, 4.2, 5.2, 5.2, # C
                    5.3, 5.4,           # X
                    6.0, 6.1, 6.4, 6.4, # Ku
                    6.9, 7.1, 7.7, 7.8, # K
                    7.4,                # Ka
                    7.5])               # V

    p138 = np.array([5.6,  7.5,  8.4, 9.0,
                     10.4, 10.7, 10.0, # null value here
                     10.0, 10.4, 9.8, 10.0,
                     10.4, 10.1,
                     8.4,  7.9,  7.7, 7.4,
                     6.7,  6.5,  6.7, 6.6,
                     6.6,
                     6.5])

    p147 = np.array([# first 2 rows (L and S) have values close to 0
                     0.1, 0.3, 0.3, 0.6, # C
                     0.7, 0.8,
                     2.2, 2.4, 2.7, 2.9,
                     3.4, 3.5, 3.8, 3.8,
                     4.4,
                     5.2])

    p286 = np.array([8.6,  9.5,  9.9,  10.1,
                     10.5, 10.8, 10.9, 11.1,
                     11.3, 11.4, 11.6, 11.7,
                     11.9, 11.9,
                     11.9, 11.9, 12.1, 12.2,
                     12.5, 12.5, 12.6, 12.6,
                     13.1,
                     13.2])

    # known frequencies for the known pol. percentages (given by Table 3)
    freqFitting = np.array([1.050, 1.450, 1.640, 1.950, \
                            2.450, 2.950, 3.250, 3.750, \
                            4.500, 5.000, 6.500, 7.250, \
                            8.100, 8.800, \
                            12.80, 13.70, 14.60, 15.50, \
                            18.10, 19.00, 22.40, 23.30, \
                            36.50, \
                            43.50]) #, \
                            # below is not originally from table,
                            # use if making other bands more robust
                            #45.0, 48.0, 51.0, 54.0, 57.0])

    # RM and X_0 values come from Table 4. RM Values for the Four Sources
    # (also from 2013 Perley, Butler paper)
    if (polAngleSource == '3C48'):
            pol = p48
            # wavelength range (cm): 1-18
            RM = -68 # rad/m^2
            X_0 = 122*pi/180 # in radians
            task_logprint("Polarization angle calibrator is 3C48\n")
    elif (polAngleSource == "3C138"):
            pol = p138
            # wavelength range (cm): 2-22
            RM = 0
            X_0 = -10*pi/180
            task_logprint("Polarization angle calibrator is 3C138\n")
            freqFitting = np.delete(freqFitting, 7, None)
            task_logprint("Not evaluating at frequency 3.75 GHz due to null value"
                  "for polarization fraction at that frequency.")
    elif (polAngleSource == "3C147"):
            if ((band == 'L') or (band == 'S')):
                    task_logprint("Unable to fit with L or S band for 3C147\n"
                          "Quitting script.\n")
                    # quit program, as unable to continue
                    exit()
            pol = p147
            # wavelength range (cm): 1-3
            RM = -1467
            X_0 = 88*pi/180
            task_logprint("Polarization angle calibrator is 3C147\n")
    elif (polAngleSource == "3C286"):
            pol = p286
            # wavelength range (cm): 1->30
            RM = 0
            X_0 = 33*pi/180
            task_logprint("Polarization angle calibrator is 3C286\n")
    else:
    # should never get here, as should have already checked that it was 1
            task_logprint("This source is not in this table.\n"
                  "Options are 3C48, 3C138, 3C147, 3C286")
            exit()

    # Fit by band
    if (band == 'L'):
            freqFitting = freqFitting[:8]
            pol = pol[:8]
    elif (band == 'S'):
            freqFitting = freqFitting[3:9]
            pol = pol[3:9]
    elif (band == 'C'):
            freqFitting = freqFitting[8:14]
            pol = pol[8:14]
    elif (band == 'X'):
            freqFitting = freqFitting[12:18]
            pol = pol[12:18]
    elif (band == 'Ku'):
            freqFitting = freqFitting[14:20]
            pol = pol[14:20]
    elif (band == 'K'):
            freqFitting = freqFitting[18:23]
            pol = pol[18:23]
    elif (band == 'Ka'): # TO DO: these ones need to be more robust
            freqFitting = freqFitting[22]
            pol = pol[22]
            #freqFitting = freqFitting[22:24]
    elif (band == 'Q'):
            freqFitting = freqFitting[23]
            pol = pol[23]
            #freqFitting = freqFitting[23:29]

    task_logprint("frequencies = " +str(freqFitting))
    task_logprint("reference frequency = "+str(refFreq))
    task_logprint("polarization percentages = "+ str(pol))

    x_data = (freqFitting - refFreq) / refFreq
    popt, pcov = sp.optimize.curve_fit(fitter4, x_data, pol/100.)	

    # refFreq - refFreq = 0
    p_ref = np.polyval(popt[::-1], 0.0)

    #print([popt, p_ref, RM, X_0])
    return popt, p_ref, RM, X_0
'''

def polyFit(polAngleSource, band, refFreq):
    '''
    polyFit fits a polynomial of order 4 (default) for the polarization index
    (polindex) input for CASA command setjy dependent on flux density calibrator
    and band.  The polarization index is a list of coefficients for frequency-dep.
    linear polarization fraction, as similarly stated in CASA setjy documentation.

    Inputs:
            polAngleSource - one of 4 flux density calibrator source 
                ('3C48', '3C138', '3C147', or '3C286')
            band - receiver band used in observation scan for polAngleSource
                   ('L', 'S', 'C', 'X', 'Ku', 'K', 'Ka', 'Q')
            refFreq - reference frequency in band from frequency Stokes I array
            order - degree of fit (it is 4); 
                    this is for fitting the polynomial

    Outputs:
            coeffs - list of freq. dep. coefficients for linear pol. frac.
            p_ref - polarization fraction based on fit
            RM - rotation measure, already defined for each source
            X_0 - intrinsic polarization angle, already defined as well

    '''
    # known polarization percentages (given by 
    # Table 3. Polarization Properties of 3C48, 3C138, 3C147, and 3C286 
    # from 2013 Perley, Butler paper)
    p48 = np.array([0.3, 0.5, 0.7, 0.9, # L 
                    1.4, 2.0, 2.5, 3.2, # S
                    3.8, 4.2, 5.2, 5.2, # C
                    5.3, 5.4,           # X
                    6.0, 6.1, 6.4, 6.4, # Ku
                    6.9, 7.1, 7.7, 7.8, # K
                    7.4,                # Ka
                    7.5])               # V

    p138 = np.array([5.6,  7.5,  8.4, 9.0,
                     10.4, 10.7, 10.0, # null value here
                     10.0, 10.4, 9.8, 10.0,
                     10.4, 10.1,
                     8.4,  7.9,  7.7, 7.4,
                     6.7,  6.5,  6.7, 6.6,
                     6.6,
                     6.5])

    p147 = np.array([# first 2 rows (L and S) have values close to 0
                     0.1, 0.3, 0.3, 0.6, # C
                     0.7, 0.8,
                     2.2, 2.4, 2.7, 2.9,
                     3.4, 3.5, 3.8, 3.8,
                     4.4,
                     5.2])

    p286 = np.array([8.6,  9.5,  9.9,  10.1,
                     10.5, 10.8, 10.9, 11.1,
                     11.3, 11.4, 11.6, 11.7,
                     11.9, 11.9,
                     11.9, 11.9, 12.1, 12.2,
                     12.5, 12.5, 12.6, 12.6,
                     13.1,
                     13.2])

    # known frequencies for the known pol. percentages (given by Table 3)
    freqFitting = np.array([1.050, 1.450, 1.640, 1.950, \
                            2.450, 2.950, 3.250, 3.750, \
                            4.500, 5.000, 6.500, 7.250, \
                            8.100, 8.800, \
                            12.80, 13.70, 14.60, 15.50, \
                            18.10, 19.00, 22.40, 23.30, \
                            36.50, \
                            43.50]) #, \
                            # below is not originally from table,
                            # use if making other bands more robust
                            #45.0, 48.0, 51.0, 54.0, 57.0])

    # RM and X_0 values come from Table 4. RM Values for the Four Sources
    # (also from 2013 Perley, Butler paper)
    cal_data2013 = np.genfromtxt('../../EVLA_Scripted_Pipeline/EVLA_SCRIPTED_PIPELINE/data/PolCals_2013_3C48.3C138.3C147.3C286.dat')

    freqFitting = cal_data2013[:,0]
    
    if (polAngleSource == '3C48'):
            pol_perc = cal_data2013[:,1]
            pol_angle = cal_data2013[:,2]
            #pol = p48
            # wavelength range (cm): 1-18
            #RM = -68 # rad/m^2
            #X_0 = 122*pi/180 # in radians
            task_logprint("Polarization angle calibrator is 3C48\n")
    elif (polAngleSource == "3C138"):
            pol_perc = cal_data2013[:,3]
            pol_angle = cal_data2013[:,4]
            #pol = p138
            # wavelength range (cm): 2-22
            #RM = 0
            #X_0 = -10*pi/180
            task_logprint("Polarization angle calibrator is 3C138\n")
            freqFitting = np.delete(freqFitting, 7, None)
            task_logprint("Not evaluating at frequency 3.75 GHz due to null value"
                  "for polarization fraction at that frequency.")
    elif (polAngleSource == "3C147"):
            if ((band == 'L') or (band == 'S')):
                    task_logprint("Unable to fit with L or S band for 3C147\n"
                          "Quitting script.\n")
                    # quit program, as unable to continue
                    exit()
            pol_perc = cal_data2013[:,5]
            pol_angle = cal_data2013[:,6]
            #pol = p147
            # wavelength range (cm): 1-3
            #RM = -1467
            #X_0 = 88*pi/180
            task_logprint("Polarization angle calibrator is 3C147\n")
    elif (polAngleSource == "3C286"):
            pol_perc = cal_data2013[:,7]
            pol_angle = cal_data2013[:,8]
            #pol = p286
            # wavelength range (cm): 1->30
            #RM = 0
            #X_0 = 33*pi/180
            task_logprint("Polarization angle calibrator is 3C286\n")
    else:
    # should never get here, as should have already checked that it was 1
            task_logprint("This source is not in this table.\n"
                  "Options are 3C48, 3C138, 3C147, 3C286")
            exit()

    # Fit by band
    if (band == 'L'):
            freqFitting = freqFitting[:4]
            pol = pol_perc[:4]
            ang = pol_angle[:4]
    elif (band == 'S'):
            freqFitting = freqFitting[4:8]
            pol = pol_perc[4:8]
            ang = pol_angle[4:8]
    elif (band == 'C'):
            freqFitting = freqFitting[8:12]
            pol = pol_perc[8:12]
            ang = pol_angle[8:12]
    elif (band == 'X'):
            freqFitting = freqFitting[12:14]
            pol = pol_perc[12:14]
            ang = pol_angle[12:14]
    elif (band == 'Ku'):
            freqFitting = freqFitting[14:18]
            pol = pol_perc[14:18]
            ang = pol_angle[14:18]
    elif (band == 'K'):
            freqFitting = freqFitting[18:22]
            pol = pol_perc[18:22]
            ang = pol_angle[18:22]
    elif (band == 'Ka'): # TO DO: these ones need to be more robust
            freqFitting = freqFitting[22]
            pol = pol_perc[22]
            ang = pol_angle[22]
            #freqFitting = freqFitting[22:24]
    elif (band == 'Q'):
            freqFitting = freqFitting[23]
            pol = pol_perc[23]
            ang = pol_angle[23]
            #freqFitting = freqFitting[23:29]

    task_logprint("frequencies = " +str(freqFitting))
    task_logprint("reference frequency = "+str(refFreq))
    task_logprint("polarization percentages = "+ str(pol))
    task_logprint("polarization angles = "+ str(ang))
    

    x_data = (freqFitting - refFreq) / refFreq
    popt_pf, pcov_pf = sp.optimize.curve_fit(fitter3, x_data, pol/100.)
    popt_pa, pcov_pa = sp.optimize.curve_fit(fitter3, x_data, ang*(np.pi/180))	

    # refFreq - refFreq = 0
    p_ref = np.polyval(popt_pf[::-1], 0.0)

    #print([popt, p_ref, RM, X_0])
    return popt_pf, popt_pa, p_ref




def determineSource(fields, isLeak):
    '''
    determineSource figures out which flux density calibrators exist
    in the measurement set

    Inputs:

            fields - the actual numbers of calibrator fields in .ms
            isLeak - boolean to know if the source is a pol. leakage
                     calibrator based on scan intent, so would need
                     to add it to list of calibrator sources

    Outputs:
            calSource - string containing field name of the calibrator source
            calField - string containing field number of the calibrator source
    '''
    tb.open(visPola+'FIELD')
    fieldNames = tb.getcol('NAME') # np array of all fields observed
    tb.close()

    calSource = []
    calField = []
    for i in np.unique(fields):
            if (('3C48' in fieldNames[i]) or
                ('3C 48' in fieldNames[i]) or
                ('3c48' in fieldNames[i]) or
                ('3c 48' in fieldNames[i])):
                    calSource.append('3C48')
                    calField.append(i)
                    task_logprint("3C48 is at index "+str(i))
            elif (('3C138' in fieldNames[i]) or
                  ('3C 138' in fieldNames[i]) or
                  ('3c138' in fieldNames[i]) or
                  ('3c 138' in fieldNames[i])):
                    calSource.append('3C138')
                    calField.append(i)
                    task_logprint("3C138 is at index "+str(i))
            elif (('3C147' in fieldNames[i]) or
                  ('3C 147' in fieldNames[i]) or
                  ('3c147' in fieldNames[i]) or
                  ('3c 147' in fieldNames[i])):
                    calSource.append('3C147')
                    calField.append(i)
                    task_logprint("3C147 is at index "+str(i))
            elif (('3C286' in fieldNames[i]) or
                  ('3C 286' in fieldNames[i]) or
                  ('3c286' in fieldNames[i]) or
                  ('3c 286' in fieldNames[i])):
                    calSource.append('3C286')
                    calField.append(i)
                    task_logprint("3C286 is at index "+str(i))
                    #elif (isLeak and (calField == [])):
            elif (isLeak): # think it's ok if calField contains one of the
                    # primary flux density calibrators
                    calField.append(i)
                    calSource.append(fieldNames[i])
                    task_logprint(str(fieldNames[i])+" is at index "+str(i))
            else:
                    task_logprint("This is not a primary calibrator.\n")

    # NOTE: This may be too presumptious, but it should work for all 3 data
    # sets for now. This assumes that regardless of length of array, 
    # calibrator should be the 1st one.
    calSource = np.unique(calSource)[0]
    calField = np.unique(calField[0])
    cfstr = str(calField)
    calField = cfstr[1:len(cfstr)-1]
    return (calSource, calField)



#################################################################################


task_logprint("Starting EVLA_pipe_calprep.py")
time_list = runtiming("calprep", "start")
QA2_calprep = "Pass"

# define name of polarization calibration measurement set
if (ms_active[-1] ==. '/'):
        visPola = ms_active[:-4]+"_pola_cal.ms/"
elif (ms_active[-1] == 's'):
        visPola = ms_active[:-3]+"_pola_cal.ms/"
else:
	visPola = 'pola_cal.ms/'
task_logprint("Polarization .ms is "+visPola+"\n")

# split out data column from .ms from user input
if not os.path.exists(visPola):
    split(vis=ms_active, outputvis=visPola, datacolumn='data')

#create listobs file for pol MS
visPola_listname = visPola.rstrip("ms/")+"listobs.txt"
os.system(f"rm -rf {visPola_listname}")
listobs(visPola, listfile=visPola_listname)



#retrieve number of fields in the MS
tb.open(visPola+'FIELD')
field_num = tb.nrows() # how many fields are there
tb.close()
task_logprint('There are '+str(field_num) +' fields in this MS')


# determine which intents are present (polarization leakage, 
# polarization angle, and flux) and match the indices in intents
# to the intent type
tb.open(visPola+'STATE')
intents = tb.getcol('OBS_MODE') # scan intents (i.e. CALIBRATE POL_ANGLE)
tb.close()
isFlux = False
isPolAngle = False
isPolLeak = False
flux_intents = []
pol_leak_intents = []
pol_angle_intents = []
task_logprint('Intents in this MS: '+str(intents))
for state_ID in range(len(intents)):
    state_intents = intents[state_ID].rsplit(",")
    task_logprint('For state ID : '+str(state_ID))
    for intent in range(len(state_intents)):
        scan_intent = state_intents[intent].rsplit("#")[0]
        task_logprint('The scan intent is: '+str(scan_intent))
        if (scan_intent == 'CALIBRATE_POL_LEAKAGE'):
            pol_leak_intents.append(state_ID)
            isPolLeak = True
        elif (scan_intent == 'CALIBRATE_POL_ANGLE'):
            pol_angle_intents.append(state_ID)
            isPolAngle = True
        elif (scan_intent == 'CALIBRATE_POLARIZATION'):
            pol_angle_intents.append(state_ID)
            isPolAngle = True
        elif (scan_intent == 'CALIBRATE_FLUX'):
            flux_intents.append(state_ID)
            isFlux = True

#task_logprint(pol_leak_intents, pol_angle_intents,  flux_intents)
        
# separate each field number into its own .ms to check its scan intent
tb.open(visPola)
for i in range(field_num):
    tb.query('FIELD_ID=='+str(i), name='field'+str(i)+'.ms')
tb.close()


# go into each field's scan intent and determine which one is a polarization
# leakage calibrator, which one is a calibrator with known polarization
# angle, and if there is a known flux density calibrator listed as well
flux_fields = []
pol_angle_fields = []
pol_leak_fields = []
task_logprint('number of fields ='+str(field_num))
for num in range(field_num): # for each field in the MS
    task_logprint('opening field '+str(num))
    tb.open('field'+str(num)+'.ms') #open its MS tables
    scan_nums = np.unique(tb.getcol('SCAN_NUMBER')) #get the scan numbers associated with that field
    task_logprint('scan numbers associated with this field = '+str(scan_nums))
    for scan in scan_nums: # connect scan number to scan intent per field, for each scan number associated with that field
        task_logprint('scan number = '+str(scan))
        temp = tb.query('SCAN_NUMBER == '+str(scan)) #extract MS rows with that scan number
        state_id = temp.getcol('STATE_ID') #and make note of the state_id for that scan number
        task_logprint('state_id = '+ str(state_id)+' ('+str(len(state_id))+')')
        if len(pol_angle_intents)!=0:
            task_logprint('length of pol_angle_intents = '+str(len(pol_angle_intents)))
        # if there is a calibrator with known polarization angle
            for pola in pol_angle_intents:
                if (pola in np.unique(state_id)):
                    pol_angle_fields.append(num)
                    task_logprint("Field "+str(num)+" is a calibrator with known polarization angle.\n")
                    task_logprint("This is Scan Number "+str(scan)+"\n ")
        if len(flux_intents)!=0:
        # if there is at least one flux density calibrator specified,
        # output the field numbers
            for f in flux_intents:
                if (f in np.unique(state_id)): 
                    flux_fields.append(num)
                    task_logprint("Field "+str(num)+" is a flux density calibrator.\n")
                    task_logprint("This is Scan Number "+str(scan)+"\n")
        if len(pol_leak_intents) != 0:
            for leak in pol_leak_intents:
                if (leak in np.unique(state_id)):
                    pol_leak_fields.append(num)
                    task_logprint("Field "+str(num)+" is a polarization leakage calibrator\n")
                    task_logprint("This is Scan Number "+str(scan)+"\n")
    tb.close()


# input name of field that is a polarization angle calibrator
# (2nd parameter in function is False, because not a pol. leakage calibrator)
#task_logprint('pol_angle_fields, flux_fields, pol_leak_fields = ' +pol_angle_fields, flux_fields, pol_leak_fields)
polAngleSource = determineSource(pol_angle_fields, False)[0]
polAngleField = determineSource(pol_angle_fields, False)[1]

fluxSource = determineSource(flux_fields, False)[0]
fluxField = determineSource(flux_fields, False)[1]

polLeakSource = determineSource(pol_leak_fields, True)[0]
polLeakField = determineSource(pol_leak_fields, True)[1]

# set the flux density model for the polarization angle calibrator by
# populating Stokes I
flux_dict = setjy(vis=visPola, field=polAngleField)

plotms(vis=visPola,field=polAngleField,correlation='RR',
       timerange='',antenna='',
       xaxis='frequency',yaxis='amp',ydatacolumn='model', plotfile=str(polAngleSource)+'_ampvsfreq_RR_model.png', overwrite=True)


#task_logprint("pol_leak_fields = ",pol_leak_fields, "\n")
task_logprint("polLeakSource = "+str(polLeakSource)+"\n")
task_logprint("polAngleSource = "+str(polAngleSource)+"\n")
task_logprint("fluxSource = "+str(fluxSource)+"\n")
#task_logprint("polLeakField = ", polLeakField, "\n")

print('flux_dict = ', flux_dict)
# in an array place each Stokes I flux density value per spw for all bands
fluxI = np.array([])
for i in range(len(flux_dict[polAngleField])-1):
    # polAngleField = field_num, str(i) = spw, fluxd = fluxd, 0 = I
    fluxI = np.append(fluxI, flux_dict[polAngleField][str(i)]['fluxd'][0])

task_logprint("fluxI from setjy is :"+str(fluxI)+"\n")

tb.open(visPola+'SPECTRAL_WINDOW')
freqI = tb.getcol('REF_FREQUENCY')
spwNum = freqI.shape[0]
task_logprint("spwNum currently using = "+str(spwNum)+"\n")

# this is the number of channels, so below is also some math to 
# determine which ones want to include for input
task_logprint("Please note that assuming this is a continuum scan, so assuming that "
      "all spectral windows have same number of channels\n")
chanNum = tb.getcol('CHAN_FREQ').shape[0]
val = 0.1*chanNum
upper = int(math.ceil(chanNum - val))
lower = int(val)
task_logprint("channels are "+str(chanNum))
task_logprint("upper = "+str(upper))
task_logprint("lower = "+str(lower))

spwL = 0
spwS = 0
spwC = 0
spwX = 0
spwKu = 0
spwK = 0
spwKa = 0
spwQ = 0
bandList = tb.getcol('NAME')
tb.close()
# first determine what frequency bands are in the .ms
bands = set()
for i in range(len(bandList)):
    if ('_L#' in bandList[i]):
        bands.add('L')
        spwL = i
    elif ('_S#' in bandList[i]):
        bands.add('S')
        spwS = i
    elif ('_C#' in bandList[i]):
        bands.add('C')
        spwC = i
    elif ('_X#' in bandList[i]):
        bands.add('X')
        spwX = i
    elif ('_KU#' in bandList[i]):
        bands.add('Ku')
        spwKu = i
    elif ('_K#' in bandList[i]):
        bands.add('K')
        spwK = i
    elif ('_KA#' in bandList[i]):
        bands.add('Ka')
        spwKa = i
    elif ('_V#' in bandList[i]):
        bands.add('Q')
        spwQ = i
    else:
        task_logprint("Unable to do calibration for this "+str(bandList[i])+"\n")
        quit()
        
task_logprint("frequency array is : "+str(freqI)+"\n")

task_logprint("bands are: "+str(bands)+"\n")

# to have bands be in the proper order
bandsList = []
if ('L' in bands):
    bandsList.append('L')
if ('S' in bands):
    bandsList.append('S')
if ('C' in bands):
    bandsList.append('C')
if ('X' in bands):
    bandsList.append('X')
if ('Ku' in bands):
    bandsList.append('Ku')
if ('K' in bands):
    bandsList.append('K')
if ('Ka' in bands):
    bandsList.append('Ka')
if ('Q' in bands):
    bandsList.append('Q')

task_logprint("bands are: "+str(bandsList)+"\n")


spw_start = 0
# example: bandsList = ['L', 'S', 'K']
for band in bandsList:
    if (band == 'L'):
        spw_end = spwL+1
    elif (band == 'S'):
        spw_end = spwS+1
    elif (band == 'C'):
        spw_end = spwC+1
    elif (band == 'X'):
        spw_end = spwX+1
    elif (band == 'Ku'):
        spw_end = spwKu+1
    elif (band == 'K'):
        spw_end = spwK+1
    elif (band == 'Ka'):
        spw_end = spwKa+1
    elif (band == 'Q'):
        spw_end = spwQ+1
    else: # not a band I know
        task_logprint(str(band)+" is not a recognized band for calibration.  Please"
              "note that this band will not be calibrated for, exiting script.\n")
        exit()

    task_logprint("Band that is being calibrated right now is: "+band+"\n")
    task_logprint('spw_start, spw_end = '+str(spw_start)+" - " +str(spw_end))
    freqI_band = freqI[spw_start:spw_end]
    fluxI_band = fluxI[spw_start:spw_end]

    task_logprint("freqI for band is "+str(freqI_band)+"\n")
    task_logprint("fluxI for band is "+str(fluxI_band)+"\n")
    task_logprint("len of freqI_band is "+str(len(freqI_band))+ "\ncompared to len of freqI, which is "+str(len(freqI))+"\n")

    refFreq = (min(freqI_band) + max(freqI_band)) / 2
    task_logprint("ref Freq would be :"+str(refFreq)+" Hz \n")
    diff = abs(refFreq - freqI_band[0])
    # begin process of finding which frequency in freqI_band is closest to
    # calculated reference frequency in the given frequencies (refFreq)

    for v in range(len(freqI_band)):
        # determine reference frequency from given frequencies
        if (diff >= abs(refFreq - freqI_band[v])):
            # found a freq. in freqI_band that is closer to calculated
            # reference frequency (refFreq)
            diff = abs(refFreq - freqI_band[v])
            refFreqI = freqI_band[v]
            # determine Stokes I value at the reference frequency
            i_ref = fluxI_band[v]

    task_logprint("refFreqI is :"+str(refFreqI)+" Hz \n")


    # determine polindex coefficients, polarization fraction, RM, and X_0
    # based on calibrator and band
    # NOTE: this assumes that refFreqI is given in terms of Hz,
    # so that is why dividing by 1e+09, to put in terms of GHz
    #polOut =
    coeffs_pf, coeffs_pa, p_ref = polyFit(polAngleSource, band, refFreqI/1e+09)
    task_logprint("polyFit output:")
    print(coeffs_pf, coeffs_pa, p_ref)

    #coeffs = polOut[0]
    task_logprint("polindex input will be: "+str(coeffs_pf))
    task_logprint("polangle input will be: "+str(coeffs_pa))

    #p_ref = polOut[1]
    task_logprint("p_ref is "+str(p_ref))

    #RM = polOut[2]
    #X_0 = polOut[3] # this is in terms of radians

    # calculate Stokes Q and U
    #q_ref = p_ref*i_ref*np.cos(2*X_0)
    #u_ref = p_ref*i_ref*np.sin(2*X_0)

    #task_logprint("Flux Dict passed to setjy is: "+str(i_ref)+" "+str(q_ref)+" "+str(u_ref))

    task_logprint("Determining setjy spix input\n")
    popt_I, pcov_I = sp.optimize.curve_fit(fitterI,freqI_band,fluxI_band)
    print('popt_I = ', popt_I)
    print(str(spw_start)+'~'+str(spw_end-1))

    setjy_full_dict = setjy(vis=visPola, standard='manual', field=polAngleField, 
                            spw=str(spw_start)+'~'+str(spw_end-1),
                            fluxdensity=[i_ref, 0, 0, 0],
                            spix = popt_I,
                            reffreq=str(refFreqI)+'Hz',
                            polindex = coeffs_pf,
                            polangle = coeffs_pa,
                            usescratch=True)





    
    plotms(vis=visPola,field=polAngleField,correlation='RL',
       timerange='',antenna='',
       xaxis='frequency',yaxis='amp',ydatacolumn='model', plotfile=str(polAngleSource)+'_ampvsfreq_RL_model.png', overwrite=True)

    plotms(vis=visPola,field=polAngleField,correlation='RL',
       timerange='',antenna='',
       xaxis='frequency',yaxis='phase',ydatacolumn='model', plotfile=str(polAngleSource)+'_phasevsfreq_RL_model.png', overwrite=True)  
'''

    setjy(vis=visPola, standard='manual', field=polAngleField, 
                            spw=str(spw_start)+'~'+str(spw_end-1),
                            fluxdensity=[i_ref,q_ref,u_ref,0],
                            spix = popt_I,
                            reffreq=str(refFreqI)+'Hz',
                            polindex = coeffs,
                            usescratch=True)
    # set the model
    setjy_full_dict = setjy(vis=visPola, standard='manual', field=polAngleField, 
                            spw=str(spw_start)+'~'+str(spw_end-1),
                            fluxdensity=[i_ref, q_ref, u_ref, 0],
                            spix = popt_I,
                            rotmeas = RM,
                            reffreq=str(refFreqI)+'Hz',
                            polindex = coeffs,
                            usescratch=True)

    print "setjy fluxdensity full = ", setjy_full_dict




task_logprint("Setting models for standard primary calibrators")

positions = field_positions.T.squeeze()
standard_source_names = ["3C48", "3C 48", "3c48", "3c 48", "3C138", "3C 138", "3c138", "3c 138", "3C147", "3C 147", "3c147", "3c 147", "3C286", "3C 286", "3c286", "3c 286"]
standard_source_fields = find_standards(positions)

standard_source_found = any(standard_source_fields)
if not standard_source_found:
    task_logprint(
        "ERROR: No standard flux density calibrator observed, flux density scale will be arbitrary."
    )
    QA2_calprep = "Fail"






for ii, fields in enumerate(standard_source_fields):
    for field in fields:
        spws = field_spws[field]
        for spw in spws:
            reference_frequency = center_frequencies[spw]
            EVLA_band = find_EVLA_band(reference_frequency)
            task_logprint(
                f"Center freq for spw {spw} = {reference_frequency}, observing band = {EVLA_band}"
            )
            model_image = f"{standard_source_names[ii]}_{EVLA_band}.im"
            task_logprint(
                f"Setting model for field {field} spw {spw} using {model_image}"
            )
            
            try:
                setjy(
                    vis=ms_active,
                    field=str(field),
                    spw=str(spw),
                    selectdata=False,
                    scalebychan=True,
                    standard="Perley-Butler 2017",
                    model=model_image,
                    listmodels=False,
                    usescratch=scratch,
                )
            except:
                task_logprint(f"no data found for field {field} spw {spw}")
            
task_logprint("Finished setting models for known calibrators")
'''
task_logprint("Finished EVLA_pipe_calprep.py")
task_logprint(f"QA2 score: {QA2_calprep}")
time_list = runtiming("calprep", "end")

pipeline_save()
