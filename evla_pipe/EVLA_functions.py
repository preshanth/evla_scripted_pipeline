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
import math
import urllib
import datetime

import numpy as np

from casatools import (table, measures, quanta)
tb = table()
me = measures()
qa = quanta()

# FIXME Requires:
# - getCalFlaggedSoln


def uniq(inlist):
    return np.unique(inlist).tolist()


def find_EVLA_band(frequency):
    # FIXME This isn't necessarily right around X/U since they overlap.
    # Band name and band edge frequencies in GHz
    band_freqs = {
            "4": ( 0.00,  0.15),
            "P": ( 0.15,  0.70),
            "L": ( 0.70,  2.00),
            "S": ( 2.00,  4.00),
            "C": ( 4.00,  8.00),
            "X": ( 8.00, 12.00),
            "U": (12.00, 18.00),
            "K": (18.00, 26.50),
            "A": (26.50, 40.00),
            "Q": (40.00, 56.00),
    }
    freq_ghz = frequency / 1e9  # Hz to GHz
    for name, (f_lo, f_hi) in band_freqs.items():
        if f_lo < freq_ghz <= f_hi:
            return name
    else:
        raise ValueError("Invalid EVLA frequency: {0}".format(frequency))


def find_standards(positions):
    # Set the max separation as ~1'
    MAX_SEPARATION = 60*2.0e-5
    position_3C48 = me.direction('j2000', '1h37m41.299', '33d9m35.133')
    fields_3C48 = []
    position_3C138 = me.direction('j2000', '5h21m9.886', '16d38m22.051')
    fields_3C138 = []
    position_3C147 = me.direction('j2000', '5h42m36.138', '49d51m7.234')
    fields_3C147 = []
    position_3C286 = me.direction('j2000', '13h31m8.288', '30d30m32.959')
    fields_3C286 = []
    for ii in range(0,len(positions)):
        position = me.direction('j2000', str(positions[ii][0])+'rad', str(positions[ii][1])+'rad')
        separation = me.separation(position,position_3C48)['value'] * pi/180.0
        if (separation < MAX_SEPARATION):
            fields_3C48.append(ii)
        else:
            separation = me.separation(position,position_3C138)['value'] * pi/180.0
            if (separation < MAX_SEPARATION):
                fields_3C138.append(ii)
            else:
                separation = me.separation(position,position_3C147)['value'] * pi/180.0
                if (separation < MAX_SEPARATION):
                    fields_3C147.append(ii)
                else:
                    separation = me.separation(position,position_3C286)['value'] * pi/180.0
                    if (separation < MAX_SEPARATION):
                        fields_3C286.append(ii)
    fields = [fields_3C48, fields_3C138, fields_3C147, fields_3C286]
    return fields


