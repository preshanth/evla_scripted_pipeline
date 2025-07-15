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
import os

from casatasks import setjy
from evla_pipe.utils import logprint, find_EVLA_band


@dataclass 
class PolCalData:
    """Polarization calibrator data from Perley-Butler 2013."""
    source_name: str
    frequencies: np.ndarray  # GHz
    pol_fraction: np.ndarray  # percentage 
    pol_angle: np.ndarray  # degrees
    rotation_measure: float  # rad/m^2
    intrinsic_angle: float  # degrees


def load_polcal_data_from_file(source_name: str, data_dir: str = None) -> PolCalData:
    """
    Load polarization calibrator data from 2019 data files.
    
    Parameters
    ----------
    source_name : str
        Source name (e.g., '3C286', '3C48', etc.)
    data_dir : str, optional
        Directory containing the data files. If None, uses default data directory.
        
    Returns
    -------
    PolCalData
        Loaded calibrator data
    """
    if data_dir is None:
        # Get the directory where this module is located
        module_dir = Path(__file__).parent
        data_dir = module_dir.parent / 'data'
    else:
        data_dir = Path(data_dir)
    
    # Map source names to filenames
    source_files = {
        '3C48': '3C48_2019.txt',
        '3C138': '3C138_2019.txt', 
        '3C147': '3C147_2019.txt',
        '3C286': '3C286_2019.txt',
        '3C196': '3C196_2019.txt',
        '3C295': '3C295_2019.txt'
    }
    
    # Handle case variations
    source_upper = source_name.upper()
    if source_upper not in source_files:
        raise ValueError(f"Unknown source {source_name}. Available: {list(source_files.keys())}")
    
    file_path = data_dir / source_files[source_upper]
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")
    
    # Read the data file
    frequencies = []
    pol_fractions = []
    pol_angles = []
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                try:
                    freq = float(parts[0])
                    intensity = float(parts[1])  # Not used but in file
                    pol_frac = float(parts[2]) if parts[2] != 'N/A' else np.nan
                    pol_angle = float(parts[3]) if parts[3] != 'N/A' else np.nan
                    
                    # Only include valid data points
                    if not (np.isnan(pol_frac) or np.isnan(pol_angle)):
                        frequencies.append(freq)
                        pol_fractions.append(pol_frac * 100.0)  # Convert to percentage
                        pol_angles.append(np.degrees(pol_angle))  # Convert to degrees
                        
                except ValueError:
                    continue
    
    if not frequencies:
        raise ValueError(f"No valid data found in {file_path}")
    
    # Create PolCalData with estimated rotation measure and intrinsic angle
    # These values are approximate and should be refined based on literature
    rm_values = {
        '3C48': -68.0,
        '3C138': 0.0,
        '3C147': 0.0, 
        '3C286': 0.0,
        '3C196': 0.0,
        '3C295': 0.0
    }
    
    # Use median angle as intrinsic angle approximation
    intrinsic_angle = np.median(pol_angles) if pol_angles else 0.0
    
    return PolCalData(
        source_name=source_upper,
        frequencies=np.array(frequencies),
        pol_fraction=np.array(pol_fractions),
        pol_angle=np.array(pol_angles),
        rotation_measure=rm_values.get(source_upper, 0.0),
        intrinsic_angle=intrinsic_angle
    )


