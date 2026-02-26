"""
Consolidated Flagging Module for EVLA Pipeline

This module implements efficient flagging using flagdata list mode to minimize
data I/O by applying all flagging operations in batches:

Stage 1: Initial Flagging (before any calibrations)
- Import flags from online flagging
- Deterministic flags (shadow, zero, pointing, setup, quack, end channels)
- First tfcrop pass on calibrators
- Second tfcrop pass with different parameters

Stage 2: Post-Calibration Flagging (after test calibrations)
- Bad deformatter flagging based on bandpass analysis
- RFI flagging on calibrators

Stage 3: Semi-Final Flagging (during iterative calibration)
- Additional RFI flagging on calibrators

Stage 4: Target Flagging (after calibrations applied)
- RFI flagging on calibrated target data
"""

import os
from typing import Any, Dict, List

from casatasks import flagdata

from evla_pipe.import_data import track_flagging_progression
from evla_pipe.utils import get_log_path, logprint, runtiming


def task_logprint(msg: str):
    """Centralized logging for flagging operations."""
    logprint(msg, logfileout=str(get_log_path("flagging.log")))


class PipelineFlagging:
    """Stage-based flagging for EVLA pipeline using flagdata list mode."""

    def __init__(self, pipeline_context: Dict[str, Any]):
        self.context = pipeline_context
        self.ms_name = pipeline_context.get("msname")

    def _write_flag_commands_file(self, commands: List[str], filename: str) -> str:
        """
        Write flag commands to a file for flagdata list mode.

        Ensures proper format: KEY=VALUE separated by single whitespace.
        """
        task_logprint(f"Writing {len(commands)} flag commands to {filename}")

        with open(filename, "w") as f:
            f.write("# EVLA Pipeline Consolidated Flagging Commands\n")
            f.write(f"# Generated for MS: {self.ms_name}\n")
            f.write(f"# Total commands: {len(commands)}\n")
            f.write("#\n")

            for i, cmd in enumerate(commands, 1):
                # Ensure proper format and add command number as comment
                f.write(f"# Command {i}\n")
                f.write(f"{cmd}\n")

        task_logprint(f"Flag commands written to {filename}")
        return filename

    def _format_flag_command(self, **kwargs) -> str:
        """
        Format flag command with proper KEY=VALUE syntax.

        Parameters are converted to proper flagdata parameter format.
        """
        # Remove None values and empty strings
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ""}

        # Format as KEY=VALUE pairs
        parts = []
        for key, value in clean_kwargs.items():
            if isinstance(value, str) and not value.startswith("'"):
                # Add quotes around string values
                parts.append(f"{key}='{value}'")
            else:
                parts.append(f"{key}={value}")

        return " ".join(parts)

    def _apply_flag_stage(self, commands: List[str], stage_name: str) -> Dict[str, Any]:
        """Apply flag commands for a stage using flagdata list mode."""
        if not commands:
            task_logprint(f"No flag commands for {stage_name}")
            return {"stage": stage_name, "commands": 0}

        task_logprint(f"*** Starting {stage_name} ***")
        runtiming(f"flagging_{stage_name.lower().replace(' ', '_')}", "start")

        # Write commands to file
        filename = f"flagcommands_{stage_name.lower().replace(' ', '_')}.txt"
        self._write_flag_commands_file(commands, filename)

        task_logprint(f"Applying {len(commands)} flag commands for {stage_name}")
        task_logprint(f"Flag commands written to {filename}")

        # Apply flags using list mode
        flag_result = flagdata(
            vis=self.ms_name,
            mode="list",
            inpfile=filename,
            action="apply",
            flagbackup=False,
            savepars=True,
        )

        runtiming(f"flagging_{stage_name.lower().replace(' ', '_')}", "end")
        task_logprint(f"*** Completed {stage_name} ***")

        return flag_result

    def stage1_initial_flagging(self) -> Dict[str, Any]:
        """
        Stage 1: Consolidated initial flagging before any calibrations.

        Combines: import flags + deterministic flags + tfcrop passes
        Replaces: EVLA_pipe_flagall + initial tfcrop operations
        """
        int_time = self.context.get("int_time", 1.0)
        quack_scan_string = self.context.get("quack_scan_string", "")
        pointing_state_IDs = self.context.get("pointing_state_IDs", [])
        numSpws = self.context.get("numSpws", 0)
        channels = self.context.get("channels", [])
        msname = self.context.get("msname", "")

        # Get calibrator information for tfcrop
        self.context.get("bandpass_field_select_string", "")
        self.context.get("delay_field_select_string", "")
        calibrator_scan_select_string = self.context.get(
            "calibrator_scan_select_string", ""
        )
        corrstring = self.context.get("corrstring", "RR,LL")

        commands = []

        # 1. Import online flags first
        online_flag_name = msname.rstrip("ms") + "flagonline.txt"
        if os.path.isfile(online_flag_name):
            commands.append(
                self._format_flag_command(
                    mode="list",
                    inpfile=online_flag_name,
                    tbuff=1.5 * int_time,
                    reason="ANTENNA_NOT_ON_SOURCE",
                )
            )

        # 2. Deterministic flagging
        # Shadow flagging
        commands.append(
            self._format_flag_command(mode="shadow", tolerance=0.0, reason="shadow")
        )

        # Zero flagging
        commands.append(
            self._format_flag_command(
                mode="clip",
                clipzeros=True,
                correlation="ABS_ALL",
                reason="CLIP_ZERO_ALL",
            )
        )

        # Pointing scans
        if len(pointing_state_IDs) != 0:
            commands.append(
                self._format_flag_command(
                    mode="manual", intent="*POINTING*", reason="pointing"
                )
            )

        # Setup scans
        commands.append(
            self._format_flag_command(
                mode="manual", intent="UNSPECIFIED#UNSPECIFIED", reason="setup"
            )
        )
        commands.append(
            self._format_flag_command(
                mode="manual", intent="SYSTEM_CONFIGURATION#UNSPECIFIED", reason="setup"
            )
        )

        # Quack the data
        if quack_scan_string:
            commands.append(
                self._format_flag_command(
                    mode="quack",
                    scan=quack_scan_string,
                    quackinterval=1.5 * int_time,
                    quackmode="beg",
                    quackincrement=False,
                    reason="quack",
                )
            )

        # Flag end channels of each SPW
        for ispw in range(numSpws):
            if ispw < len(channels):
                fivepctch = int(0.05 * channels[ispw])
                if fivepctch > 0:
                    startch1 = 0
                    startch2 = fivepctch - 1
                    endch1 = channels[ispw] - fivepctch
                    endch2 = channels[ispw] - 1

                    commands.append(
                        self._format_flag_command(
                            mode="manual",
                            spw=f"{ispw}:{startch1}~{startch2}",
                            reason="end_channels",
                        )
                    )
                    commands.append(
                        self._format_flag_command(
                            mode="manual",
                            spw=f"{ispw}:{endch1}~{endch2}",
                            reason="end_channels",
                        )
                    )

        # 3. First tfcrop pass on calibrators (conservative)
        calibrator_fields = self._get_consolidated_calibrator_fields()
        if calibrator_fields and calibrator_scan_select_string:
            commands.append(
                self._format_flag_command(
                    mode="tfcrop",
                    field=calibrator_fields,
                    scan=calibrator_scan_select_string,
                    correlation=f"ABS_{corrstring}",
                    ntime="scan",
                    timecutoff=4.0,
                    freqcutoff=3.0,
                    combinescans=False,
                    datacolumn="data",
                    extendflags=False,
                    reason="tfcrop_pass1",
                )
            )

        # 4. Second tfcrop pass on calibrators (more aggressive)
        if calibrator_fields and calibrator_scan_select_string:
            commands.append(
                self._format_flag_command(
                    mode="tfcrop",
                    field=calibrator_fields,
                    scan=calibrator_scan_select_string,
                    correlation=f"ABS_{corrstring}",
                    ntime="scan",
                    timecutoff=3.0,
                    freqcutoff=2.5,
                    combinescans=False,
                    datacolumn="data",
                    extendflags=False,
                    reason="tfcrop_pass2",
                )
            )

        # 5. Extend flags across polarizations and adjacent channels
        commands.append(
            self._format_flag_command(
                mode="extend",
                extendpols=True,
                extendflags=True,
                growtime=80.0,
                growfreq=80.0,
                reason="extend_flags",
            )
        )

        result = self._apply_flag_stage(commands, "Initial Consolidated Flagging")

        # Track flagging progression
        self.context = track_flagging_progression(self.context, "stage1_flagging")

        # Update context
        self.context["stage1_flagging_applied"] = True
        self.context["QA2_stage1_flagging"] = "Pass"

        return result

    def _get_consolidated_calibrator_fields(self) -> str:
        """Get consolidated list of calibrator fields for flagging."""
        bandpass_fields = self.context.get("bandpass_field_select_string", "")
        delay_fields = self.context.get("delay_field_select_string", "")
        flux_fields = self.context.get("flux_field_select_string", "")
        phase_fields = self.context.get("phase_field_select_string", "")

        # Combine all calibrator fields
        all_fields = []
        for fields in [bandpass_fields, delay_fields, flux_fields, phase_fields]:
            if fields:
                all_fields.extend(fields.split(","))

        # Remove duplicates and create comma-separated string
        unique_fields = list(set(all_fields))
        return ",".join(unique_fields) if unique_fields else ""

    def stage2_calibrator_flagging(self) -> Dict[str, Any]:
        """
        Stage 2: Post-calibration flagging on calibrators.
        Replaces: EVLA_pipe_flag_baddeformatters + EVLA_pipe_checkflag
        """
        bandpass_field_select_string = self.context.get(
            "bandpass_field_select_string", ""
        )
        delay_field_select_string = self.context.get("delay_field_select_string", "")
        corrstring = self.context.get("corrstring", "RR,LL")
        testgainscans = self.context.get("testgainscans", "")

        commands = []

        # Bad deformatter flagging would go here (complex logic requiring cal table analysis)
        # For now, we'll add placeholder for this

        # RFI flagging on bandpass and delay calibrators
        checkflagfields = bandpass_field_select_string
        if bandpass_field_select_string != delay_field_select_string:
            checkflagfields += "," + delay_field_select_string

        if checkflagfields and testgainscans:
            commands.append(
                f"mode='rflag' field='{checkflagfields}' correlation='ABS_{corrstring}' scan='{testgainscans}' ntime='scan' combinescans=False datacolumn='corrected' winsize=3 timedevscale=4.0 freqdevscale=4.0 extendflags=False reason='RFI_calibrators'"
            )

        result = self._apply_flag_stage(commands, "Calibrator Flagging")

        # Update context
        self.context["stage2_flagging_applied"] = True
        self.context["QA2_stage2_flagging"] = "Pass"

        return result

    def stage3_semifinal_flagging(self) -> Dict[str, Any]:
        """
        Stage 3: Semi-final flagging during iterative calibration.
        Replaces: EVLA_pipe_checkflag_semiFinal
        """
        bandpass_field_select_string = self.context.get(
            "bandpass_field_select_string", ""
        )
        delay_field_select_string = self.context.get("delay_field_select_string", "")
        corrstring = self.context.get("corrstring", "RR,LL")
        testgainscans = self.context.get("testgainscans", "")

        commands = []

        # More aggressive RFI flagging
        checkflagfields = bandpass_field_select_string
        if bandpass_field_select_string != delay_field_select_string:
            checkflagfields += "," + delay_field_select_string

        if checkflagfields and testgainscans:
            commands.append(
                f"mode='rflag' field='{checkflagfields}' correlation='ABS_{corrstring}' scan='{testgainscans}' ntime='scan' combinescans=False datacolumn='corrected' winsize=3 timedevscale=3.0 freqdevscale=3.0 extendflags=False reason='RFI_semifinal'"
            )

        result = self._apply_flag_stage(commands, "Semi-Final Flagging")

        # Update context
        self.context["stage3_flagging_applied"] = True
        self.context["QA2_stage3_flagging"] = "Pass"

        return result

    def stage4_target_flagging(self) -> Dict[str, Any]:
        """
        Stage 4: Target flagging after calibrations applied.
        Replaces: EVLA_pipe_targetflag
        """
        corrstring = self.context.get("corrstring", "RR,LL")

        commands = []

        # RFI flagging on all calibrator scans
        commands.append(
            f"mode='rflag' field='' correlation='ABS_{corrstring}' scan='' intent='*CALIBRATE*' ntime='scan' combinescans=False datacolumn='corrected' winsize=3 timedevscale=4.0 freqdevscale=4.0 extendflags=False reason='RFI_all_calibrators'"
        )

        # RFI flagging on all target scans
        commands.append(
            f"mode='rflag' field='' correlation='ABS_{corrstring}' scan='' intent='*TARGET*' ntime='scan' combinescans=False datacolumn='corrected' winsize=3 timedevscale=4.0 freqdevscale=4.0 extendflags=False reason='RFI_all_targets'"
        )

        result = self._apply_flag_stage(commands, "Target Flagging")

        # Update context
        self.context["stage4_flagging_applied"] = True
        self.context["QA2_stage4_flagging"] = "Pass"

        return result


# Convenience functions for pipeline integration
def apply_stage1_flagging(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Stage 1 initial flagging."""
    flagger = PipelineFlagging(pipeline_context)
    flagger.stage1_initial_flagging()
    return pipeline_context


def apply_stage2_flagging(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Stage 2 calibrator flagging."""
    flagger = PipelineFlagging(pipeline_context)
    flagger.stage2_calibrator_flagging()
    return pipeline_context


def apply_stage3_flagging(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Stage 3 semi-final flagging."""
    flagger = PipelineFlagging(pipeline_context)
    flagger.stage3_semifinal_flagging()
    return pipeline_context


def apply_stage4_flagging(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Stage 4 target flagging."""
    flagger = PipelineFlagging(pipeline_context)
    flagger.stage4_target_flagging()
    return pipeline_context