def correct_ant_posns(vis_name, print_offsets=False):
    """
    Given an input visibility MS name (vis_name), find the antenna
    position offsets that should be applied.  This application should
    be via the gencal task, using caltype='antpos'.

    If the print_offsets parameter is True, will print out each of
    the found offsets (or indicate that none were found), otherwise
    runs silently.

    A list is returned where the first element is the returned error
    code, the second element is a string of the antennas, and the
    third element is a list of antenna Bx,By,Bz offsets.  An example
    return list might look like:
    [ 0, 'ea01,ea19', [0.0184, -0.0065, 0.005, 0.0365, -0.0435, 0.0543] ]

    Usage examples:

       CASA <1>: antenna_offsets = correct_ant_posns('test.ms')
       CASA <2>: if (antenna_offsets[0] == 0):
       CASA <3>:     gencal(vis='test.ms', caltable='cal.G', \
                     caltype='antpos', antenna=antenna_offsets[1], \
                     parameter=antenna_offsets[2])

    This function does NOT work for VLA datasets, only EVLA.  If an
    attempt is made to use the function for VLA data (prior to 2010),
    an error code of 1 is returned.

    The offsets are retrieved over the internet.  A description and the
    ability to manually examine and retrieve offsets is at:
    http://www.vla.nrao.edu/astro/archive/baselines/
    If the attempt to establish the internet connection fails, an error
    code of 2 is returned.

    Uses the same algorithm that the AIPS task VLANT does.
    """
    # FIXME haven't checked dictionary iterator stuff yet
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
              'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    URL_BASE = 'http://www.vla.nrao.edu/cgi-bin/evlais_blines.cgi?Year='
    # Get start date+time of observation
    try:
        observation = tb.open(vis_name+'/OBSERVATION')
        time_range = tb.getcol('TIME_RANGE')
    finally:
        tb.close()
    MJD_start_time = time_range[0][0] / 86400
    q1 = qa.quantity(time_range[0][0],'s')
    date_time = qa.time(q1,form='ymd')
    # FIXME this should probably use the Python datetime module
    # date_time format: '2011/08/10/06:56:49'
    obs_year, obs_month, obs_day, obs_time_string = date_time[0].split('/')
    if int(obs_year) < 2010:
        if print_offsets:
            print('Does not work for VLA observations')
        return [1, '', []]
    obs_hour, obs_minute,obs_second = obs_time_string.split(':')
    obs_time = 10000*int(obs_year) + 100*int(obs_month) + int(obs_day) + \
               int(obs_hour)/24.0 + int(obs_minute)/1440.0 + \
               int(obs_second)/86400.0
    # Get antenna to station mappings
    try:
        observation = tb.open(vis_name+'/ANTENNA')
        ant_names = tb.getcol('NAME')
        ant_stations = tb.getcol('STATION')
    finally:
        tb.close()
    ant_num_stas = []
    for ii in range(len(ant_names)):
        ant_num_stas.append([int(ant_names[ii][2:]), ant_names[ii], \
                            ant_stations[ii], 0.0, 0.0, 0.0, False])
    correction_lines = []
    current_year = datetime.datetime.now().year
    # First, see if the internet connection is possible
    try:
        response = urllib.request.urlopen(URL_BASE + '2010')
    except URLError as err:
        if print_offsets:
            print('No internet connection to antenna position correction URL ', err.reason)
        return [2, '', []]
    finally:
        response.close()
    for year in range(2010, current_year+1):
        try:
            response = urllib.request.urlopen(URL_BASE + str(year))
            html = response.read()
        finally:
            response.close()
        html_lines = html.split('\n')
        for correction_line in html_lines:
            if len(correction_line) and correction_line[0] != '<' and correction_line[0] != ';':
                for month in MONTHS:
                    if month in correction_line:
                        correction_lines.append(str(year)+' '+correction_line)
                        break
    corrections_list = []
    for correction_line in correction_lines:
        correction_line_fields = correction_line.split()
        if (len(correction_line_fields) > 9):
            c_year, moved_date, obs_date, put_date, put_time_str, ant, pad, Bx, By, Bz = correction_line_fields
            s_moved = moved_date[:3]
            i_month = 1
            for month in MONTHS:
                if (moved_date.find(month) >= 0):
                    break
                i_month = i_month + 1
            moved_time = 10000 * int(c_year) + 100 * i_month + \
                         int(moved_date[3:])
        else:
            c_year, obs_date, put_date, put_time_str, ant, pad, Bx, By, Bz = correction_line_fields
            moved_date = '     '
            moved_time = 0
        s_obs = obs_date[:3]
        i_month = 1
        for month in MONTHS:
            if s_obs.find(month) >= 0:
                break
            i_month = i_month + 1
        obs_time_2 = 10000 * int(c_year) + 100 * i_month + int(obs_date[3:])
        s_put = put_date[:3]
        i_month = 1
        for month in MONTHS:
            if s_put.find(month) >= 0:
                break
            i_month += 1
        put_time = 10000 * int(c_year) + 100 * i_month + int(put_date[3:])
        put_hr, put_min = put_time_str.split(':')
        put_time += (int(put_hr)/24.0 + int(put_min)/1440.0)
        corrections_list.append([c_year, moved_date, moved_time, obs_date, obs_time_2, put_date, put_time, int(ant), pad, float(Bx), float(By), float(Bz)])
    for correction_list in corrections_list:
        c_year, moved_date, moved_time, obs_date, obs_time_2, put_date, put_time, ant, pad, Bx, By, Bz = correction_list
        ant_ind = -1
        for ii in range(len(ant_num_stas)):
            ant_num_sta = ant_num_stas[ii]
            if (ant == ant_num_sta[0]):
                ant_ind = ii
                break
        if (ant_ind == -1) or (ant_num_sta[6]):
            # FIXME this should probably be a `continue` not `pass`
            # The antenna in this correction isn't in the observation, or is
            # done, so skip it
            pass
        ant_num_sta = ant_num_stas[ant_ind]
        if moved_time:
            # the antenna moved
            if (moved_time > obs_time):
                # we are done considering this antenna
                ant_num_sta[6] = True
            else:
                # otherwise, it moved, so the offsets should be reset
                ant_num_sta[3] = 0.0
                ant_num_sta[4] = 0.0
                ant_num_sta[5] = 0.0
        if ((put_time > obs_time) and (not ant_num_sta[6]) and
            (pad == ant_num_sta[2])):
            # it's the right antenna/pad; add the offsets to those already accumulated
            ant_num_sta[3] += Bx
            ant_num_sta[4] += By
            ant_num_sta[5] += Bz
    ants = []
    parms = []
    for ii in range(len(ant_num_stas)):
        ant_num_sta = ant_num_stas[ii]
        if ((ant_num_sta[3] != 0.0) or (ant_num_sta[4] != 0.0) or \
            (ant_num_sta[3] != 0.0)):
            if (print_offsets):
                print("offsets for antenna %4s : %8.5f  %8.5f  %8.5f" % \
                      (ant_num_sta[1], ant_num_sta[3], ant_num_sta[4], ant_num_sta[5]))
            ants.append(ant_num_sta[1])
            parms.append(ant_num_sta[3])
            parms.append(ant_num_sta[4])
            parms.append(ant_num_sta[5])
    if len(parms) == 0 and print_offsets:
        print("No offsets found for this MS")
    ant_string = ','.join(["%s" % ii for ii in ants])
    return [0, ant_string, parms]


