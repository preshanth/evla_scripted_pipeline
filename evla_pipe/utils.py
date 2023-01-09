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
import copy
import time
import math
import urllib
import datetime
from pathlib import Path

import numpy as np
# NOTE `np` is aliased in `getBCalStatistics` so use `numpy` directly there.
import numpy

from casatasks import gaincal
from casatools import ms as mstool
from casatools import (table, measures, quanta, msmetadata)
tb = table()
me = measures()
qa = quanta()
msmd = msmetadata()

from . import PIPE_PATH
from .compat import running_within_casa

if not running_within_casa:
    from casatasks import (flagdata, casalog)


log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

MAINLOG = casalog.logfile()


def logprint(msg, logfileout=None):
    if logfileout is None:
        # Print only to main log file
        casalog.setlogfile(MAINLOG)
        casalog.post(msg)
    else:
        # Print to both the passed and main log files
        casalog.setlogfile(logfileout)
        casalog.post(msg)
        casalog.setlogfile(MAINLOG)
        casalog.post(msg)
    print(msg)


class RunTimer:
    log_dir = Path("logs")

    def __init__(self, timing_file="timing.log"):
        self.log_dir.mkdir(exist_ok=True)
        self.timing_file = self.log_dir / timing_file
        self.times = []

    def __call__(self, pipestate, status):
        times = self.times
        times.append({
                'pipestate': pipestate,
                'time': time.time(),
                'status': status,
        })
        if status == "end":
            if len(times) < 2:
                logprint("WARNING Could not write timing, fewer than two measurements.")
            interval = times[-1]['time'] - times[-2]['time']
            with open(self.timing_file, "a") as timelog:
                timelog.write(f"{pipestate}: {interval} sec\n")
        return times

runtiming = RunTimer()


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


def spwsforfield(vis, field_id):
    """
    Get observed DDIDs for the given field ID.
    Included for backword compatibility. Future uses should probably just inline.
    """
    try:
        msmd.open(vis)
        spws = msmd.spwsforfield(field_id)
    finally:
        msmd.close()
    return spws.tolist()


def _calc_separation(pos1, pos2):
    deg_to_rad = np.pi / 180.0
    return me.separation(pos1, pos2)["value"] * deg_to_rad


def find_standards(positions, max_sep=1.2e-3):
    """
    Parameters
    ----------
    max_sep : number, default 1.2e-3 rad (about 4.1 arcmin)
    """
    position_3C48  = me.direction('j2000', '1h37m41.299', '33d9m35.133')
    position_3C138 = me.direction('j2000', '5h21m9.886', '16d38m22.051')
    position_3C147 = me.direction('j2000', '5h42m36.138', '49d51m7.234')
    position_3C286 = me.direction('j2000', '13h31m8.288', '30d30m32.959')
    fields_3C48  = []
    fields_3C138 = []
    fields_3C147 = []
    fields_3C286 = []
    for ii, (lon, lat) in enumerate(positions):
        position = me.direction('j2000', "{0}rad".format(lon), "{0}rad".format(lat))
        separation = _calc_separation(position, position_3C48)
        if _calc_separation(position, position_3C48) < max_sep:
            fields_3C48.append(ii)
        elif _calc_separation(position, position_3C138) < max_sep:
            fields_3C138.append(ii)
        elif _calc_separation(position, position_3C147) < max_sep:
            fields_3C147.append(ii)
        elif _calc_separation(position, position_3C286) < max_sep:
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
        html_lines = html.decode("utf-8").split('\n')
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


