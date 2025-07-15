"""
EVLA Pipeline Polarization Calibration Module
============================================

A modular, pythonic interface for polarization calibration in the EVLA pipeline.
This module provides classes and functions that can be imported and used flexibly
in different contexts - from interactive sessions to automated pipelines.

Key Features:
- Object-oriented design with clear separation of concerns
- Msmetadata integration for efficient data queries
- Dataclass-based configuration
- Context manager support for resource management
- Importable functions for specific polarization tasks

Example Usage:
    Basic usage with context manager:
    >>> from evla_pipe.polarization import PolarizationCalibrator
    >>> with PolarizationCalibrator('my_data.ms') as polcal:
    ...     calibrators = polcal.find_polarization_calibrators()
    ...     polcal.set_standard_models(calibrators)
    ...     kcross_table = polcal.solve_kcross(calibrators['angle'])
    
    Direct function usage:
    >>> from evla_pipe.polarization import find_pol_calibrators, solve_pol_leakage
    >>> calibrators = find_pol_calibrators('my_data.ms')
    >>> dterms = solve_pol_leakage('my_data.ms', calibrators)
"""

import numpy as np
import warnings
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union, Any
from pathlib import Path

from casatasks import setjy, gaincal, polcal, applycal
from casatools import msmetadata

from evla_pipe.utils import runtiming, logprint, find_standards, find_EVLA_band, RefAntHeuristics