def spwsforfield(vis,field):
    # FIXME Isn't this a function in `msmd`?
    # Get observed DDIDs for specified field from MAIN
    try:
        tb.open(vis)
        st = tb.query('FIELD_ID==' + str(field))
        ddids = np.unique(st.getcol('DATA_DESC_ID'))
        st.close()
    finally:
        tb.close()
    # Get SPW_IDs corresponding to those DDIDs
    try:
        tb.open(vis+'/DATA_DESCRIPTION')
        spws = tb.getcol('SPECTRAL_WINDOW_ID')[ddids]
    finally:
        tb.close()
    return list(spws)


# Classes
# -------
# RefAntHeuristics - Chooses the reference antenna heuristics.
# RefAntGeometry   - Contains the geometry heuristics for the reference antenna.
# RefAntFlagging   - Contains the flagging heuristics for the reference antenna.

class RefAntHeuristics:
    """
    Calculate reference antenna heuristics.

    Attributes
    ----------
    vis      - This python string contains the MS name.

    field    - This python string or list of strings contains the field numbers
               or IDs.  Presently it is used only for the flagging heuristic.
    spw      - This python string or list of strings contains the spectral
               window numbers of IDs.  Presently it is used only for the
               flagging heuristic.
    intent   - This python string or list of strings contains the intent(s).
               Presently it is used only for the flagging heuristic.

    geometry - This python boolean determines whether the geometry heuristic will
               be used.
    flagging - This python boolean determines whether the flagging heuristic will
               be used.

    Methods
    -------
    __init__   - This public member function constructs an instance of the
                 RefAntHeuristics() class.
    calculate  - This public member function forms the reference antenna list
                 calculated from the selected heuristics.
    _get_names - This private member function gets the antenna names from the MS.
    """

    def __init__(self,
            vis,
            field='',
            spw='',
            intent='',
            geometry=False,
            flagging=False,
        ):
        """
        Note: If all of the defaults are chosen, no reference antenna list is returned.

        Parameters
        ----------
        vis        - This python string contains the MS name.
        field      - This python string or list of strings contains the field numbers
                     or IDs.  Presently it is used only for the flagging heuristic.
                     The default is ''.
        spw        - This python string or list of strings contains the spectral
                     window numbers of IDs.  Presently it is used only for the
                     flagging heuristic.  The default is ''.
        intent     - This python string or list of strings contains the intent(s).
                     Presently it is used only for the flagging heuristic.  The
                     default is ''.
        geometry   - This python boolean determines whether the geometry heuristic
                     will be used in automatic mode.  The default is False.
        flagging   - This python boolean determines whether the flagging heuristic
                     will be used in automatic mode.  The default is False.
        """
        self.vis = vis
        self.field = field
        self.spw = spw
        self.intent = intent
        self.geometry = geometry
        self.flagging = flagging

    def calculate(self):
        """
        Calculate reference antenna list from the selected heuristics.

        Note: A total score is calculated from all heuristics.  The best
        antennas have the highest scores, so a reverse sort is performed to
        obtain the final list.

        Returns
        -------
        Numpy array of strings containing the ranked reference antenna list.
        """
        # If no heuristics are specified, return no reference antennas
        if not (self.geometry or self.flagging):
            return []
        # Get the antenna names and initialize the score dictionary
        names = self._get_names()
        score = dict()
        for n in names:
            score[n] = 0.0
        # For each selected heuristic, add the score for each antenna
        self.geoScore = 0.0
        self.flagScore = 0.0
        if self.geometry:
            geoClass = RefAntGeometry( self.vis )
            self.geoScore = geoClass.calc_score()
            for n in names: score[n] += self.geoScore[n]
        if self.flagging:
            flagClass = RefAntFlagging(self.vis, self.field, self.spw, self.intent)
            self.flagScore = flagClass.calc_score()
            for n in names:
                try:
                    score[n] += self.flagScore[n]
                except KeyError as e:
                    logprint("WARNING: antenna "+str(e)+", is completely flagged and missing from calibrators.ms", logfileout='logs/refantwarnings.log')
        # Calculate the final score and return the list of ranked
        # reference antennas.  NB: The best antennas have the highest
        # score, so a reverse sort is required.
        keys = np.array(score.keys())
        values = np.array(score.values())
        argSort = np.argsort(values)[::-1]
        refAntUpper = keys[argSort]
        refAnt = list()
        for r in refAntUpper:
            refAnt.append(r.lower())
        # Return the list of ranked reference antennas
        return refAnt

    def _get_names(self):
        tbLoc = casac.table()
        try:
            tbLoc.open( self.vis+'/ANTENNA' )
            # Get the antenna names and capitalize them (unfortunately,
            # some CASA tools capitalize them and others don't)
            names = tbLoc.getcol( 'NAME' ).tolist()
            rNames = range( len(names) )
            for n in rNames:
                names[n] = names[n]
        finally:
            tbLoc.close()
        return names