# Classes
# -------
# RefAntHeuristics - Chooses the reference antenna heuristics.
# RefAntGeometry   - Contains the geometry heuristics for the reference antenna.
# RefAntFlagging   - Contains the flagging heuristics for the reference antenna.
# FIXME update docstring and writing styles.

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
        self.geo_score = None
        self.flag_score = None

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
        names = self._get_names()
        score = {n: 0.0 for n in names}
        # For each selected heuristic, add the score for each antenna
        if self.geometry:
            ref_ant_geo = RefAntGeometry(self.vis)
            self.geo_score = ref_ant_geo.calc_score()
            for n in names:
                score[n] += self.geo_score[n]
        if self.flagging:
            ref_ant_flag = RefAntFlagging(self.vis, self.field, self.spw, self.intent)
            self.flag_score = ref_ant_flag.calc_score()
            for n in names:
                try:
                    score[n] += self.flag_score[n]
                except KeyError as e:
                    logprint(f"WARNING: antenna {e}, is completely flagged and missing from calibrators.ms", logfileout='logs/refantwarnings.log')
        # Calculate the final score and return the list of ranked reference
        # antennas.  The best antennas have the highest score, so a reverse
        # sort is required.
        keys = np.array(list(score.keys()))
        values = np.array(list(score.values()))
        argSort = np.argsort(values)[::-1]
        refAntUpper = keys[argSort]
        refAnt = list()
        for r in refAntUpper:
            refAnt.append(r.lower())
        # Return the list of ranked reference antennas
        return refAnt

    def _get_names(self):
        try:
            tb.open(self.vis+'/ANTENNA')
            names = tb.getcol('NAME').tolist()
        finally:
            tb.close()
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
        measures = self._get_measures(info)
        radii, longs, lats = self._get_latlongrad(info, measures)
        # Calculate the antenna distances and scores
        distance = self._calc_distance(radii, longs, lats)
        score = self._calc_score(distance)
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
        info = dict()
        try:
            tb.open( self.vis+'/ANTENNA' )
            # Get the antenna information from the antenna table
            info['position'] = tb.getcol('POSITION')
            info['flag_row'] = tb.getcol('FLAG_ROW')
            info['name'] = tb.getcol('NAME')
            info['position_keywords'] = tb.getcolkeywords('POSITION')
        finally:
            tb.close()
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
        # Initialize the measures dictionary and the position and
        # position_keywords variables
        measures = dict()
        position = info['position']
        position_keywords = info['position_keywords']
        rf = position_keywords['MEASINFO']['Ref']
        for row, ant in enumerate(info['name']):
            if not info['flag_row'][row]:
                p = position[0, row]
                pk = position_keywords['QuantumUnits'][0]
                v0 = qa.quantity(p, pk)
                #
                p = position[1, row]
                pk = position_keywords['QuantumUnits'][1]
                v1 = qa.quantity(p, pk)
                #
                p = position[2, row]
                pk = position_keywords['QuantumUnits'][2]
                v2 = qa.quantity(p, pk)
                measures[ant] = me.position(rf=rf, v0=v0, v1=v1, v2=v2)
        return measures

    def _get_latlongrad(self, info, measures):
        """
        Get the latitude, longitude and radius (from the center of the earth)
        for each antenna.

        Parameters
        ----------
        info     - Dictionary of the antenna information from private member
                   function _get_info().
        measures - Dictionary of the antenna measures from private member
                   function _get_measures().

        Returns
        -------
        Tuple containing containing radius, longitude, and latitude dictionaries.
        """
        # The `measures` dictionary follows:
        #   {"ea01": {"m0": {"value": 1, "unit": "m"} ...}}
        # The values from `qa.getvalue` are returned as a single-element numpy
        # arrays so must be indexed to return a scalar value.
        def get_measures_value(ant, ax, as_unit):
            quantity = qa.convert(measures[ant][ax], as_unit)
            return qa.getvalue(quantity)[0]
        ant_names = info["name"]
        radii = {a: get_measures_value(a, "m2", "m")   for a in ant_names}
        lons  = {a: get_measures_value(a, "m0", "rad") for a in ant_names}
        lats  = {a: get_measures_value(a, "m1", "rad") for a in ant_names}
        return radii, lons, lats

    def _calc_distance(self, radii, lons, lats):
        """
        Calculate the antenna distances from the array reference from the
        radii, longitudes, and latitudes.

        NB: The array reference is the median location.

        Parameters
        ----------
        radii - Radius (from the center of the earth) dictionary for each antenna.
        lons  - Longitude dictionary for each antenna.
        lats  - Latitude dictionary for each antenna.

        Results
        -------
        Dictionary containing the antenna distances from the array reference.
        """
        # Convert the dictionaries to numpy float arrays.
        rad = np.array(list(radii.values()))
        lon = np.array(list(lons.values()))
        lat = np.array(list(lats.values()))
        lon -= np.median(lon)
        # Calculate the "x" and "y" antenna locations and subtract medians.
        x = lon * np.cos(lat) * rad
        y = lat * rad
        x -= np.median(x)
        y -= np.median(y)
        # Calculate the antenna distances from the array reference
        distance = {
                ant_name: np.sqrt(x[i]**2 + y[i]**2)
                for i, ant_name in enumerate(radii.keys())
        }
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
        far = np.array(list(distance.values()), float)
        n = far.shape[0]
        closeness_score = (1 - far / far.max()) * n
        score = {
                name: closeness_score[i]
                for i, name in enumerate(distance.keys())
        }
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
        # Calculate the good data total for each antenna.
        good = {
                name: vals["total"] - vals["flagged"]
                for name, vals in results["antenna"].items()
        }
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
        good - Dictionary of unflagged (good) data from the MS. They are
               obtained in private member function _get_good().

        Returns
        -------
        Dictionary containing the score for each antenna.
        """
        unflag = np.array(list(good.values()), float)
        n = unflag.shape[0]
        unflagged_score = unflag / unflag.max() * n
        score = {
                name: unflagged_score[i]
                for i, name in enumerate(good.keys())
        }
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
        separation = me.separation(position,position_3C84)['value'] * np.pi/180.0
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


def getCalFlaggedSoln(calTable):
    """
    This method will look at the specified calibration table and return the
    fraction of flagged solutions for each Antenna, SPW, Poln.  This assumes
    that the specified cal table will not have any channel dependent flagging.

    The return structure is a dictionary with AntennaID and Spectral Window ID
    as the keys and returns a list of fractional flagging per polarization in
    the order specified in the Cal Table.

    STM 2012-05-03 revised dictionary structure:
    key: 'all' all solutions
             ['all']['total'] = <number>
             ['all']['flagged'] = <number>
             ['all']['fraction'] = <fraction>

         'antspw' indexed by antenna and spectral window id per poln
             ['antspw'][<antid>][<spwid>][<polid>]['total'] = <total number sols per poln>
             ['antspw'][<antid>][<spwid>][<polid>]['flagged'] = <flagged number sols per poln>
             ['antspw'][<antid>][<spwid>][<polid>]['fraction'] = <flagged fraction per poln>

         'ant' indexed by antenna summed over spectral window per poln
             ['ant'][<antid>][<polid>]['total'] = <total number sols per poln>
             ['ant'][<antid>][<polid>]['flagged'] = <flagged number sols per poln>
             ['ant'][<antid>][<polid>]['fraction'] = <flagged fraction per poln>

         'spw' indexed by spectral window summed over antenna per poln
             ['spw'][<spwid>][<polid>]['total'] = <total number sols per poln>
             ['spw'][<spwid>][<polid>]['flagged'] = <flagged number sols per poln>
             ['spw'][<spwid>][<polid>]['fraction'] = <flagged fraction per poln>

         'antmedian' median fractions over antenna summed over spw and polarization
             ['total'] = median <total number sols per ant>
             ['flagged'] = median <flagged number sols per ant>
             ['fraction'] = median <flagged fraction of sols per ant>
             ['number'] = number of antennas that went into the median

    Note that fractional numbers flagged per poln are computed as a fraction of channels
    (thus a full set of channels for a given ant/spw/poln count as 1.0)

    Example:

    ```
    !cp /home/sandrock2/smyers/casa/pipeline/lib_EVLApipeutils.py .
    from lib_EVLApipeutils import getCalFlaggedSoln
    result = getCalFlaggedSoln('calSN2010FZ.G0')
    result['all']
        Out: {'flagged': 1212, 'fraction': 0.16031746031746033, 'total': 7560}
    result['antspw'][21][7]
        Out: {0: {'flagged': 3.0, 'fraction': 0.29999999999999999, 'total': 10},
              1: {'flagged': 3.0, 'fraction': 0.29999999999999999, 'total': 10}}
    result['ant'][15]
        Out: {0: {'flagged': 60.0, 'fraction': 0.42857142857142855, 'total': 140},
              1: {'flagged': 60.0, 'fraction': 0.42857142857142855, 'total': 140}}
    result['spw'][3]
        Out: {0: {'flagged': 39.0, 'fraction': 0.14444444444444443, 'total': 270},
              1: {'flagged': 39.0, 'fraction': 0.14444444444444443, 'total': 270}}

    Bresult = getCalFlaggedSoln('calSN2010FZ.B0')
    Bresult['all']
        Out: {'flagged': 69.171875, 'fraction': 0.091497189153439157, 'total': 756}
    Bresult['ant'][15]
        Out: {0: {'flagged': 6.03125, 'fraction': 0.43080357142857145, 'total': 14},
              1: {'flagged': 6.03125, 'fraction': 0.43080357142857145, 'total': 14}}
    Bresult['antmedian']
        Out: {'flagged': 0.0625, 'fraction': 0.002232142857142857, 'number': 27, 'total': 28.0}
    ```

    Another example, to make a list of spws in the caltable that have any
    unflagged solutions in them:

    ```
    G2result = getCalFlaggedSoln('calSN2010FZ.G2.2')
    goodspw = []
    for ispw in G2result['spw'].keys():
        tot = 0
        flagd = 0
        for ipol in G2result['spw'][ispw].keys():
            tot += G2result['spw'][ispw][ipol]['total']
            flagd += G2result['spw'][ispw][ipol]['flagged']
        if tot>0:
            fract = flagd/tot
            if fract<1.0:
                goodspw.append(ispw)
    goodspw
        Out: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    ```

    Changelog
    ---------
    2012-05-03 v1.0 STM to 3.4 from original 3.3 version, new dictionary
    2012-05-03 v1.1 STM indexed by ant, spw also
    2012-09-11 v1.1 STM correct doc of <polid> indexing, bug fix, median over ant
    2012-09-12 v1.2 STM median over ant revised
    2012-11-13 v2.0 STM casa 4.0 version with new call mechanism
    2013-01-11 v2.1 STM use getvarcol
    """
    mytb = table()

    mytb.open(calTable)
    antCol = mytb.getcol('ANTENNA1')
    spwCol = mytb.getcol('SPECTRAL_WINDOW_ID')
    fldCol = mytb.getcol('FIELD_ID')
    #flagCol = mytb.getcol('FLAG')
    flagVarCol = mytb.getvarcol('FLAG')
    mytb.close()

    # Initialize a list to hold the results
    # Get shape of FLAG
    #(np,nc,ni) = flagCol.shape
    rowlist = flagVarCol.keys()
    nrows = len(rowlist)

    # Create the output dictionary
    outDict = {}
    outDict['all'] = {}
    outDict['antspw'] = {}
    outDict['ant'] = {}
    outDict['spw'] = {}
    outDict['antmedian'] = {}

    # Ok now go through and for each row and possibly channel compile flags
    ntotal = 0
    nflagged = 0
    # Lists for median calc
    medDict = {}
    medDict['total'] = []
    medDict['flagged'] = []
    medDict['fraction'] = []

    for rrow in rowlist:
        rown = rrow.strip('r')
        idx = int(rown)-1
        antIdx = antCol[idx]
        spwIdx = spwCol[idx]
        #
        flagArr = flagVarCol[rrow]
        # Get the shape of this data row
        (np,nc,ni) = flagArr.shape
        # ni should be 1 for this
        iid = 0
        #
        # Set up dictionaries if needed
        if antIdx in outDict['antspw']:
            if spwIdx not in outDict['antspw'][antIdx]:
                outDict['antspw'][antIdx][spwIdx] = {}
                for poln in range(np):
                    outDict['antspw'][antIdx][spwIdx][poln] = {}
                    outDict['antspw'][antIdx][spwIdx][poln]['total'] = 0
                    outDict['antspw'][antIdx][spwIdx][poln]['flagged'] = 0
        else:
            outDict['ant'][antIdx] = {}
            outDict['antspw'][antIdx] = {}
            outDict['antspw'][antIdx][spwIdx] = {}
            for poln in range(np):
                outDict['ant'][antIdx][poln] = {}
                outDict['ant'][antIdx][poln]['total'] = 0
                outDict['ant'][antIdx][poln]['flagged'] = 0.0
                outDict['antspw'][antIdx][spwIdx][poln] = {}
                outDict['antspw'][antIdx][spwIdx][poln]['total'] = 0
                outDict['antspw'][antIdx][spwIdx][poln]['flagged'] = 0.0
        if spwIdx not in outDict['spw']:
            outDict['spw'][spwIdx] = {}
            for poln in range(np):
                outDict['spw'][spwIdx][poln] = {}
                outDict['spw'][spwIdx][poln]['total'] = 0
                outDict['spw'][spwIdx][poln]['flagged'] = 0.0
        #
        # Sum up the in-row (per pol per chan) flags for this row
        nptotal = 0
        npflagged = 0
        for poln in range(np):
            ntotal += 1
            nptotal += 1
            ncflagged = 0
            for chan in range(nc):
                if flagArr[poln][chan][iid]:
                    ncflagged += 1
            npflagged = float(ncflagged)/float(nc)
            nflagged += float(ncflagged)/float(nc)
            #
            outDict['ant'][antIdx][poln]['total'] += 1
            outDict['spw'][spwIdx][poln]['total'] += 1
            outDict['antspw'][antIdx][spwIdx][poln]['total'] += 1
            #
            outDict['ant'][antIdx][poln]['flagged'] += npflagged
            outDict['spw'][spwIdx][poln]['flagged'] += npflagged
            outDict['antspw'][antIdx][spwIdx][poln]['flagged'] += npflagged
            #

    outDict['all']['total'] = ntotal
    outDict['all']['flagged'] = nflagged
    if ntotal>0:
        outDict['all']['fraction'] = float(nflagged)/float(ntotal)
    else:
        outDict['all']['fraction'] = 0.0

    # Go back and get fractions
    for antIdx in outDict['ant'].keys():
        nptotal = 0
        npflagged = 0
        for poln in outDict['ant'][antIdx].keys():
            nctotal = outDict['ant'][antIdx][poln]['total']
            ncflagged = outDict['ant'][antIdx][poln]['flagged']
            outDict['ant'][antIdx][poln]['fraction'] = float(ncflagged)/float(nctotal)
            #
            nptotal += nctotal
            npflagged += ncflagged
        medDict['total'].append(nptotal)
        medDict['flagged'].append(npflagged)
        medDict['fraction'].append(float(npflagged)/float(nptotal))
    #
    for spwIdx in outDict['spw'].keys():
        for poln in outDict['spw'][spwIdx].keys():
            nptotal = outDict['spw'][spwIdx][poln]['total']
            npflagged = outDict['spw'][spwIdx][poln]['flagged']
            outDict['spw'][spwIdx][poln]['fraction'] = float(npflagged)/float(nptotal)
    #
    for antIdx in outDict['antspw'].keys():
        for spwIdx in outDict['antspw'][antIdx].keys():
            for poln in outDict['antspw'][antIdx][spwIdx].keys():
                nptotal = outDict['antspw'][antIdx][spwIdx][poln]['total']
                npflagged = outDict['antspw'][antIdx][spwIdx][poln]['flagged']
                outDict['antspw'][antIdx][spwIdx][poln]['fraction'] = float(npflagged)/float(nptotal)
    # do medians
    outDict['antmedian'] = {}
    for item in medDict.keys():
        alist = medDict[item]
        aarr = numpy.array(alist)
        amed = numpy.median(aarr)
        outDict['antmedian'][item] = amed
    outDict['antmedian']['number'] = len(medDict['fraction'])

    return outDict


def buildscans(msfile):
    """
    Compile scan information for a measurement set.

    Usage:
           from lib_EVLApipeutils import buildscans

    Input:

            msfile   -   name of MS

    Output: scandict (return value)

    Examples:

    CASA <2>: from lib_EVLApipeutils import buildscans

    CASA <3>: msfile = 'TRSR0045_sb600507.55900.ms'

    CASA <4>: myscans = buildscans(msfile)
    Getting scansummary from MS
    Found 16 DataDescription IDs
    Found 4 StateIds
    Found 3422 times in DD=0
    Found 3422 times in DD=1
    Found 3422 times in DD=2
    Found 3422 times in DD=3
    Found 3422 times in DD=4
    Found 3422 times in DD=5
    Found 3422 times in DD=6
    Found 3422 times in DD=7
    Found 3422 times in DD=8
    Found 3422 times in DD=9
    Found 3422 times in DD=10
    Found 3422 times in DD=11
    Found 3422 times in DD=12
    Found 3422 times in DD=13
    Found 3422 times in DD=14
    Found 3422 times in DD=15
    Found total 54752 times
    Found 175 scans min=1 max=180
    Size of scandict in memory is 248 bytes

    CASA <5>: myscans['Scans'][1]['intents']
      Out[5]: 'CALIBRATE_AMPLI#UNSPECIFIED,UNSPECIFIED#UNSPECIFIED'

    CASA <6>: myscans['Scans'][1]['dd']
      Out[6]: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    CASA <7>: myscans['DataDescription'][0]
      Out[7]:
    {'corrdesc': ['RR', 'RL', 'LR'', 'LL'],
     'corrtype': [5, 6, 7, 8],
     'ipol': 0,
     'nchan': 64,
     'npol': 4,
     'reffreq': 994000000.0,
     'spw': 0,
     'spwname': 'Subband:0'}

    CASA <8>: myscans['Scans'][1]['times'][0]
      Out[8]:
    [4829843281.500001,
     4829843282.5,
     4829843283.5,
     4829843284.5,
     ...
     4829843336.5]

    The last of these returns the integration midpoints for scan 1 DD 0.

    Note that to get spw and pol info you use the DD indexes from ['dd']
    in the 'Scans' part to index into the 'DataDescription' info.

    You can also list the keys available in the Scans sub-dictionary:

    CASA <9>: myscans['Scans'][1].keys()
      Out[9]:
    ['scan_mid',
     'intents',
     'field',
     'dd',
     'npol',
     'rra',
     'spw',
     'scan_int',
     'scan_start',
     'times',
     'scan_end',
     'rdec']

    Changelog
    ---------
    Created S.T. Myers 2012-05-07  v1.0
    Updated S.T. Myers 2012-05-14  v1.1 add corrtype
    Updated S.T. Myers 2012-06-27  v1.2 add corrdesc lookup
    Updated S.T. Myers 2012-11-13  v2.0 STM casa 4.0 new calls
    """
    # dictionary with lookup for correlation strings
    # from http://casa.nrao.edu/docs/doxygen/html/classcasa_1_1Stokes.html
    cordesclist = ['Undefined',
                   'I',
                   'Q',
                   'U',
                   'V',
                   'RR',
                   'RL',
                   'LR',
                   'LL',
                   'XX',
                   'XY',
                   'YX',
                   'YY',
                   'RX',
                   'RY',
                   'LX',
                   'LY',
                   'XR',
                   'XL',
                   'YR',
                   'YL',
                   'PP',
                   'PQ',
                   'QP',
                   'QQ',
                   'RCircular',
                   'LCircular',
                   'Linear',
                   'Ptotal',
                   'Plinear',
                   'PFtotal',
                   'PFlinear',
                   'Pangle' ]
    #
    # Usage: find desc for an index, e.g. cordesclist[corrtype]
    #        find index for a desc, e.g. cordesclist.index(corrdesc)
    #
    ms = mstool()
    tb = table()

    # Access the MS
    try:
        ms.open(msfile,nomodify=True)
    except:
        print(f"ERROR: failed to open ms tool on file {msfile}")
        exit(1)

    print('Getting scansummary from MS')
    scd = ms.getscansummary()

    # Find number of data description IDs
    tb.open(msfile+"/DATA_DESCRIPTION")
    ddspwarr=tb.getcol("SPECTRAL_WINDOW_ID")
    ddpolarr=tb.getcol("POLARIZATION_ID")
    tb.close()
    ddspwlist = ddspwarr.tolist()
    ddpollist = ddpolarr.tolist()
    ndd = len(ddspwlist)
    print(f'Found {ndd} DataDescription IDs')
    #
    # The SPECTRAL_WINDOW table
    tb.open(msfile+"/SPECTRAL_WINDOW")
    nchanarr=tb.getcol("NUM_CHAN")
    spwnamearr=tb.getcol("NAME")
    reffreqarr=tb.getcol("REF_FREQUENCY")
    tb.close()
    nspw = len(nchanarr)
    spwlookup = {}
    for isp in range(nspw):
        spwlookup[isp] = {}
        spwlookup[isp]['nchan'] = nchanarr[isp]
        spwlookup[isp]['name'] = str( spwnamearr[isp] )
        spwlookup[isp]['reffreq'] = reffreqarr[isp]
    print('Extracted information for '+str(nspw)+' SpectralWindows')
    #
    # Now the polarizations (number of correlations in each pol id
    tb.open(msfile+"/POLARIZATION")
    ncorarr=tb.getcol("NUM_CORR")
    # corr_type is in general variable shape, have to read row-by-row
    # or use getvarcol to return into dictionary, we will iterate manually
    npols = len(ncorarr)
    polindex = {}
    poldescr = {}
    for ip in range(npols):
        cort=tb.getcol("CORR_TYPE",startrow=ip,nrow=1)
        (nct,nr) = cort.shape
        cortypes = []
        cordescs = []
        for ict in range(nct):
            cct = cort[ict][0]
            cde = cordesclist[cct]
            cortypes.append(cct)
            cordescs.append(cde)
        polindex[ip] = cortypes
        poldescr[ip] = cordescs
    # cortype is an array of npol, e.g. 5,6,7,8 is for RR,RL,LR,LL respectively
    # for alma this would be 9,10,11,12 for XX,XY,YX,YY respectively
    # cordesc are the strings associated with the types (enum for casa)
    tb.close()
    print('Extracted information for '+str(npols)+' Polarization Setups')
    #
    # Build the DD index
    #
    ddindex = {}
    ncorlist=ncorarr.tolist()
    for idd in range(ndd):
        ddindex[idd] = {}
        isp = ddspwlist[idd]
        ddindex[idd]['spw'] = isp
        ddindex[idd]['spwname'] = spwlookup[isp]['name']
        ddindex[idd]['nchan'] = spwlookup[isp]['nchan']
        ddindex[idd]['reffreq'] = spwlookup[isp]['reffreq']
        #
        ipol = ddpollist[idd]
        ddindex[idd]['ipol'] = ipol
        ddindex[idd]['npol'] = ncorlist[ipol]
        ddindex[idd]['corrtype'] = polindex[ipol]
        ddindex[idd]['corrdesc'] = poldescr[ipol]
    #
    # Now get raw scan intents from STATE table
    tb.open(msfile+"/STATE")
    intentarr=tb.getcol("OBS_MODE")
    subscanarr=tb.getcol("SUB_SCAN")
    tb.close()
    intentlist = intentarr.tolist()
    subscanlist = subscanarr.tolist()
    nstates = intentlist.__len__()
    print('Found '+str(nstates)+' StateIds')
    #
    # Now get FIELD table directions
    tb.open(msfile+"/FIELD")
    fnamearr=tb.getcol("NAME")
    fpdirarr=tb.getcol("PHASE_DIR")
    tb.close()
    flist = fnamearr.tolist()
    nfields = len(flist)
    (nd1, nd2, npf) = fpdirarr.shape
    fielddict = {}
    for ifld in range(nfields):
        fielddict[ifld] = {}
        fielddict[ifld]['name'] = flist[ifld]
        # these are numpy.float64
        fielddict[ifld]['rra'] = fpdirarr[0,0,ifld]
        fielddict[ifld]['rdec'] = fpdirarr[1,0,ifld]
    #
    # Now compile list of visibility times and info
    #
    # Extract times from the Main Table
    # Build lookup for DDs by scan_number
    timdict = {}
    ddlookup = {}
    ddscantimes = {}
    ntottimes=0
    for idd in range(ndd):
        # Select this DD (after reset if needed)
        if idd>0: ms.selectinit(reset=True)
        ms.selectinit(idd)
        #recf = ms.getdata(["flag"])
        #(nx,nc,ni) = recf['flag'].shape
        # get the times
        rect = ms.getdata(["time","field_id","scan_number"],ifraxis=True)
        nt = rect['time'].shape[0]
        ntottimes+=nt
        print('Found '+str(nt)+' times in DD='+str(idd))
        #
        timdict[idd] = {}
        timdict[idd]['time'] = rect['time']
        timdict[idd]['field_id'] = rect['field_id']
        timdict[idd]['scan_number'] = rect['scan_number']
        #
        for it in range(nt):
            isc = rect['scan_number'][it]
            tim = rect['time'][it]
            if isc in ddlookup:
                if ddlookup[isc].count(idd)<1:
                    ddlookup[isc].append(idd)
                if idd in ddscantimes[isc]:
                    ddscantimes[isc][idd].append(tim)
                else:
                    ddscantimes[isc][idd] = [tim]
            else:
                ddlookup[isc] = [idd]
                ddscantimes[isc] = {}
                ddscantimes[isc][idd] = [tim]

    #
    print('Found total '+str(ntottimes)+' times')

    ms.close()

    # compile a list of scan times
    #
    #scd = mysc['summary']
    scanlist = []
    scanindex = {}
    scl = scd.keys()
    for sscan in scl:
        isc = int(sscan)
        scanlist.append(isc)
        scanindex[isc]=sscan

    scanlist.sort()

    nscans = len(scanlist)
    print('Found '+str(nscans)+' scans min='+str(min(scanlist))+' max='+str(max(scanlist)))

    scantimes = []
    scandict = {}

    # Put DataDescription lookup into dictionary
    scandict['DataDescription'] = ddindex

    # Put Scan information in dictionary
    scandict['Scans'] = {}
    for isc in scanlist:
        sscan = scanindex[isc]
        # sub-scans, differentiated by StateId
        subs = scd[sscan].keys()
        #
        scan_start = -1.
        scan_end = -1.
        for ss in subs:
            bt = scd[sscan][ss]['BeginTime']
            et = scd[sscan][ss]['EndTime']
            if scan_start>0.:
                if bt<scan_start:
                    scan_start=bt
            else:
                scan_start=bt
            if scan_end>0.:
                if et>scan_end:
                    scan_end=et
            else:
                scan_end=et
        scan_mid = 0.5*(scan_start + scan_end)

        scan_int = scd[sscan]['0']['IntegrationTime']

        scantimes.append(scan_mid)

        scandict['Scans'][isc] = {}
        scandict['Scans'][isc]['scan_start'] = scan_start
        scandict['Scans'][isc]['scan_end'] = scan_end
        scandict['Scans'][isc]['scan_mid'] = scan_mid
        scandict['Scans'][isc]['scan_int'] = scan_int

        ifld = scd[sscan]['0']['FieldId']
        scandict['Scans'][isc]['field'] = ifld
        scandict['Scans'][isc]['rra'] = fielddict[ifld]['rra']
        scandict['Scans'][isc]['rdec'] = fielddict[ifld]['rdec']

        spws = scd[sscan]['0']['SpwIds']
        scandict['Scans'][isc]['spw'] = spws.tolist()

        # state id of first sub-scan
        stateid = scd[sscan]['0']['StateId']
        # get intents from STATE table
        intents = intentlist[stateid]
        # this is a string with comma-separated intents
        scandict['Scans'][isc]['intents'] = intents

        # DDs for this scan
        ddlist = ddlookup[isc]
        scandict['Scans'][isc]['dd'] = ddlist

        # number of polarizations for this list of dds
        ddnpollist = []
        for idd in ddlist:
            npol = ddindex[idd]['npol']
            ddnpollist.append(npol)
        scandict['Scans'][isc]['npol'] = ddnpollist

        # visibility times per dd in this scan
        #
        scandict['Scans'][isc]['times'] = {}
        for idd in ddlist:
            scandict['Scans'][isc]['times'][idd] = ddscantimes[isc][idd]

    mysize = scandict.__sizeof__()
    print('Size of scandict in memory is '+str(mysize)+' bytes')
    return scandict


def getBCalStatistics(calTable, innerbuff=0.1):
    """
    This method will look at the specified B calibration table and return the
    statistics of unflagged solutions for each Antenna, SPW, Poln.  This assumes
    that the specified cal table will not have any channel dependent flagging.

    return structure is a dictionary with AntennaID and Spectral Window ID
    as the keys and returns a list of statistics per polarization in
    the order specified in the Cal Table.

    Input:

         calTable  -  name of MS
         innerbuff -  fraction of spw bandwidth to ignore at each edge
                      (<0.5, default=0.1 use inner 80% of channels each spw)

    Output: OutDict (return value)

    STM 2012-11-19 dictionary structure:
    key: 'antspw' indexed by antenna and spectral window id per poln
             ['antspw'][<antid>][<spwid>][<polid>]

         'antband' indexed by antenna and rx/baseband summed over subbands and poln
             ['ant'][<antid>][<rxband>][<baseband>]
             Note: this requires that the spectral window NAME follow JVLA convention of
                   rxband#baseband#spw (e.g. 'EVLA_K#A0C0#48')

    For each of these there is a data structure for ['all'] and ['inner']
    that contains the fields: ['total'], ['number'], ['mean'], ['min'], ['max']

    Some useful indexing dictionaries are also output:
       ['antDict'][ant] the name of antenna with index ant
       ['spwDict'][spw] {'RX':rx, 'Baseband':bb, 'Subband':sb} correspoding to a given spw
       ['rxBasebandDict'][rx][bb] list of spws corresponding to a given rx and bb

    Example:

    ```
    !cp /home/sandrock2/smyers/casa/pipeline/pipeline4.1/lib_EVLApipeutils.py .
    from lib_EVLApipeutils import getBCalStatistics
    result = getBCalStatistics('testBPcal.b')

    This is a B Jones table, proceeding
    Found 1 Rx bands
    Rx band EVLA_K has basebands: ['A0C0', 'B0D0']
    Within all channels:
    Found 864 total solutions with 47824 good (unflagged)
    Within inner 0.8 of channels:
    Found 0 total solutions with 42619 good (unflagged)

        AntID      AntName      Rx-band      Baseband    min/max(all)  min/max(inner) ALERT?
            0         ea01       EVLA_K         A0C0        0.3541        0.3575
            0         ea01       EVLA_K         B0D0        0.4585        0.4591
            1         ea02       EVLA_K         A0C0        0.3239        0.3298
            1         ea02       EVLA_K         B0D0        0.2130        0.2179
            2         ea03       EVLA_K         A0C0        0.3097        0.3124
            2         ea03       EVLA_K         B0D0        0.3247        0.3282
            3         ea04       EVLA_K         A0C0        0.3029        0.3055
            3         ea04       EVLA_K         B0D0        0.2543        0.2543
            4         ea05       EVLA_K         A0C0        0.2657        0.2715
            4         ea05       EVLA_K         B0D0        0.2336        0.2357
            5         ea06       EVLA_K         A0C0        0.3474        0.3501
            5         ea06       EVLA_K         B0D0        0.2371        0.2398
            6         ea07       EVLA_K         A0C0        0.2294        0.2322
            6         ea07       EVLA_K         B0D0        0.3684        0.3690
            7         ea08       EVLA_K         A0C0        0.2756        0.2809
            7         ea08       EVLA_K         B0D0        0.5269        0.5269
            8         ea10       EVLA_K         A0C0        0.2617        0.2686
            8         ea10       EVLA_K         B0D0        0.2362        0.2407
            9         ea11       EVLA_K         A0C0        0.2594        0.2607
            9         ea11       EVLA_K         B0D0        0.3015        0.3111
           10         ea12       EVLA_K         A0C0        0.2418        0.2491
           10         ea12       EVLA_K         B0D0        0.3839        0.3849
           11         ea13       EVLA_K         A0C0        0.3017        0.3156
           11         ea13       EVLA_K         B0D0        0.3299        0.3299
           12         ea14       EVLA_K         A0C0        0.2385        0.2415
           12         ea14       EVLA_K         B0D0        0.2081        0.2101
           13         ea15       EVLA_K         A0C0        0.3118        0.3151
           13         ea15       EVLA_K         B0D0        0.1749        0.1844 *
           14         ea16       EVLA_K         A0C0        0.2050        0.2051
           14         ea16       EVLA_K         B0D0        0.4386        0.4537
           15         ea17       EVLA_K         A0C0        0.4084        0.4107
           15         ea17       EVLA_K         B0D0        0.2151        0.2189
           16         ea18       EVLA_K         A0C0        0.3124        0.3147
           16         ea18       EVLA_K         B0D0        0.3712        0.3730
           17         ea19       EVLA_K         A0C0        0.3084        0.3132
           17         ea19       EVLA_K         B0D0        0.2453        0.2522
           18         ea20       EVLA_K         A0C0        0.4618        0.4672
           18         ea20       EVLA_K         B0D0        0.2772        0.2790
           19         ea21       EVLA_K         A0C0        0.3971        0.4032
           19         ea21       EVLA_K         B0D0        0.2812        0.2818
           20         ea22       EVLA_K         A0C0        0.2495        0.2549
           20         ea22       EVLA_K         B0D0        0.3777        0.3833
           21         ea23       EVLA_K         A0C0        0.3213        0.3371
           21         ea23       EVLA_K         B0D0        0.2702        0.2787
           22         ea24       EVLA_K         A0C0        0.2470        0.2525
           22         ea24       EVLA_K         B0D0        0.0127        0.0127 ***
           23         ea25       EVLA_K         A0C0        0.3173        0.3205
           23         ea25       EVLA_K         B0D0        0.0056        0.0066 ***
           24         ea26       EVLA_K         A0C0        0.3505        0.3550
           24         ea26       EVLA_K         B0D0        0.4028        0.4071
           25         ea27       EVLA_K         A0C0        0.3165        0.3244
           25         ea27       EVLA_K         B0D0        0.2644        0.2683
           26         ea28       EVLA_K         A0C0        0.1695        0.1712 *
           26         ea28       EVLA_K         B0D0        0.3213        0.3318

    result['antband'][22]['EVLA_K']['B0D0']
       Out:
         {'all': {'amp': {'max': 3.3507643208628997,
                          'mean': 1.2839660621605888,
                          'min': 0.042473547230042749,
                          'var': 0.42764307104292559},
                  'imag': {'max': array(1.712250828742981),
                           'mean': -0.0042696134968516824,
                           'min': array(-2.2086853981018066),
                           'var': 0.43859873853192027},
                  'number': 900,
                  'phase': {'max': 112.32456525225054,
                            'mean': -0.70066399447640126,
                            'min': -108.23612296337477,
                            'var': 1445.9499062237583},
                  'real': {'max': array(3.3105719089508057),
                           'mean': 1.0975328904785548,
                           'min': array(-0.13342639803886414),
                           'var': 0.433613996950728},
                  'total': 1024},
          'inner': {'amp': {'max': 3.3507643208628997,
                            'mean': 1.2913493102726084,
                            'min': 0.042473547230042749,
                            'var': 0.45731194085061877},
                    'imag': {'max': array(1.712250828742981),
                             'mean': -0.0019235184823728287,
                             'min': array(-2.2086853981018066),
                             'var': 0.43650578363669668},
                    'number': 802,
                    'phase': {'max': 112.32456525225054,
                              'mean': -0.74464737957566107,
                              'min': -108.23612296337477,
                              'var': 1496.4536912732597},
                    'real': {'max': array(3.3105719089508057),
                             'mean': 1.1054519462910002,
                             'min': array(-0.13342639803886414),
                             'var': 0.4665390728630604},
                    'total': 816}}

    result['rxBasebandDict']['EVLA_K']['B0D0']
       Out: [8, 9, 10, 11, 12, 13, 14, 15]


    result['antspw'][22][10]
       Out:
         {0: {'all': {'amp': {'max': 3.3507643208628997,
                              'mean': 1.6887832659451747,
                              'min': 0.054888048286296932,
                              'var': 0.84305637195708472},
                      'imag': {'max': array(1.4643619060516357),
                               'mean': -0.13419617990315968,
                               'min': array(-2.2086853981018066),
                               'var': 0.97892254522390565},
                      'number': 59,
                      'phase': {'max': 112.32456525225054,
                                'mean': -1.0111711887628112,
                                'min': -102.4143890204484,
                                'var': 2885.5110793438112},
                      'real': {'max': array(3.3105719089508057),
                               'mean': 1.2845739619253926,
                               'min': array(-0.13342639803886414),
                               'var': 1.0099576839663802},
                      'total': 64},
              'inner': {'amp': {'max': 3.3507643208628997,
                                'mean': 1.1064667538670538,
                                'min': 0.054888048286296932,
                                'var': 0.94882587512210448},
                        'imag': {'max': array(1.4643619060516357),
                                 'mean': 0.056129313275038409,
                                 'min': array(-2.2086853981018066),
                                 'var': 0.55401604820332395},
                        'number': 201,
                        'phase': {'max': 112.32456525225054,
                                  'mean': 17.99353823044413,
                                  'min': -102.4143890204484,
                                  'var': 5065.0038289850836},
                        'real': {'max': array(3.3105719089508057),
                                 'mean': 0.75592079894228781,
                                 'min': array(-0.13342639803886414),
                                 'var': 0.89091406078797231},
                        'total': 51}},
         1: {'all': {'amp': {'max': 1.0603890232940267,
                              'mean': 0.9966154059201201,
                              'min': 0.92736792814263314,
                              'var': 0.032951023002670755},
                      'imag': {'max': array(0.28490364551544189),
                               'mean': 0.10552169008859259,
                               'min': array(-0.08266795426607132),
                               'var': 0.017548692059680165},
                      'number': 59,
                      'phase': {'max': 17.237656150196859,
                                'mean': 6.0660176622725466,
                                'min': -4.9577763029789832,
                                'var': 40.224751029787001},
                      'real': {'max': array(1.047441840171814),
                               'mean': 0.98505325640662234,
                               'min': array(0.90479201078414917),
                               'var': 0.032541082320460629},
                      'total': 64},
              'inner': {'amp': {'max': 1.0603890232940267,
                                'mean': 1.0327309832106102,
                                'min': 0.92837663017787742,
                                'var': 0.19543922221719845},
                        'imag': {'max': array(0.26414120197296143),
                                 'mean': 0.13256895535348001,
                                 'min': array(-0.08266795426607132),
                                 'var': 0.036957882304178208},
                        'number': 201,
                        'phase': {'max': 15.395755389451365,
                                  'mean': 7.3133434743802201,
                                  'min': -4.9577763029789832,
                                  'var': 18.607793373980815},
                        'real': {'max': array(1.047441840171814),
                                 'mean': 1.0216352563400155,
                                 'min': array(0.92740714550018311),
                                 'var': 0.19275019403126262},
                        'total': 51}}}
    ```

    NOTE: You can see the problem is in poln 0 of this spw from the amp range and phase.

    Changelog
    ---------
    Version 2012-11-20 v1.0 STM casa 4.0 version
    Version 2012-12-17 v1.0 STM casa 4.1 version, phase, real, imag stats
    """
    # define range for "inner" channels
    if innerbuff >= 0.0 and innerbuff < 0.5:
        fcrange = [innerbuff, 1.0-innerbuff]
    else:
        fcrange = [0.1, 0.9]

    # Print extra information here?
    doprintall = False

    # Create the output dictionary
    outDict = {}

    mytb = table()

    mytb.open(calTable)

    # Check that this is a B Jones table
    caltype = mytb.getkeyword('VisCal')
    if caltype=='B Jones':
        print('This is a B Jones table, proceeding')
    else:
        print('This is NOT a B Jones table, aborting')
        return outDict

    antCol = mytb.getcol('ANTENNA1')
    spwCol = mytb.getcol('SPECTRAL_WINDOW_ID')
    fldCol = mytb.getcol('FIELD_ID')

    # these columns are possibly variable in size
    #flagCol = mytb.getcol('FLAG')
    flagVarCol = mytb.getvarcol('FLAG')
    #dataCol = mytb.getcol('CPARAM')
    dataVarCol = mytb.getvarcol('CPARAM')
    mytb.close()

    # get names from ANTENNA table
    mytb.open(calTable+'/ANTENNA')
    antNameCol = mytb.getcol('NAME')
    mytb.close()
    nant = len(antNameCol)

    antDict = {}
    for iant in range(nant):
        antDict[iant] = antNameCol[iant]

    # get names from SPECTRAL_WINDOW table
    mytb.open(calTable+'/SPECTRAL_WINDOW')
    spwNameCol = mytb.getcol('NAME')
    mytb.close()
    nspw = len(spwNameCol)

    # get baseband list
    rxbands = []
    rxBasebandDict = {}
    spwDict = {}
    for ispw in range(nspw):
        try:
            (rx,bb,sb) = spwNameCol[ispw].split('#')
        except:
            rx = 'Unknown'
            bb = 'Unknown'
            sb = ispw
        spwDict[ispw] = {'RX':rx, 'Baseband':bb, 'Subband':sb}
        if rxbands.count(rx)<1:
            rxbands.append(rx)
        if rx in rxBasebandDict:
            if bb in rxBasebandDict[rx]:
                rxBasebandDict[rx][bb].append(ispw)
            else:
                rxBasebandDict[rx][bb] = [ispw]
        else:
            rxBasebandDict[rx] = {}
            rxBasebandDict[rx][bb] = [ispw]

    print('Found '+str(len(rxbands))+' Rx bands')
    for rx in rxBasebandDict.keys():
        bblist = rxBasebandDict[rx].keys()
        print('Rx band '+str(rx)+' has basebands: '+str(bblist))

    # Initialize a list to hold the results
    # Get shape of FLAG
    #(np,nc,ni) = flagCol.shape
    # Get shape of CPARAM
    #(np,nc,ni) = dataCol.shape
    rowlist = dataVarCol.keys()
    nrows = len(rowlist)

    # Populate output dictionary structure
    outDict['antspw'] = {}
    outDict['antband'] = {}

    # Our fields will be: running 'n','mean','min','max' for 'amp'
    # Note - running mean(n+1) = ( n*mean(n) + x(n+1) )/(n+1) = mean(n) + (x(n+1)-mean(n))/(n+1)

    # Ok now go through for each row and possibly channel
    ntotal = 0
    ninner = 0
    nflagged = 0
    ngood = 0
    ninnergood = 0
    for rrow in rowlist:
        rown = rrow.strip('r')
        idx = int(rown)-1
        antIdx = antCol[idx]
        spwIdx = spwCol[idx]
        #
        dataArr = dataVarCol[rrow]
        flagArr = flagVarCol[rrow]
        # Get the shape of this data row
        (np,nc,ni) = dataArr.shape
        # ni should be 1 for this
        iid = 0

        # receiver and baseband and subband
        rx = spwDict[spwIdx]['RX']
        bb = spwDict[spwIdx]['Baseband']
        sb = spwDict[spwIdx]['Subband']

        # Set up dictionaries if needed
        parts = ['all','inner']
        quants = ['amp','phase','real','imag']
        vals = ['min','max','mean','var']
        if antIdx in outDict['antspw']:
            if spwIdx not in outDict['antspw'][antIdx]:
                outDict['antspw'][antIdx][spwIdx] = {}
                for poln in range(np):
                    outDict['antspw'][antIdx][spwIdx][poln] = {}
                    for part in parts:
                        outDict['antspw'][antIdx][spwIdx][poln][part] = {}
                        outDict['antspw'][antIdx][spwIdx][poln][part]['total'] = 0
                        outDict['antspw'][antIdx][spwIdx][poln][part]['number'] = 0
                        for quan in quants:
                            outDict['antspw'][antIdx][spwIdx][poln][part][quan] = {}
                            for val in vals:
                                outDict['antspw'][antIdx][spwIdx][poln][part][quan][val] = 0.0
            if rx in outDict['antband'][antIdx]:
                if bb not in outDict['antband'][antIdx][rx]:
                    outDict['antband'][antIdx][rx][bb] = {}
                    for part in parts:
                        outDict['antband'][antIdx][rx][bb][part] = {}
                        outDict['antband'][antIdx][rx][bb][part]['total'] = 0
                        outDict['antband'][antIdx][rx][bb][part]['number'] = 0
                        for quan in quants:
                            outDict['antband'][antIdx][rx][bb][part][quan] = {}
                            for val in vals:
                                outDict['antband'][antIdx][rx][bb][part][quan][val] = 0.0
            else:
                outDict['antband'][antIdx][rx] = {}
                outDict['antband'][antIdx][rx][bb] = {}
                for part in parts:
                    outDict['antband'][antIdx][rx][bb][part] = {}
                    outDict['antband'][antIdx][rx][bb][part]['total'] = 0
                    outDict['antband'][antIdx][rx][bb][part]['number'] = 0
                    for quan in quants:
                        outDict['antband'][antIdx][rx][bb][part][quan] = {}
                        for val in vals:
                            outDict['antband'][antIdx][rx][bb][part][quan][val] = 0.0

        else:
            outDict['antspw'][antIdx] = {}
            outDict['antspw'][antIdx][spwIdx] = {}
            for poln in range(np):
                outDict['antspw'][antIdx][spwIdx][poln] = {}
                for part in parts:
                    outDict['antspw'][antIdx][spwIdx][poln][part] = {}
                    outDict['antspw'][antIdx][spwIdx][poln][part]['total'] = 0
                    outDict['antspw'][antIdx][spwIdx][poln][part]['number'] = 0
                    for quan in quants:
                        outDict['antspw'][antIdx][spwIdx][poln][part][quan] = {}
                        for val in vals:
                            outDict['antspw'][antIdx][spwIdx][poln][part][quan][val] = 0.0

            outDict['antband'][antIdx] = {}
            outDict['antband'][antIdx][rx] = {}
            outDict['antband'][antIdx][rx][bb] = {}
            for part in parts:
                outDict['antband'][antIdx][rx][bb][part] = {}
                outDict['antband'][antIdx][rx][bb][part]['total'] = 0
                outDict['antband'][antIdx][rx][bb][part]['number'] = 0
                for quan in quants:
                    outDict['antband'][antIdx][rx][bb][part][quan] = {}
                    for val in vals:
                        outDict['antband'][antIdx][rx][bb][part][quan][val] = 0.0

        #
        # Sum up the in-row (per pol per chan) flags for this row
        nptotal = 0
        npflagged = 0
        for poln in range(np):
            ntotal += 1
            nptotal += 1
            ncflagged = 0
            ncgood = 0
            ncinnergood = 0
            for chan in range(nc):
                outDict['antspw'][antIdx][spwIdx][poln]['all']['total'] += 1
                outDict['antband'][antIdx][rx][bb]['all']['total'] += 1
                #
                fc = 1
                if nc>0:
                    fc = float(chan)/float(nc)
                if fc>=fcrange[0] and fc<fcrange[1]:
                    outDict['antspw'][antIdx][spwIdx][poln]['inner']['total'] += 1
                    outDict['antband'][antIdx][rx][bb]['inner']['total'] += 1
                #
                if flagArr[poln][chan][iid]:
                    # a flagged data point
                    ncflagged += 1
                else:
                    cx = dataArr[poln][chan][iid]
                    # get quantities from complex data
                    ampx = numpy.absolute(cx)
                    phasx = numpy.angle(cx,deg=True)
                    realx = numpy.real(cx)
                    imagx = numpy.imag(cx)
                    #
                    # put in dictionary
                    cdict = {}
                    cdict['amp'] = ampx
                    cdict['phase'] = phasx
                    cdict['real'] = realx
                    cdict['imag'] = imagx
                    # an unflagged data point
                    ncgood += 1
                    # Data stats
                    # By antspw per poln
                    nx = outDict['antspw'][antIdx][spwIdx][poln]['all']['number']
                    if nx==0:
                        outDict['antspw'][antIdx][spwIdx][poln]['all']['number'] = 1
                        for quan in quants:
                            for val in vals:
                                outDict['antspw'][antIdx][spwIdx][poln]['all'][quan][val] = cdict[quan]
                    else:
                        for quan in quants:
                            vx = cdict[quan]
                            if vx>outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['max']:
                                outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['max'] = vx
                            if vx<outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['min']:
                                outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['min'] = vx
                            # Running mean(n+1) = mean(n) + (x(n+1)-mean(n))/(n+1)
                            meanx = outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['mean']
                            runx = meanx + (vx - meanx)/float(nx+1)
                            outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['mean'] = runx
                            # Running var(n+1) = {n*var(n)+[x(n+1)-mean(n)][x(n+1)-mean(n+1)]}/(n+1)
                            varx = outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['var']
                            qx = nx*varx + (vx-meanx)*(vx-runx)
                            outDict['antspw'][antIdx][spwIdx][poln]['all'][quan]['var'] = qx/float(nx+1)
                    outDict['antspw'][antIdx][spwIdx][poln]['all']['number'] += 1
                    # Now the rx-band stats
                    ny = outDict['antband'][antIdx][rx][bb]['all']['number']
                    if ny==0:
                        outDict['antband'][antIdx][rx][bb]['all']['number'] = 1
                        for quan in quants:
                            for val in vals:
                                outDict['antband'][antIdx][rx][bb]['all'][quan][val] = cdict[quan]
                    else:
                        for quan in quants:
                            vy = cdict[quan]
                            if vy>outDict['antband'][antIdx][rx][bb]['all'][quan]['max']:
                                outDict['antband'][antIdx][rx][bb]['all'][quan]['max'] = vy
                            if vy<outDict['antband'][antIdx][rx][bb]['all'][quan]['min']:
                                outDict['antband'][antIdx][rx][bb]['all'][quan]['min'] = vy
                            # Running mean(n+1) = mean(n) + (x(n+1)-mean(n))/(n+1)
                            meany = outDict['antband'][antIdx][rx][bb]['all'][quan]['mean']
                            runy = meany + (vy - meany)/float(ny+1)
                            outDict['antband'][antIdx][rx][bb]['all'][quan]['mean'] = runy
                            # Running var(n+1) = {n*var(n)+[x(n+1)-mean(n)][x(n+1)-mean(n+1)]}/(n+1)
                            vary = outDict['antband'][antIdx][rx][bb]['all'][quan]['var']
                            qy = ny*vary + (vy-meany)*(vy-runy)
                            outDict['antband'][antIdx][rx][bb]['all'][quan]['var'] = qy/float(ny+1)
                        outDict['antband'][antIdx][rx][bb]['all']['number'] += 1
                    #
                    if fc>=fcrange[0] and fc<fcrange[1]:
                        # this chan lies in the "inner" part of the spw
                        ncinnergood += 1
                        # Data stats
                        # By antspw per poln
                        nx = outDict['antspw'][antIdx][spwIdx][poln]['inner']['number']
                        if nx==0:
                            outDict['antspw'][antIdx][spwIdx][poln]['inner']['number'] = 1
                            for quan in quants:
                                for val in vals:
                                    outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan][val] = cdict[quan]
                        else:
                            for quan in quants:
                                vx = cdict[quan]
                                if vx>outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['max']:
                                    outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['max'] = vx
                                if vx<outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['min']:
                                    outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['min'] = vx
                                # Running mean(n+1) = mean(n) + (x(n+1)-mean(n))/(n+1)
                                meanx = outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['mean']
                                runx = meanx + (vx - meanx)/float(nx+1)
                                outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['mean'] = runx
                                # Running var(n+1) = {n*var(n)+[x(n+1)-mean(n)][x(n+1)-mean(n+1)]}/(n+1)
                                varx = outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['var']
                                qx = nx*varx + (vx-meanx)*(vx-runx)
                                outDict['antspw'][antIdx][spwIdx][poln]['inner'][quan]['var'] = qx/float(nx+1)
                                outDict['antspw'][antIdx][spwIdx][poln]['inner']['number'] += 1
                        # Now the rx-band stats
                        ny = outDict['antband'][antIdx][rx][bb]['inner']['number']
                        if ny==0:
                            outDict['antband'][antIdx][rx][bb]['inner']['number'] = 1
                            for quan in quants:
                                for val in vals:
                                    outDict['antband'][antIdx][rx][bb]['inner'][quan][val] = cdict[quan]
                        else:
                            for quan in quants:
                                vy = cdict[quan]
                                if vy>outDict['antband'][antIdx][rx][bb]['inner'][quan]['max']:
                                    outDict['antband'][antIdx][rx][bb]['inner'][quan]['max'] = vy
                                if vy<outDict['antband'][antIdx][rx][bb]['inner'][quan]['min']:
                                    outDict['antband'][antIdx][rx][bb]['inner'][quan]['min'] = vy
                                # Running mean(n+1) = mean(n) + (x(n+1)-mean(n))/(n+1)
                                meany = outDict['antband'][antIdx][rx][bb]['inner'][quan]['mean']
                                runy = meany + (vy - meany)/float(ny+1)
                                outDict['antband'][antIdx][rx][bb]['inner'][quan]['mean'] = runy
                                # Running var(n+1) = {n*var(n)+[x(n+1)-mean(n)][x(n+1)-mean(n+1)]}/(n+1)
                                vary = outDict['antband'][antIdx][rx][bb]['inner'][quan]['var']
                                qy = ny*vary + (vy-meany)*(vy-runy)
                                outDict['antband'][antIdx][rx][bb]['inner'][quan]['var'] = qy/float(ny+1)
                            outDict['antband'][antIdx][rx][bb]['inner']['number'] += 1


            npflagged = float(ncflagged)/float(nc)
            nflagged += float(ncflagged)/float(nc)
            ngood += ncgood
            ninnergood += ncinnergood

    # Assemble rest of dictionary
    outDict['antDict'] = antDict
    outDict['spwDict'] = spwDict
    outDict['rxBasebandDict'] = rxBasebandDict

    # Print summary
    print('Within all channels:')
    print('Found '+str(ntotal)+' total solutions with '+str(ngood)+' good (unflagged)')
    print('Within inner '+str(fcrange[1]-fcrange[0])+' of channels:')
    print('Found '+str(ninner)+' total solutions with '+str(ninnergood)+' good (unflagged)')
    print('')
    print('        AntID      AntName      Rx-band      Baseband    min/max(all)  min/max(inner) ALERT?')
    #
    # Print more?
    if doprintall:
        for ant in outDict['antband'].keys():
            antName = antDict[ant]
            for rx in outDict['antband'][ant].keys():
                for bb in outDict['antband'][ant][rx].keys():
                    xmin = outDict['antband'][ant][rx][bb]['all']['amp']['min']
                    xmax = outDict['antband'][ant][rx][bb]['all']['amp']['max']
                    ymin = outDict['antband'][ant][rx][bb]['inner']['amp']['min']
                    ymax = outDict['antband'][ant][rx][bb]['inner']['amp']['max']
                    if xmax != 0.0:
                        xrat = xmin / xmax
                    else:
                        xrat = -1
                    if ymax != 0.0:
                        yrat = ymin / ymax
                    else:
                        yrat = -1
                    #
                    if yrat < 0.05:
                        print(' %12s %12s %12s %12s  %12.4f  %12.4f *** ' % (ant,antName,rx,bb,xrat,yrat))
                    elif yrat < 0.1:
                        print(' %12s %12s %12s %12s  %12.4f  %12.4f ** ' % (ant,antName,rx,bb,xrat,yrat))
                    elif yrat < 0.2:
                        print(' %12s %12s %12s %12s  %12.4f  %12.4f * ' % (ant,antName,rx,bb,xrat,yrat))
                    else:
                        print(' %12s %12s %12s %12s  %12.4f  %12.4f ' % (ant,antName,rx,bb,xrat,yrat))
    return outDict


