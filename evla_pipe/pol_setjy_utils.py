"""
Polarization setjy utilities for EVLA pipeline.

This module provides modern, simplified polarization model fitting and setjy calls
that integrate with the main pipeline setjy operations.

Key improvements over legacy code:
- Uses numpy.polyfit instead of scipy.optimize.curve_fit
- Handles CASA coefficient ordering correctly
- Modular functions that can be integrated into main setjy calls
- Uses dataclasses for polarization calibrator data
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from casatasks import setjy
from .utils import logprint, find_EVLA_band


@dataclass 
class PolCalData:
    """Polarization calibrator data from Perley-Butler 2013."""
    source_name: str
    frequencies: np.ndarray  # GHz
    pol_fraction: np.ndarray  # percentage 
    pol_angle: np.ndarray  # degrees
    rotation_measure: float  # rad/m^2
    intrinsic_angle: float  # degrees


# Perley-Butler 2013 polarization data
# Table 3: Polarization Properties of 3C48, 3C138, 3C147, and 3C286
POL_CAL_DATABASE = {
    '3C48': PolCalData(
        source_name='3C48',
        frequencies=np.array([1.050, 1.450, 1.640, 1.950, 2.450, 2.950, 3.250, 3.750,
                             4.500, 5.000, 6.500, 7.250, 8.100, 8.800, 12.80, 13.70,
                             14.60, 15.50, 18.10, 19.00, 22.40, 23.30, 36.50, 43.50]),
        pol_fraction=np.array([0.3, 0.5, 0.7, 0.9, 1.4, 2.0, 2.5, 3.2, 3.8, 4.2,
                              5.2, 5.2, 5.3, 5.4, 6.0, 6.1, 6.4, 6.4, 6.9, 7.1,
                              7.7, 7.8, 7.4, 7.5]),
        pol_angle=np.array([120, 120, 120, 120, 120, 120, 120, 120, 120, 120,
                           120, 120, 120, 120, 120, 120, 120, 120, 120, 120,
                           120, 120, 120, 120]),  # Approximate values
        rotation_measure=-68.0,  # rad/m^2
        intrinsic_angle=122.0  # degrees
    ),
    
    '3C138': PolCalData(
        source_name='3C138', 
        frequencies=np.array([1.050, 1.450, 1.640, 1.950, 2.450, 2.950, 3.250,
                             4.500, 5.000, 6.500, 7.250, 8.100, 8.800, 12.80,
                             13.70, 14.60, 15.50, 18.10, 19.00, 22.40, 23.30,
                             36.50, 43.50]),  # Skip 3.750 GHz (null value)
        pol_fraction=np.array([5.6, 7.5, 8.4, 9.0, 10.4, 10.7, 10.0, 10.0, 10.4,
                              9.8, 10.0, 10.4, 10.1, 8.4, 7.9, 7.7, 7.4, 6.7,
                              6.5, 6.7, 6.6, 6.6, 6.5]),
        pol_angle=np.array([-10, -10, -10, -10, -10, -10, -10, -10, -10, -10,
                           -10, -10, -10, -10, -10, -10, -10, -10, -10, -10,
                           -10, -10, -10]),  # Approximate values
        rotation_measure=0.0,
        intrinsic_angle=-10.0
    ),
    
    '3C147': PolCalData(
        source_name='3C147',
        frequencies=np.array([4.500, 5.000, 6.500, 7.250, 8.100, 8.800, 12.80,
                             13.70, 14.60, 15.50, 18.10, 19.00, 22.40, 23.30,
                             36.50, 43.50]),  # Only C-band and higher
        pol_fraction=np.array([0.1, 0.3, 0.3, 0.6, 0.7, 0.8, 2.2, 2.4, 2.7,
                              2.9, 3.4, 3.5, 3.8, 3.8, 4.4, 5.2]),
        pol_angle=np.array([135, 135, 135, 135, 135, 135, 135, 135, 135, 135,
                           135, 135, 135, 135, 135, 135]),  # Approximate values
        rotation_measure=0.0,
        intrinsic_angle=135.0
    ),
    
    '3C286': PolCalData(
        source_name='3C286',
        frequencies=np.array([1.050, 1.450, 1.640, 1.950, 2.450, 2.950, 3.250, 3.750,
                             4.500, 5.000, 6.500, 7.250, 8.100, 8.800, 12.80, 13.70,
                             14.60, 15.50, 18.10, 19.00, 22.40, 23.30, 36.50, 43.50]),
        pol_fraction=np.array([8.6, 9.5, 9.9, 10.1, 10.5, 10.8, 10.9, 11.1, 11.3,
                              11.4, 11.6, 11.7, 11.9, 11.9, 11.9, 11.9, 12.1, 12.2,
                              12.5, 12.5, 12.6, 12.6, 13.1, 13.2]),
        pol_angle=np.array([66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66,
                           66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66]),
        rotation_measure=0.0,
        intrinsic_angle=66.0
    )
}

# Aliases for different naming conventions
POL_CAL_DATABASE['3c48'] = POL_CAL_DATABASE['3C48']
POL_CAL_DATABASE['3c138'] = POL_CAL_DATABASE['3C138'] 
POL_CAL_DATABASE['3c147'] = POL_CAL_DATABASE['3C147']
POL_CAL_DATABASE['3c286'] = POL_CAL_DATABASE['3C286']


def get_band_frequency_range(band: str) -> Tuple[float, float]:
    """
    Get frequency range for VLA bands.
    
    Parameters
    ----------
    band : str
        VLA band ('L', 'S', 'C', 'X', 'Ku', 'K', 'Ka', 'Q')
        
    Returns
    -------
    Tuple[float, float]
        (min_freq, max_freq) in GHz
    """
    band_ranges = {
        'L': (1.0, 2.0),
        'S': (2.0, 4.0), 
        'C': (4.0, 8.0),
        'X': (8.0, 12.0),
        'Ku': (12.0, 18.0),
        'K': (18.0, 26.5),
        'Ka': (26.5, 40.0),
        'Q': (40.0, 50.0)
    }
    return band_ranges.get(band.upper(), (1.0, 50.0))


def filter_data_for_band(cal_data: PolCalData, band: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Filter polarization calibrator data for specific band.
    
    Parameters
    ----------
    cal_data : PolCalData
        Calibrator data
    band : str
        VLA band
        
    Returns
    -------
    Tuple[np.ndarray, np.ndarray, np.ndarray]
        (frequencies, pol_fractions, pol_angles) filtered for band
    """
    min_freq, max_freq = get_band_frequency_range(band)
    
    # Find frequencies in band range
    mask = (cal_data.frequencies >= min_freq) & (cal_data.frequencies <= max_freq)
    
    if not np.any(mask):
        # No data in band, use nearest frequencies
        logprint(f"Warning: No polarization data for {cal_data.source_name} in {band} band")
        return cal_data.frequencies, cal_data.pol_fraction, cal_data.pol_angle
        
    return (cal_data.frequencies[mask], 
            cal_data.pol_fraction[mask], 
            cal_data.pol_angle[mask])