class RefAntGeometry:
    """
    This class contains the geometry heuristics for the reference antenna.

    Algorithm
    ---------
    * Calculate the antenna distances from the array center.
    * Normalize the distances by the maximum distance.
    * Calculate the score for each antenna, which is one minus the normalized
      distance.  The best antennas have the highest score.
    * Sort according to score.

    Attributes
    ----------
    vis - MS name.

    Methods
    -------
    __init__        - This public member function constructs an instance of the
                      RefAntGeometry() class.
    calc_score      - This public member function calculates the geometry score for
                      each antenna.
    _get_info       - This private member function gets the information from the
                      antenna table of the MS.
    _get_measures   - This private member function gets the measures from the
                      antenna table of the MS.
    _get_latlongrad - This private member function gets the latitude, longitude
                      and radius (from the center of the earth) for each antenna.
    _calc_distance  - This private member function calculates the antenna
                      distances from the array reference from the radii,
                      longitudes, and latitudes.
    _calc_score     - This private member function calculates the geometry score
                      for each antenna.
    """

    def __init__(self, vis):
        """
        Parameters
        ----------
        vis - MS name.
        """
        self.vis = vis

    def calc_score(self):
        """
        Calculates the geometry-score for each antenna.

        Returns
        -------
        Dictionary containing the score for each antenna.
        """
        # Get the antenna information, measures, and locations
        info = self._get_info()
        measures = self._get_measures( info )
        radii, longs, lats = self._get_latlongrad( info, measures )
        # Calculate the antenna distances and scores
        distance = self._calc_distance( radii, longs, lats )
        score = self._calc_score( distance )
        return score

    def _get_info(self):
        """
        Get the information from the antenna table of the MS.

        Returns
        -------
        Dictionary containing the antenna information, with format:

            'position'          - Array of antenna positions.
            'flag_row'          - Array of flag row booleans.
                                  NB: This element is of limited use now and
                                      may be eliminated.
            'name'              - Array antenna name strings.
            'position_keywords' - Antenna information dictionary.
        """
        # Create the local instance of the table tool and open it with
        # the antenna subtable of the MS
        tbLoc = casac.table()
        try:
            tbLoc.open( self.vis+'/ANTENNA' )
            # Get the antenna information from the antenna table
            info = dict()
            info['position'] = tbLoc.getcol( 'POSITION' )
            info['flag_row'] = tbLoc.getcol( 'FLAG_ROW' )
            info['name'] = tbLoc.getcol( 'NAME' )
            info['position_keywords'] = tbLoc.getcolkeywords( 'POSITION' )
        finally:
            tbLoc.close()
        # The flag tool appears to return antenna names as upper case,
        # which seems to be different from the antenna names stored in
        # MSes.  Therefore, these names will be capitalized here.
        rRow = range( len( info['name'] ) )
        # Return the antenna information
        return info

    def _get_measures(self, info):
        """
        Get the measures from the antenna table of the MS.

        Parameters
        ----------
        info - Dictionary of the antenna information from private
               member function `_get_info()`.

        Returns
        -------
        Dictionary containing the antenna measures with format:
        '<antenna name>' - antenna measures
        """
        # Create the local instances of the measures and quanta tools
        meLoc = casac.measures()
        qaLoc = casac.quanta()
        # Initialize the measures dictionary and the position and
        # position_keywords variables
        measures = dict()
        position = info['position']
        position_keywords = info['position_keywords']
        rf = position_keywords['MEASINFO']['Ref']
        for row,ant in enumerate( info['name'] ):
            if not info['flag_row'][row]:
                p = position[0,row]
                pk = position_keywords['QuantumUnits'][0]
                v0 = qaLoc.quantity( p, pk )
                #
                p = position[1,row]
                pk = position_keywords['QuantumUnits'][1]
                v1 = qaLoc.quantity( p, pk )
                #
                p = position[2,row]
                pk = position_keywords['QuantumUnits'][2]
                v2 = qaLoc.quantity( p, pk )
                measures[ant] = meLoc.position( rf=rf, v0=v0,
                    v1=v1, v2=v2 )
        return measures

    def _get_latlongrad( self, info, measures ):
        """
        Get the latitude, longitude and radius (from the center of the earth)
        for each antenna.

        Parameters
        ----------
        info     - This python dictionary contains the antenna information from
                   private member function _get_info().
        measures - This python dictionary contains the antenna measures from private
                   member function _get_measures().

        Returns
        -------
        Tuple containing containing radius, longitude, and latitude python
        dictionaries.
        """
        qaLoc = casac.quanta()
        # Get the radii, longitudes, and latitudes
        radii = dict()
        longs = dict()
        lats = dict()
        for ant in info['name']:
            value = measures[ant]['m2']['value']
            unit = measures[ant]['m2']['unit']
            quantity = qaLoc.quantity( value, unit )
            convert = qaLoc.convert( quantity, 'm' )
            radii[ant] = qaLoc.getvalue( convert )
            #
            value = measures[ant]['m0']['value']
            unit = measures[ant]['m0']['unit']
            quantity = qaLoc.quantity( value, unit )
            convert = qaLoc.convert( quantity, 'rad' )
            longs[ant] = qaLoc.getvalue( convert )
            #
            value = measures[ant]['m1']['value']
            unit = measures[ant]['m1']['unit']
            quantity = qaLoc.quantity( value, unit )
            convert = qaLoc.convert( quantity, 'rad' )
            lats[ant] = qaLoc.getvalue( convert )
        return radii, longs, lats

    def _calc_distance(self, radii, longs, lats):
        """
        Calculate the antenna distances from the array reference from the
        radii, longitudes, and latitudes.

        NB: The array reference is the median location.

        Parameters
        ----------
        radii - This python dictionary contains the radius (from the center of the
                earth) for each antenna.
        longs - This python dictionary contains the longitude for each antenna.
        lats  - This python dictionary contains the latitude for each antenna.

        Results
        -------
        Dictionary containing the antenna distances from the array reference.
        """
        # Convert the dictionaries to numpy float arrays.  The median
        # longitude is subtracted.
        radiusValues = np.array( radii.values() )
        longValues = np.array( longs.values() )
        longValues -= np.median( longValues )
        latValues = np.array( lats.values() )
        # Calculate the x and y antenna locations.  The medians are
        # subtracted.
        x = longValues * np.cos(latValues) * radiusValues
        x -= np.median( x )
        y = latValues * radiusValues
        y -= np.median( y )
        # Calculate the antenna distances from the array reference and
        # return them
        distance = dict()
        names = radii.keys()
        for i,ant in enumerate(names):
            distance[ant] = np.sqrt(pow(x[i],2) + pow(y[i],2))
        return distance

    def _calc_score(self, distance):
        """
        Calculate the geometry score for each antenna.

        Algorithm
        ---------
        * Calculate the antenna distances from the array center.
        * Normalize the distances by the maximum distance.
        * Calculate the score for each antenna, which is one minus the normalized
          distance.  The best antennas have the highest score.
        * Sort according to score.

        Parameters
        ----------
        distance - Dictionary of the antenna distances from the array
                   reference.  They are calculated in private member
                   function `_calc_distance()`.

        Results
        -------
        Dictionary containing the score for each antenna.
        """
        # Get the number of good data, calculate the fraction of good
        # data, and calculate the good and bad weights
        far = np.array( distance.values(), np.float )
        fFar = far / float( np.max(far) )
        wFar = fFar * len(far)
        wClose = ( 1.0 - fFar ) * len(far)
        # Calculate the score for each antenna and return them
        score = dict()
        names = distance.keys()
        rName = range( len(wClose) )
        for n in rName:
            score[names[n]] = wClose[n]
        return score