@dataclass
class PolCalibrator:
    """Data class representing a polarization calibrator source."""
    name: str
    field_id: int
    scans: List[int] = field(default_factory=list)
    category: str = ""  # 'A' for angle, 'C' for leakage  
    band: str = ""
    spws: List[int] = field(default_factory=list)
    flux_model: Optional[Dict[str, Any]] = None
    pol_model: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate calibrator data after initialization."""
        if self.category not in ['A', 'C', '']:
            raise ValueError("Category must be 'A' (angle) or 'C' (leakage)")


@dataclass  
class PolConfig:
    """Configuration parameters for polarization calibration."""
    # Standard calibrator lists
    angle_calibrators: List[str] = field(default_factory=lambda: [
        'J1331+3030', '3c286', '3C286', 'J0521+1638', '3c138', '3C138', 
        'J0137+3309', '0137+331=3C48', '3c48', '3C48'
    ])
    
    leakage_calibrators: List[str] = field(default_factory=lambda: [
        'J0542+4951', '3c147', '3C147', 'J1407+2827', 'OQ208', 
        'Oq208', 'oq208', 'J0259+0747'
    ])
    
    # Calibration parameters
    reference_antenna: str = ""
    solve_kcross: bool = True
    solve_leakage: bool = True
    solve_angle: bool = True
    pol_mode: str = 'auto'  # 'auto', 'linear', 'circular'
    
    # Solution parameters
    solint: str = 'inf'
    combine: str = 'scan'
    minsnr: float = 3.0
    minblperant: int = 4


class PolarizationCalibrator:
    """
    Main class for polarization calibration operations.
    
    Provides a clean, object-oriented interface to polarization calibration
    that can be used interactively or in automated pipelines.
    
    Example:
        >>> with PolarizationCalibrator('data.ms') as polcal:
        ...     cals = polcal.find_polarization_calibrators()
        ...     if cals:
        ...         tables = polcal.calibrate_polarization(cals)
    """
    
    def __init__(self, msname: str, config: Optional[PolConfig] = None):
        """
        Initialize polarization calibrator.
        
        Parameters
        ----------
        msname : str
            Path to measurement set
        config : PolConfig, optional
            Configuration parameters. If None, uses defaults.
        """
        self.msname = Path(msname)
        self.config = config or PolConfig()
        self.msmd = msmetadata()
        self._is_open = False
        
    def __enter__(self):
        """Context manager entry - opens msmetadata."""
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes msmetadata."""
        self.close()
        
    def open(self):
        """Open msmetadata connection."""
        if not self._is_open:
            self.msmd.open(str(self.msname))
            self._is_open = True
            
    def close(self):
        """Close msmetadata connection."""
        if self._is_open:
            self.msmd.close()
            self._is_open = False
            
    def find_polarization_calibrators(self) -> Dict[str, PolCalibrator]:
        """
        Find available polarization calibrators in the measurement set.
        
        Returns
        -------
        Dict[str, PolCalibrator]
            Dictionary with keys 'angle' and 'leakage' containing found calibrators
        """
        if not self._is_open:
            raise RuntimeError("Must open msmetadata first (use context manager)")
            
        field_names = list(self.msmd.fieldnames())
        calibrators = {'angle': None, 'leakage': None}
        
        # Search for angle calibrators (Category A)
        for cal_name in self.config.angle_calibrators:
            if cal_name in field_names:
                field_id = field_names.index(cal_name)
                scans = list(self.msmd.scansforfield(field_id))
                spws = list(self.msmd.spwsforfield(field_id))
                
                if scans and spws:
                    # Determine band
                    ref_freq = self.msmd.reffreq(spws[0])['m0']['value']
                    band = find_EVLA_band(ref_freq)
                    
                    calibrators['angle'] = PolCalibrator(
                        name=cal_name,
                        field_id=field_id,
                        scans=scans,
                        spws=spws,
                        category='A',
                        band=band
                    )
                    break
        
        # Search for leakage calibrators (Category C)  
        for cal_name in self.config.leakage_calibrators:
            if cal_name in field_names:
                field_id = field_names.index(cal_name)
                scans = list(self.msmd.scansforfield(field_id))
                spws = list(self.msmd.spwsforfield(field_id))
                
                if scans and spws:
                    # Determine band
                    ref_freq = self.msmd.reffreq(spws[0])['m0']['value']
                    band = find_EVLA_band(ref_freq)
                    
                    calibrators['leakage'] = PolCalibrator(
                        name=cal_name,
                        field_id=field_id,
                        scans=scans,
                        spws=spws,
                        category='C', 
                        band=band
                    )
                    break
                    
        return calibrators
        
    def set_standard_models(self, calibrators: Dict[str, PolCalibrator]):
        """
        Set standard flux density models for polarization calibrators.
        
        Parameters
        ----------
        calibrators : Dict[str, PolCalibrator]
            Dictionary of calibrators to set models for
        """
        for cal_type, calibrator in calibrators.items():
            if calibrator is None:
                continue
                
            try:
                setjy(
                    vis=str(self.msname),
                    field=str(calibrator.field_id),
                    standard='Perley-Butler 2017',
                    scalebychan=True,
                    usescratch=True
                )
                logprint(f"Set standard model for {calibrator.name} ({cal_type})")
                
            except Exception as e:
                logprint(f"Error setting model for {calibrator.name}: {e}")
                
    def solve_kcross(self, angle_calibrator: PolCalibrator, 
                     gaintables: List[str] = None) -> str:
        """
        Solve for cross-hand delays (Kcross).
        
        Parameters
        ----------
        angle_calibrator : PolCalibrator
            Angle calibrator to use for solving
        gaintables : List[str], optional
            Prior calibration tables to apply
            
        Returns
        -------
        str
            Path to Kcross calibration table
        """
        if angle_calibrator is None:
            raise ValueError("Angle calibrator required for Kcross solving")
            
        kcross_table = f"{self.msname.stem}.Kcross"
        
        # Determine reference antenna
        if self.config.reference_antenna:
            refant = self.config.reference_antenna
        else:
            refant = RefAntHeuristics(
                vis=str(self.msname),
                field=str(angle_calibrator.field_id),
                geometry=True,
                flagging=True
            )
            
        gaincal(
            vis=str(self.msname),
            caltable=kcross_table,
            field=str(angle_calibrator.field_id),
            spw='',
            solint=self.config.solint,
            combine=self.config.combine,
            refant=refant,
            minblperant=self.config.minblperant,
            minsnr=self.config.minsnr,
            gaintype='KCROSS',
            gaintable=gaintables or [],
            parang=True
        )
        
        logprint(f"Solved Kcross: {kcross_table}")
        return kcross_table
        
    def solve_leakage(self, leakage_calibrator: PolCalibrator,
                      gaintables: List[str] = None) -> str:
        """
        Solve for instrumental polarization leakage (D-terms).
        
        Parameters
        ----------
        leakage_calibrator : PolCalibrator
            Leakage calibrator to use for solving
        gaintables : List[str], optional
            Prior calibration tables to apply
            
        Returns
        -------
        str
            Path to D-terms calibration table
        """
        if leakage_calibrator is None:
            raise ValueError("Leakage calibrator required for D-terms solving")
            
        dterms_table = f"{self.msname.stem}.Dleakage"
        
        polcal(
            vis=str(self.msname),
            caltable=dterms_table,
            field=str(leakage_calibrator.field_id),
            spw='',
            solint=self.config.solint,
            combine=self.config.combine,
            minblperant=self.config.minblperant,
            minsnr=self.config.minsnr,
            poltype='Df+QU',
            gaintable=gaintables or [],
            parang=True
        )
        
        logprint(f"Solved D-terms: {dterms_table}")
        return dterms_table
        
    def solve_polarization_angle(self, angle_calibrator: PolCalibrator,
                                 gaintables: List[str] = None) -> str:
        """
        Solve for polarization angle.
        
        Parameters
        ----------
        angle_calibrator : PolCalibrator
            Angle calibrator to use for solving
        gaintables : List[str], optional
            Prior calibration tables to apply
            
        Returns
        -------
        str
            Path to polarization angle calibration table
        """
        if angle_calibrator is None:
            raise ValueError("Angle calibrator required for polarization angle solving")
            
        polangle_table = f"{self.msname.stem}.Xf"
        
        polcal(
            vis=str(self.msname),
            caltable=polangle_table,
            field=str(angle_calibrator.field_id),
            spw='',
            solint=self.config.solint,
            combine=self.config.combine,
            minblperant=self.config.minblperant,
            minsnr=self.config.minsnr,
            poltype='Xf',
            gaintable=gaintables or [],
            parang=True
        )
        
        logprint(f"Solved polarization angle: {polangle_table}")
        return polangle_table
        
    def calibrate_polarization(self, calibrators: Dict[str, PolCalibrator],
                               prior_tables: List[str] = None) -> Dict[str, str]:
        """
        Run complete polarization calibration sequence.
        
        Parameters
        ----------
        calibrators : Dict[str, PolCalibrator]
            Dictionary containing 'angle' and 'leakage' calibrators
        prior_tables : List[str], optional
            Prior calibration tables to apply
            
        Returns
        -------
        Dict[str, str]
            Dictionary of calibration table paths
        """
        if calibrators['angle'] is None:
            raise ValueError("Angle calibrator required for polarization calibration")
        if calibrators['leakage'] is None:
            raise ValueError("Leakage calibrator required for polarization calibration")
            
        cal_tables = {}
        applied_tables = prior_tables or []
        
        # Set standard models
        self.set_standard_models(calibrators)
        
        # Solve Kcross
        if self.config.solve_kcross:
            kcross_table = self.solve_kcross(calibrators['angle'], applied_tables)
            cal_tables['kcross'] = kcross_table
            applied_tables.append(kcross_table)
            
        # Solve D-terms  
        if self.config.solve_leakage:
            dterms_table = self.solve_leakage(calibrators['leakage'], applied_tables)
            cal_tables['leakage'] = dterms_table
            applied_tables.append(dterms_table)
            
        # Solve polarization angle
        if self.config.solve_angle:
            polangle_table = self.solve_polarization_angle(calibrators['angle'], applied_tables)
            cal_tables['angle'] = polangle_table
            
        return cal_tables