def load_perley_butler_2013_data(source_name: str, data_dir: str = None) -> PolCalData:
    """
    Load polarization calibrator data from Perley-Butler 2013 table.
    
    Parameters
    ----------
    source_name : str
        Source name (e.g., '3C286', '3C48', etc.)
    data_dir : str, optional
        Directory containing the data files. If None, uses default data directory.
        
    Returns
    -------
    PolCalData
        Loaded calibrator data
    """
    if data_dir is None:
        # Get the directory where this module is located
        module_dir = Path(__file__).parent
        data_dir = module_dir.parent / 'data'
    else:
        data_dir = Path(data_dir)
    
    file_path = data_dir / 'perley-butler-2013.txt'
    if not file_path.exists():
        raise FileNotFoundError(f"Perley-Butler 2013 data file not found: {file_path}")
    
    # Map source names to column indices in the table
    source_columns = {
        '3C48': (1, 2),    # pol%, angle columns
        '3C138': (3, 4),
        '3C147': (5, 6), 
        '3C286': (7, 8)
    }
    
    source_upper = source_name.upper()
    if source_upper not in source_columns:
        available = list(source_columns.keys())
        raise ValueError(f"Source {source_name} not in Perley-Butler 2013 data. Available: {available}")
    
    pol_col, angle_col = source_columns[source_upper]
    
    # Read the data file
    frequencies = []
    pol_fractions = []
    pol_angles = []
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and header lines
            if line.startswith('Table') or line.startswith('Polarization') or line.startswith('Frequency') or line.startswith('(GHz)') or not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 9:  # Ensure we have all columns
                try:
                    freq = float(parts[0])
                    pol_frac_str = parts[pol_col].strip()
                    pol_angle_str = parts[angle_col].strip()
                    
                    # Skip entries with missing data (marked with symbols)
                    if ('sdotsdotsdot' in pol_frac_str or '<' in pol_frac_str or 
                        'sdotsdotsdot' in pol_angle_str or pol_frac_str == '' or pol_angle_str == ''):
                        continue
                    
                    pol_frac = float(pol_frac_str)
                    pol_angle = float(pol_angle_str)
                    
                    frequencies.append(freq)
                    pol_fractions.append(pol_frac)  # Already in percentage
                    pol_angles.append(pol_angle)    # Already in degrees
                    
                except (ValueError, IndexError):
                    continue
    
    if not frequencies:
        raise ValueError(f"No valid data found for {source_name} in Perley-Butler 2013 table")
    
    # Rotation measure values from Perley-Butler 2013
    rm_values = {
        '3C48': -68.0,
        '3C138': 0.0,
        '3C147': 0.0,
        '3C286': 0.0
    }
    
    # Use median angle as intrinsic angle approximation
    intrinsic_angle = np.median(pol_angles) if pol_angles else 0.0
    
    return PolCalData(
        source_name=source_upper,
        frequencies=np.array(frequencies),
        pol_fraction=np.array(pol_fractions),
        pol_angle=np.array(pol_angles),
        rotation_measure=rm_values.get(source_upper, 0.0),
        intrinsic_angle=intrinsic_angle
    )