class RefAntFlagging:
    """
    This class contains the flagging heuristics for the reference antenna.

    Algorithm
    ---------
    * Get the number of unflagged (good) data for each antenna.
    * Normalize the good data by the maximum good data.
    * Calculate the score for each antenna, which is one minus the normalized
      number of good data.  The best antennas have the highest score.
    * Sort according to score.

    Attributes
    ----------
    vis    - This python string contains the MS name.

    field  - This python string or list of strings contains the field numbers or
             or IDs.
    spw    - This python string or list of strings contains the spectral window
             numbers of IDs.
    intent - This python string or list of strings contains the intent(s).

    Methods
    -------
    __init__    - Initialize an instance of the class.
    calc_score  - Calculate the flagging score for each antenna.
    _get_good   - Get the number of unflagged (good) data from the MS.
    _calc_score - Calculates the flagging score for each antenna.
    """

    def __init__(self, vis, field, spw, intent):
        """
        Parameters
        ----------
        vis: str
            MS name.
        field: str or list-like
            Field ID or list of field IDs.
        spw: str or list-like
            Spectral window ID or list of spectral window IDs.
        intent: str or list-like
            Intent or list of intents.

        """
        self.vis = vis
        self.field = field
        self.spw = spw
        self.intent = intent

    def calc_score(self):
        """
        Calculate the number of unflagged (good) measurements for each
        antenna and determine the scores.

        Returns
        -------
        Dictionary containing the score for each antenna.
        """
        good = self._get_good()
        return self._calc_score(good)

    def _get_good(self):
        """
        Gets the number of unflagged (good) data from the MS.

        Returns
        -------
        Dictionary containing the number of unflagged (good) data from the MS.
        """
        # FIXME will need to import flagdata from casatasks
        results = flagdata(
                vis=self.vis,
                mode="summary",
                field=self.field,
                spw=self.spw,
                intent=self.intent,
                display="",
                flagbackup=False,
                savepars=False,
        )
        # Calculate the number of good data for each antenna and return
        # them
        antenna = results['antenna']
        good = dict()
        for a in antenna.keys():
            good[a] = antenna[a]['total'] - antenna[a]['flagged']
        return good

    def _calc_score(self, good):
        """
        Calculate the flagging score for each antenna.

        Algorithm
        ---------
        * Get the number of unflagged (good) data for each antenna.
        * Normalize the good data by the maximum good data.
        * Calculate the score for each antenna, which is one minus the normalized
          number of good data.  The best antennas have the highest score.
        * Sort according to score.

        Parameters
        ----------
        good - This python dictionary contains the number of unflagged (good) data
               from the MS.  They are obtained in private member function _get_good().

        Returns
        -------
        Dictionary containing the score for each antenna.
        """
        # Get the number of good data, calculate the fraction of good
        # data, and calculate the good and bad weights
        nGood = np.array(good.values(), np.float)
        fGood = nGood / float(np.max(nGood))
        wGood = fGood * len(nGood)
        wBad = (1.0 - fGood) * len(nGood)
        # Calculate the score for each antenna and return them
        score = dict()
        names = good.keys()
        rName = range(len(wGood))
        for n in rName:
            score[names[n]] = wGood[n]
        return score