# Standalone functions for direct usage without classes
def find_pol_calibrators(msname: str, config: Optional[PolConfig] = None) -> Dict[str, PolCalibrator]:
    """
    Find polarization calibrators in a measurement set.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    config : PolConfig, optional
        Configuration parameters
        
    Returns
    -------
    Dict[str, PolCalibrator]
        Dictionary with 'angle' and 'leakage' calibrators
    """
    with PolarizationCalibrator(msname, config) as polcal:
        return polcal.find_polarization_calibrators()


def set_pol_models(msname: str, calibrators: Dict[str, PolCalibrator]):
    """
    Set standard models for polarization calibrators.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    calibrators : Dict[str, PolCalibrator]
        Dictionary of calibrators
    """
    with PolarizationCalibrator(msname) as polcal:
        polcal.set_standard_models(calibrators)


def solve_pol_kcross(msname: str, angle_calibrator: PolCalibrator,
                     gaintables: List[str] = None, config: Optional[PolConfig] = None) -> str:
    """
    Solve for cross-hand delays.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    angle_calibrator : PolCalibrator
        Angle calibrator
    gaintables : List[str], optional
        Prior calibration tables
    config : PolConfig, optional
        Configuration parameters
        
    Returns
    -------
    str
        Path to Kcross table
    """
    with PolarizationCalibrator(msname, config) as polcal:
        return polcal.solve_kcross(angle_calibrator, gaintables)