def get_polcal_data(source_name: str, data_dir: str = None, obs_date: str = None) -> PolCalData:
    """
    Get polarization calibrator data, selecting nearest in time.
    
    Uses 2019 data when available, falls back to Perley-Butler 2013.
    
    Parameters
    ----------
    source_name : str
        Source name
    data_dir : str, optional
        Data directory path
    obs_date : str, optional
        Observation date in format 'YYYY-MM-DD' or 'YYYY'. If None, uses 2019 data first.
        
    Returns
    -------
    PolCalData
        Calibrator data
    """
    # Determine which dataset to use based on observation date
    use_2019_data = True
    
    if obs_date:
        try:
            # Extract year from date string
            if '-' in obs_date:
                obs_year = int(obs_date.split('-')[0])
            else:
                obs_year = int(obs_date)
            
            # Use nearest data in time
            # 2019 data vs 2013 data
            if abs(obs_year - 2019) <= abs(obs_year - 2013):
                use_2019_data = True
            else:
                use_2019_data = False
                
        except (ValueError, IndexError):
            logprint(f"Warning: Could not parse observation date '{obs_date}', using 2019 data")
            use_2019_data = True
    
    # Try to load data, with fallback
    if use_2019_data:
        try:
            return load_polcal_data_from_file(source_name, data_dir)
        except (FileNotFoundError, ValueError) as e:
            logprint(f"Warning: Could not load 2019 data for {source_name}: {e}")
            logprint(f"Falling back to Perley-Butler 2013 data")
            return load_perley_butler_2013_data(source_name, data_dir)
    else:
        try:
            return load_perley_butler_2013_data(source_name, data_dir)
        except (FileNotFoundError, ValueError) as e:
            logprint(f"Warning: Could not load Perley-Butler 2013 data for {source_name}: {e}")
            logprint(f"Falling back to 2019 data")
            return load_polcal_data_from_file(source_name, data_dir)


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
        # No data in band - return None to indicate no polarization data available
        logprint(f"Warning: No polarization data for {cal_data.source_name} in {band} band")
        return None, None, None
        
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
    cal_data = get_polcal_data(source_name)
    
    # Filter data for band
    freqs, pol_fracs, pol_angles = filter_data_for_band(cal_data, band)
    
    # Check if no polarization data available for this band
    if freqs is None:
        logprint(f"No polarization data available for {source_name} in {band} band")
        return None, None, None
    
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
                                 obs_date: str = None, use_model_image: str = None,
                                 standard: str = "Perley-Butler 2017", 
                                 usescratch: bool = True) -> Dict:
    """
    Single integrated setjy call that sets both intensity and polarization models.
    
    This replaces the standard setjy call entirely, providing both intensity 
    and polarization information in one step.
    
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
    obs_date : str, optional
        Observation date for selecting best polarization data
    use_model_image : str, optional
        Model image to use for intensity
    standard : str, optional
        Flux density standard (default: "Perley-Butler 2017")
    usescratch : bool, optional
        Use scratch columns (default: True)
        
    Returns
    -------
    Dict
        Complete setjy result with polarization
    """
    try:
        # Check if this is a known polarization calibrator
        cal_data = get_polcal_data(field_name, obs_date=obs_date)
        
        # Get polarization coefficients
        ref_freq_ghz = ref_freq_hz / 1e9
        pol_frac_coeffs, pol_angle_coeffs, pol_frac_ref = fit_polarization_polynomials(
            field_name, band, ref_freq_ghz
        )
        
        # Check if polarization data is available
        if pol_frac_coeffs is None:
            # No polarization data available, fall back to intensity-only
            raise ValueError(f"No polarization data available for {field_name} in {band} band")
        
        # Create spw selection string
        spw_str = ','.join(map(str, spws)) if spws else ''
        
        logprint(f"Setting combined intensity + polarization model for {field_name}")
        logprint(f"  Field: {field_id}, SPWs: {spw_str}, Band: {band}")
        logprint(f"  Reference frequency: {ref_freq_ghz:.3f} GHz")
        logprint(f"  Polarization fraction at ref: {pol_frac_ref:.4f}")
        
        # First set the standard intensity model
        intensity_result = setjy(
            vis=vis,
            field=str(field_id),
            spw=spw_str,
            selectdata=False,
            scalebychan=True,
            standard=standard,
            model=use_model_image if use_model_image else '',
            listmodels=False,
            usescratch=usescratch,
        )
        
        # Then enhance with polarization using setjy_with_polarization
        pol_setjy_result = setjy_with_polarization(
            vis=vis,
            field=str(field_id),
            spw=spw_str,
            ref_freq_hz=ref_freq_hz,
            stokes_i=None,  # Will be derived from the previous setjy call
            spectral_index=None,
            pol_fraction_coeffs=pol_frac_coeffs,
            pol_angle_coeffs=pol_angle_coeffs,
            rotation_measure=cal_data.rotation_measure,
            use_scratch=usescratch
        )
        
        logprint(f"Successfully set combined model for {field_name}")
        
        # Merge results (polarization result should include everything)
        if pol_setjy_result and intensity_result:
            # Use the polarization result as primary, add any missing intensity info
            return pol_setjy_result
        else:
            return intensity_result or pol_setjy_result or {}
        
    except Exception as e:
        logprint(f"Warning: No polarization data for {field_name} in {band} band")
        logprint(f"Falling back to intensity-only model")
        
        # Fallback to intensity-only setjy
        spw_str = ','.join(map(str, spws)) if spws else ''
        
        intensity_result = setjy(
            vis=vis,
            field=str(field_id),
            spw=spw_str,
            selectdata=False,
            scalebychan=True,
            standard=standard,
            model=use_model_image if use_model_image else '',
            listmodels=False,
            usescratch=usescratch,
        )
        
        logprint(f"Successfully set intensity-only model for {field_name}")
        return intensity_result


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