def testBPdgains(
        calMs,
        calTable,
        calSpw,
        calScans,
        calSolint,
        refAnt,
        minBL_for_cal,
        priorcals,
        do3C84,
        UVrange3C84,
    ):
    # FIXME regularize names
    GainTables = copy.copy(priorcals)
    GainTables.append('testdelay.k')
    uvrange = UVrange3C84 if do3C84 else ""
    gaincal(
            vis=calMs,
            caltable=calTable,
            field='',
            spw=calSpw,
            intent='',
            selectdata=True,
            uvrange=uvrange,
            scan=calScans,
            solint=calSolint,
            combine='scan',
            preavg=-1.0,
            refant=refAnt,
            minblperant=minBL_for_cal,
            minsnr=5.0,
            solnorm=False,
            gaintype='G',
            smodel=[],
            calmode='ap',
            append=False,
            docallib=False,
            gaintable=GainTables,
            gainfield=[''],
            interp=[''],
            spwmap=[],
            parang=False,
    )
    return getCalFlaggedSoln(calTable)


def testdelays(
        calMs,
        calTable,
        calField,
        calScans,
        refAnt,
        minBL_for_cal,
        priorcals,
        do3C84,
        UVrange3C84,
    ):
    """
    Note: can't use uvrange for delay cals because it flags all antennas beyond
    uvrange from the refant; so leave as all in delay cal and have any residual
    structure taken out by bandpass and gaincal until this is fixed.
    """
    # FIXME regularize names
    GainTables = copy.copy(priorcals)
    GainTables.append('testdelayinitialgain.g')
    # FIXME see above note in docstring
    #uvrange = UVrange3C84 if do3C84 else ""
    uvrange = ""
    gaincal(
            vis=calMs,
            caltable=calTable,
            field=calField,
            spw='',
            intent='',
            selectdata=True,
            uvrange=uvrange,
            scan=calScans,
            solint='inf',
            combine='scan',
            preavg=-1.0,
            refant=refAnt,
            minblperant=minBL_for_cal,
            minsnr=3.0,
            solnorm=False,
            gaintype='K',
            smodel=[],
            calmode='p',
            append=False,
            docallib=False,
            gaintable=GainTables,
            gainfield=[''],
            interp=[''],
            spwmap=[],
            parang=False,
    )
    # FIXME should perform a check that the caltable was successfully written.
    return getCalFlaggedSoln(calTable)