def solve_pol_leakage(msname: str, leakage_calibrator: PolCalibrator,
                      gaintables: List[str] = None, config: Optional[PolConfig] = None) -> str:
    """
    Solve for polarization leakage.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    leakage_calibrator : PolCalibrator
        Leakage calibrator
    gaintables : List[str], optional
        Prior calibration tables
    config : PolConfig, optional
        Configuration parameters
        
    Returns
    -------
    str
        Path to D-terms table
    """
    with PolarizationCalibrator(msname, config) as polcal:
        return polcal.solve_leakage(leakage_calibrator, gaintables)


def solve_pol_angle(msname: str, angle_calibrator: PolCalibrator,
                    gaintables: List[str] = None, config: Optional[PolConfig] = None) -> str:
    """
    Solve for polarization angle.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    angle_calibrator : PolCalibrator
        Angle calibrator
    gaintables : List[str], optional
        Prior calibration tables
    config : PolConfig, optional
        Configuration parameters
        
    Returns
    -------
    str
        Path to polarization angle table
    """
    with PolarizationCalibrator(msname, config) as polcal:
        return polcal.solve_polarization_angle(angle_calibrator, gaintables)


def calibrate_polarization_full(msname: str, prior_tables: List[str] = None,
                                config: Optional[PolConfig] = None) -> Dict[str, str]:
    """
    Run complete polarization calibration sequence.
    
    This is the main high-level function for polarization calibration.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    prior_tables : List[str], optional
        Prior calibration tables to apply
    config : PolConfig, optional
        Configuration parameters
        
    Returns
    -------
    Dict[str, str]
        Dictionary of calibration table paths
        
    Example
    -------
    >>> from evla_pipe.polarization import calibrate_polarization_full
    >>> tables = calibrate_polarization_full('my_data.ms')
    >>> print(f"Created tables: {list(tables.keys())}")
    """
    with PolarizationCalibrator(msname, config) as polcal:
        calibrators = polcal.find_polarization_calibrators()
        
        if calibrators['angle'] is None or calibrators['leakage'] is None:
            raise ValueError("Both angle and leakage calibrators required")
            
        return polcal.calibrate_polarization(calibrators, prior_tables)


def apply_pol_calibration(msname: str, cal_tables: List[str], target_fields: List[int]):
    """
    Apply polarization calibration to target fields.
    
    Parameters
    ----------
    msname : str
        Path to measurement set
    cal_tables : List[str]
        List of calibration table paths
    target_fields : List[int]
        List of target field IDs
    """
    applycal(
        vis=msname,
        field=','.join(map(str, target_fields)),
        gaintable=cal_tables,
        gainfield=[''] * len(cal_tables),
        interp=['linear'] * len(cal_tables),
        spwmap=[[] for _ in cal_tables],
        calwt=[True] * len(cal_tables),
        parang=True,
        applymode='calflag',
        flagbackup=True
    )
    
    logprint(f"Applied polarization calibration to fields {target_fields}")


# Integration function for pipeline usage
def integrate_polarization_calibration(pipeline_context: Dict) -> Dict:
    """
    Integrate polarization calibration into the main pipeline context.
    
    This function is called by the main pipeline when polarization
    calibration is enabled.
    
    Parameters
    ----------
    pipeline_context : Dict
        Main pipeline context dictionary
        
    Returns
    -------
    Dict
        Updated pipeline context with polarization results
    """
    msname = pipeline_context.get('msname')
    do_pol = pipeline_context.get('do_pol', False)
    
    if not do_pol or not msname:
        return pipeline_context
        
    try:
        # Get prior calibration tables from context
        prior_tables = []
        for table_key in ['delay_cal_table', 'bpass_cal_table', 'phase_cal_table']:
            if table_key in pipeline_context:
                prior_tables.append(pipeline_context[table_key])
        
        # Run polarization calibration
        pol_tables = calibrate_polarization_full(msname, prior_tables)
        
        # Update context with results
        pipeline_context['polarization_cal_tables'] = pol_tables
        pipeline_context['polarization_success'] = True
        
        logprint("Polarization calibration completed successfully")
        
    except Exception as e:
        logprint(f"Polarization calibration failed: {e}")
        pipeline_context['polarization_success'] = False
        pipeline_context['polarization_error'] = str(e)
        
    return pipeline_context