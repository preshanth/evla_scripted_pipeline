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

from casatasks import gaincal, applycal
from . import pipeline_save
from .utils import runtiming, logprint, find_standards, find_EVLA_band, RefAntHeuristics

pi = np.pi

def task_logprint(msg):
    logprint(msg, logfileout="logs/polcal.log")
    
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



    # RM and X_0 values come from Table 4. RM Values for the Four Sources
    # (also from 2013 Perley, Butler paper)
    cal_data2013 = np.genfromtxt('../../EVLA_Scripted_Pipeline/EVLA_SCRIPTED_PIPELINE/data/PolCals_2013_3C48.3C138.3C147.3C286.dat')

    freqFitting = cal_data2013[:,0]
    print('3C48' in polAngleSource)
    if ('3C48' in polAngleSource):
            pol_perc = cal_data2013[:,1]
            pol_angle = cal_data2013[:,2]
            #pol = p48
            # wavelength range (cm): 1-18
            #RM = -68 # rad/m^2
            #X_0 = 122*pi/180 # in radians
            task_logprint("Polarization angle calibrator is 3C48\n")
    elif ("3C138" in polAngleSource):
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
    elif ("3C147" in polAngleSource):
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
    elif ("3C286" in polAngleSource):
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

if do_pol == True:
    task_logprint("*** Starting EVLA_pipe_polcal_testing_v2.py ***")
    time_list = runtiming("calprep", "start")
    QA2_calprep = "Pass"

    # define name of polarization calibration measurement set
    if (ms_active[-1] == '/'):
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


    task_logprint("Finding a reference antenna")

    refantfield = polarization_angle_field_select_string
    findrefant = RefAntHeuristics(
        vis=ms_active,
        field=refantfield,
        geometry=True,
        flagging=True,
    )
    RefAntOutput = findrefant.calculate()
    refAnt = str(RefAntOutput[0])

    task_logprint(f"The pipeline will use antenna {refAnt} as the reference")



    # set the stokes I model for the polarization angle calibrator and plot results
    flux_dict = setjy(vis=visPola, field=polarization_angle_field_select_string)

    plotms(vis=visPola,field=polAngleField,correlation='RR',
           timerange='',antenna='',
           xaxis='frequency',yaxis='amp',ydatacolumn='model', plotfile=str(polAngleField)+'_ampvsfreq_RR_model.png', overwrite=True)
    

    task_logprint("polLeakSource = "+str(polLeakField)+"\n")
    task_logprint("polAngleSource = "+str(polAngleField)+"\n")
    task_logprint("fluxSource = "+str(fluxField)+"\n")



    # in an array place each Stokes I flux density value per spw for all bands
    fluxI = np.array([])
    for i in range(len(flux_dict[polarization_angle_field_select_string])-1):
        # polAngleField = field_num, str(i) = spw, fluxd = fluxd, 0 = I
        fluxI = np.append(fluxI, flux_dict[polarization_angle_field_select_string][str(i)]['fluxd'][0])

    task_logprint("fluxI from setjy is :"+str(fluxI)+"\n")


    task_logprint("reference_frequencies = %s" % reference_frequencies)

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
    
    bandsList = unique_bands_string
    print("bands are: ", bandsList, "\n")

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
        print(bandList[i])
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
            print(str(band)+" is not a recognized band for calibration.  Please"
                  "note that this band will not be calibrated for, exiting script.\n")
            exit()

        print("Band that is being calibrated right now is: "+band+"\n")

        freqI_band = freqI[spw_start:spw_end]
        fluxI_band = fluxI[spw_start:spw_end]

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
        coeffs_pf, coeffs_pa, p_ref = polyFit(polAngleField, band, refFreqI/1e+09)
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
               xaxis='frequency',yaxis='amp',ydatacolumn='model', plotfile=str(polAngleField)+'_ampvsfreq_RL_model.png', overwrite=True)

        plotms(vis=visPola,field=polAngleField,correlation='RL',
               timerange='',antenna='',
               xaxis='frequency',yaxis='phase',ydatacolumn='model', plotfile=str(polAngleField)+'_phasevsfreq_RL_model.png', overwrite=True)

        # Solving for the Cross Hand Delays
        kcross_sbd = polAngleField+'_'+band+'_band_data.Kcross'
        gaincal(vis=visPola, caltable=kcross_sbd, field=polAngleField,
                spw=str(spw_start)+'~'+str(spw_end-1)+':'+str(lower)+'~'+str(upper),
                gaintype='KCROSS',
                solint='inf',
                combine='scan', 
                refant=refAnt,
                gaintable=[''],
                gainfield=[''],
                parang=True)

        plotms(vis=kcross_sbd, xaxis='frequency', yaxis='delay', antenna = refAnt, coloraxis='corr', plotfile=str(polAngleField)+'_delayvsfreq_kcross_sbd_sol.png', overwrite=True)