def testgains(
        calMs,
        calTable,
        calSpw,
        calScans,
        calSolint,
        refAnt,
        minBL_for_cal,
        combtime,
    ):
    """
    Note: when the pipeline can use the full MS instead of calibrators.ms,
    gaintable will have to include all priorcals plus delay.k and BPcal.b
    """
    # FIXME regularize names
    gaincal(
            vis=calMs,
            caltable=calTable,
            field='',
            spw=calSpw,
            intent='',
            selectdata=True,
            scan=calScans,
            solint=calSolint,
            combine='scan',
            preavg=-1.0,
            refant=refAnt,
            minblperant=minBL_for_cal,
            minsnr=5.0,
            solnorm=False,
            gaintype='G',
            smodel=[],
            calmode='ap',
            append=False,
            docallib=False,
            gaintable=[''],
            gainfield=[''],
            interp=[''],
            spwmap=[],
            parang=False,
    )
    # FIXME should perform a check that the caltable was successfully written.
    return getCalFlaggedSoln(calTable)


def semiFinaldelays(
        calMs,
        calTable,
        calField,
        calScans,
        refAnt,
        minBL_for_cal,
        priorcals,
        do3C84,
        UVrange3C84,
    ):
    """
    Note: can't use uvrange for delay cals because it flags all antennas
    beyond uvrange from the refant; so leave as all in delay cal and
    have any residual structure taken out by bandpass and gaincal
    until this is fixed
    """
    # FIXME regularize names
    GainTables=copy.copy(priorcals)
    GainTables.append('semiFinaldelayinitialgain.g')
    # FIXME see note above in docstring.
    #uvrange = UVrange3C84 if do3C84 else ""
    uvrange = ""
    gaincal(
            vis=calMs,
            caltable=calTable,
            field=calField,
            spw='',
            intent='',
            selectdata=True,
            uvrange=uvrange,
            scan=calScans,
            solint='inf',
            combine='scan',
            preavg=-1.0,
            refant=refAnt,
            minblperant=minBL_for_cal,
            minsnr=3.0,
            solnorm=False,
            gaintype='K',
            smodel=[],
            calmode='p',
            append=False,
            docallib=False,
            gaintable=GainTables,
            gainfield=[''],
            interp=[''],
            spwmap=[],
            parang=False,
    )
    # FIXME should validate caltable was written successfully
    return getCalFlaggedSoln(calTable)


def find_3C84(positions):
    MAX_SEPARATION = 60*2.0e-5
    position_3C84 = me.direction('j2000', '3h19m48.160', '41d30m42.106')
    fields_3C84 = []
    for ii in range(0,len(positions)):
        position = me.direction('j2000', str(positions[ii][0])+'rad', str(positions[ii][1])+'rad')
        separation = me.separation(position,position_3C84)['value'] * pi/180.0
        if (separation < MAX_SEPARATION):
                  fields_3C84.append(ii)
    return fields_3C84


def checkblankplot(plotfile, maincasalog):
    """Returns `True` if file is removed."""
    blankplot = False
    fhandle = os.popen('tail ' + maincasalog + ' | grep "Plotting 0 unflagged points."')
    if fhandle.read() != '':
        # Plot is blank, so delete the file
        os.system('rm -rf ' + plotfile)
        logprint("Plot is blank - file removed.", logfileout='logs/targetflag.log')
        blankplot = True
    return blankplot