def fit_polarization_polynomials(source_name: str, band: str, ref_freq_ghz: float, 
                                 order: int = 3) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Fit polynomials for polarization fraction and angle using numpy.polyfit.
    
    This is the modern replacement for the legacy scipy.optimize.curve_fit approach.
    
    Parameters
    ----------
    source_name : str
        Source name ('3C48', '3C138', '3C147', '3C286')
    band : str
        VLA band ('L', 'S', 'C', 'X', 'Ku', 'K', 'Ka', 'Q')
    ref_freq_ghz : float
        Reference frequency in GHz
    order : int, optional
        Polynomial order (default: 3)
        
    Returns
    -------
    Tuple[np.ndarray, np.ndarray, float]
        (pol_fraction_coeffs, pol_angle_coeffs, pol_fraction_at_ref)
        
    Notes
    -----
    CASA expects polynomial coefficients in ascending order of powers:
    p(x) = c0 + c1*x + c2*x^2 + c3*x^3
    
    numpy.polyfit returns coefficients in descending order, so we reverse them.
    """
    # Get calibrator data
    if source_name not in POL_CAL_DATABASE:
        raise ValueError(f"Unknown polarization calibrator: {source_name}")
        
    cal_data = POL_CAL_DATABASE[source_name]
    
    # Filter data for band
    freqs, pol_fracs, pol_angles = filter_data_for_band(cal_data, band)
    
    if len(freqs) < order + 1:
        logprint(f"Warning: Only {len(freqs)} points for {source_name} {band}-band, reducing polynomial order")
        order = max(0, len(freqs) - 1)
    
    # Normalize frequency (standard approach for polynomial fitting)
    x_data = (freqs - ref_freq_ghz) / ref_freq_ghz
    
    # Convert percentages to fractions
    y_pol_frac = pol_fracs / 100.0
    
    # Convert angles to radians
    y_pol_angle = pol_angles * np.pi / 180.0
    
    # Fit polynomials using numpy.polyfit (much simpler than scipy.optimize.curve_fit!)
    pol_frac_coeffs_desc = np.polyfit(x_data, y_pol_frac, order)
    pol_angle_coeffs_desc = np.polyfit(x_data, y_pol_angle, order) 
    
    # IMPORTANT: CASA expects coefficients in ASCENDING order of powers
    # numpy.polyfit returns DESCENDING order, so we reverse
    pol_frac_coeffs = pol_frac_coeffs_desc[::-1]
    pol_angle_coeffs = pol_angle_coeffs_desc[::-1]
    
    # Calculate polarization fraction at reference frequency (x=0)
    pol_frac_at_ref = pol_frac_coeffs[0]  # c0 term when x=0
    
    logprint(f"Polarization fit for {source_name} {band}-band:")
    logprint(f"  Reference frequency: {ref_freq_ghz:.3f} GHz")
    logprint(f"  Polarization fraction coefficients: {pol_frac_coeffs}")
    logprint(f"  Polarization angle coefficients: {pol_angle_coeffs}")
    logprint(f"  Polarization fraction at ref freq: {pol_frac_at_ref:.4f}")
    
    return pol_frac_coeffs, pol_angle_coeffs, pol_frac_at_ref


def compute_stokes_qu(pol_fraction: float, pol_angle_rad: float, stokes_i: float) -> Tuple[float, float]:
    """
    Compute Stokes Q and U from polarization fraction and angle.
    
    Parameters
    ----------
    pol_fraction : float
        Linear polarization fraction (0-1)
    pol_angle_rad : float
        Polarization angle in radians
    stokes_i : float
        Stokes I flux density
        
    Returns
    -------
    Tuple[float, float]
        (stokes_q, stokes_u)
    """
    pol_intensity = pol_fraction * stokes_i
    stokes_q = pol_intensity * np.cos(2 * pol_angle_rad)
    stokes_u = pol_intensity * np.sin(2 * pol_angle_rad)
    return stokes_q, stokes_u


def setjy_with_polarization(vis: str, field: str, spw: str = '', 
                           ref_freq_hz: float = None,
                           stokes_i: float = None, spectral_index: List[float] = None,
                           pol_fraction_coeffs: np.ndarray = None,
                           pol_angle_coeffs: np.ndarray = None,
                           rotation_measure: float = 0.0,
                           use_scratch: bool = True) -> Dict:
    """
    Enhanced setjy call that includes polarization parameters.
    
    This function can be integrated into the main pipeline setjy calls.
    
    Parameters
    ----------
    vis : str
        Measurement set path
    field : str
        Field ID or name
    spw : str, optional
        Spectral window selection
    ref_freq_hz : float, optional
        Reference frequency in Hz
    stokes_i : float, optional
        Stokes I flux density at reference frequency
    spectral_index : List[float], optional
        Spectral index coefficients [alpha, beta, ...]
    pol_fraction_coeffs : np.ndarray, optional
        Polarization fraction polynomial coefficients
    pol_angle_coeffs : np.ndarray, optional
        Polarization angle polynomial coefficients  
    rotation_measure : float, optional
        Rotation measure in rad/m^2
    use_scratch : bool, optional
        Use scratch columns
        
    Returns
    -------
    Dict
        setjy return dictionary
    """
    # Start with basic parameters
    setjy_params = {
        'vis': vis,
        'field': field,
        'usescratch': use_scratch
    }
    
    if spw:
        setjy_params['spw'] = spw
        
    # If no polarization info provided, use standard setjy
    if pol_fraction_coeffs is None:
        setjy_params['standard'] = 'Perley-Butler 2017'
        setjy_params['scalebychan'] = True
        logprint(f"Setting standard model for field {field}")
        
    else:
        # Manual mode with polarization
        setjy_params['standard'] = 'manual'
        
        if ref_freq_hz is not None:
            setjy_params['reffreq'] = f"{ref_freq_hz}Hz"
            
        if stokes_i is not None:
            # Calculate Q and U at reference frequency if angle coeffs provided
            if pol_angle_coeffs is not None:
                pol_frac_ref = pol_fraction_coeffs[0]  # c0 term
                pol_angle_ref = pol_angle_coeffs[0]    # c0 term
                stokes_q, stokes_u = compute_stokes_qu(pol_frac_ref, pol_angle_ref, stokes_i)
                setjy_params['fluxdensity'] = [stokes_i, stokes_q, stokes_u, 0.0]
            else:
                setjy_params['fluxdensity'] = [stokes_i, 0.0, 0.0, 0.0]
                
        if spectral_index is not None:
            setjy_params['spix'] = spectral_index
            
        # Add polarization parameters
        setjy_params['polindex'] = pol_fraction_coeffs.tolist()
        
        if pol_angle_coeffs is not None:
            setjy_params['polangle'] = pol_angle_coeffs.tolist()
            
        if rotation_measure != 0.0:
            setjy_params['rotmeas'] = rotation_measure
            
        logprint(f"Setting polarization model for field {field}:")
        logprint(f"  Flux density: {setjy_params.get('fluxdensity', 'N/A')}")
        logprint(f"  Polindex: {pol_fraction_coeffs}")
        if pol_angle_coeffs is not None:
            logprint(f"  Polangle: {pol_angle_coeffs}")
            
    return setjy(**setjy_params)


def integrate_polarization_setjy(vis: str, field_id: int, field_name: str, 
                                 spws: List[int], band: str, ref_freq_hz: float,
                                 standard_setjy_result: Dict = None) -> Dict:
    """
    Integrate polarization setjy into main pipeline setjy calls.
    
    This function should be called immediately after the standard setjy
    for polarization calibrators to add polarization information.
    
    Parameters
    ----------
    vis : str
        Measurement set path
    field_id : int
        Field ID
    field_name : str
        Field name
    spws : List[int]
        Spectral window IDs
    band : str
        VLA band
    ref_freq_hz : float
        Reference frequency in Hz
    standard_setjy_result : Dict, optional
        Result from standard setjy call
        
    Returns
    -------
    Dict
        Updated setjy result with polarization
    """
    # Check if this is a known polarization calibrator
    if field_name not in POL_CAL_DATABASE:
        logprint(f"Field {field_name} is not a standard polarization calibrator")
        return standard_setjy_result or {}
        
    try:
        # Get polarization coefficients
        ref_freq_ghz = ref_freq_hz / 1e9
        pol_frac_coeffs, pol_angle_coeffs, pol_frac_ref = fit_polarization_polynomials(
            field_name, band, ref_freq_ghz
        )
        
        # Get calibrator data for rotation measure
        cal_data = POL_CAL_DATABASE[field_name]
        
        # Extract flux density from standard setjy result if available
        stokes_i = None
        spectral_index = None
        if standard_setjy_result:
            field_key = str(field_id)
            if field_key in standard_setjy_result:
                spw_data = standard_setjy_result[field_key]
                # Use first spw as reference
                first_spw = str(spws[0]) if spws else '0'
                if first_spw in spw_data:
                    flux_data = spw_data[first_spw]
                    if 'fluxd' in flux_data:
                        stokes_i = flux_data['fluxd'][0]  # Stokes I
                        
        # Create spw selection string
        spw_str = ','.join(map(str, spws)) if spws else ''
        
        # Call enhanced setjy with polarization
        pol_setjy_result = setjy_with_polarization(
            vis=vis,
            field=str(field_id),
            spw=spw_str,
            ref_freq_hz=ref_freq_hz,
            stokes_i=stokes_i,
            spectral_index=spectral_index,
            pol_fraction_coeffs=pol_frac_coeffs,
            pol_angle_coeffs=pol_angle_coeffs,
            rotation_measure=cal_data.rotation_measure
        )
        
        logprint(f"Successfully set polarization model for {field_name}")
        return pol_setjy_result
        
    except Exception as e:
        logprint(f"Error setting polarization model for {field_name}: {e}")
        return standard_setjy_result or {}


def example_usage():
    """Example of how to use the improved polarization setjy functions."""
    
    # Example 1: Standalone polarization fitting
    source = '3C286'
    band = 'C'
    ref_freq_ghz = 6.0
    
    pol_frac_coeffs, pol_angle_coeffs, pol_frac_ref = fit_polarization_polynomials(
        source, band, ref_freq_ghz
    )
    
    print(f"Polarization fraction coefficients: {pol_frac_coeffs}")
    print(f"Polarization angle coefficients: {pol_angle_coeffs}")
    print(f"Pol fraction at {ref_freq_ghz} GHz: {pol_frac_ref:.4f}")
    
    # Example 2: Integration with main setjy call
    # This would be called from the main pipeline after standard setjy
    """
    # In main pipeline:
    standard_result = setjy(vis='data.ms', field='3C286', standard='Perley-Butler 2017')
    
    # Then add polarization:
    pol_result = integrate_polarization_setjy(
        vis='data.ms',
        field_id=2, 
        field_name='3C286',
        spws=[0, 1, 2, 3],
        band='C',
        ref_freq_hz=6e9,
        standard_setjy_result=standard_result
    )
    """


if __name__ == "__main__":
    example_usage()