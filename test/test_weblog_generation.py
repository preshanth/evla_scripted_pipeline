"""
Test weblog generation with mock data.

Verifies that all pages generate correctly and navigation links work.
"""

import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock CASA and numpy modules to avoid dependencies in test environment
from unittest.mock import MagicMock

# Create comprehensive mocks
sys.modules['numpy'] = MagicMock()
sys.modules['casatasks'] = MagicMock()
sys.modules['casatools'] = MagicMock()
sys.modules['casaplotms'] = MagicMock()

# Now safe to import
from evla_pipe.modern_weblog import ModernWeblogGenerator
from evla_pipe.weblog_templates import WeblogTemplateEngine


def create_mock_context():
    """Create mock pipeline context with realistic fake data."""
    context = {
        # Project metadata
        'projectCode': 'TEST2025A-001',
        'piName': 'Dr. Jane Astronomer',
        'SDM_name': 'test_observation_2025-01-15.ms',
        'observeDateString': '2025-01-15 12:34:56',

        # Data characteristics
        'EVLA_band': 'X',
        'do_pol': True,
        'total_time': '3600.0 seconds',
        'num_spws': 16,

        # Metrics
        'total_flagged_percent': '18.3',
        'calibrator_count': 4,
        'target_count': 2,
        'rms_noise': '15.7',

        # Calibration tables (polarization)
        'kcross_cal_table': 'test.kcross',
        'dterms_cal_table': 'test.dterms',
        'polarization_models_set': True,
        'pol_angle_field': 'J1331+3030',
        'pol_leakage_field': 'J0542+4951',
        'kcross_solutions': 12,
        'avg_leakage': '2.3',
        'standard_source_names': ['3C286', '3C138'],
        'avg_pol_fraction': '4.1',

        # QA scores - simulate a real run with some issues
        'QA2_import': 'Pass',
        'QA2_hanning': 'Pass',
        'QA2_msinfo': 'Pass',
        'QA2_flagall': 'Pass',
        'QA2_calprep': 'Pass',
        'QA2_priorcals': 'Pass',
        'QA2_testBPdcals': 'Partial',  # Some issues
        'QA2_flag_baddeformatters': 'Pass',
        'QA2_checkflag': 'Pass',
        'QA2_semiFinalBPdcals1': 'Pass',
        'QA2_checkflag_semiFinal': 'Pass',
        'QA2_solint': 'Pass',
        'QA2_testgains': 'Pass',
        'QA2_fluxgains': 'Partial',  # Flux scale uncertainty
        'QA2_fluxboot': 'Pass',
        'QA2_finalcals': 'Pass',
        'QA2_applycals': 'Pass',
        'QA2_targetflag': 'Pass',
        'QA2_statwt': 'Pass',
        'QA2_plotsummary': 'Pass',
    }

    return context


def create_mock_plots(weblog_dir):
    """Create fake plot files for testing."""
    plots = [
        'bandpass_phase.png',
        'bandpass_amplitude.png',
        'gain_phase.png',
        'gain_amplitude.png',
        'flux_calibration.png',
        'target_data.png'
    ]

    for plot_name in plots:
        plot_path = weblog_dir / plot_name
        # Create a minimal PNG file (1x1 pixel transparent)
        # PNG header + minimal IHDR + IEND chunks
        png_data = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        with open(plot_path, 'wb') as f:
            f.write(png_data)


def verify_html_file(file_path, expected_content_snippets):
    """Verify HTML file exists and contains expected content."""
    assert file_path.exists(), f"File {file_path} not created"

    content = file_path.read_text()

    for snippet in expected_content_snippets:
        assert snippet in content, f"Expected snippet not found in {file_path}: {snippet}"

    return content


def test_weblog_generation():
    """Test complete weblog generation with mock data."""

    # Create temporary directory for weblog output
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        weblog_dir = tmpdir / 'weblog'
        weblog_dir.mkdir()

        # Mock the weblog path functions
        original_get_weblog_path = None
        original_get_log_path = None
        try:
            from evla_pipe import utils
            original_get_weblog_path = utils.get_weblog_path
            original_get_log_path = utils.get_log_path

            def mock_get_weblog_path(filename=''):
                """Mock get_weblog_path - returns Path, not string."""
                if filename:
                    return weblog_dir / filename
                return weblog_dir

            def mock_get_log_path(filename=''):
                """Mock get_log_path - returns Path, not string."""
                log_dir = tmpdir / 'logs'
                log_dir.mkdir(exist_ok=True)
                if filename:
                    return log_dir / filename
                return log_dir

            def mock_logprint(msg, logfileout=None):
                """Mock logprint to avoid CASA dependency."""
                print(f"LOG: {msg}")

            utils.get_weblog_path = mock_get_weblog_path
            utils.get_log_path = mock_get_log_path
            utils.logprint = mock_logprint

            # Reload modern_weblog module to pick up mocked functions
            import importlib
            from evla_pipe import modern_weblog
            importlib.reload(modern_weblog)
            from evla_pipe.modern_weblog import ModernWeblogGenerator

            # Create mock context and plots
            context = create_mock_context()
            create_mock_plots(weblog_dir)

            # Generate weblog
            print("\n=== Testing Weblog Generation ===")
            print(f"Weblog directory: {weblog_dir}")
            generator = ModernWeblogGenerator(context)
            generator.generate_weblog()

            # Debug: List what files actually got created
            files_created = list(weblog_dir.glob('*'))
            print(f"\nFiles in weblog directory: {[f.name for f in files_created]}")

            # Verify all pages were created
            print("\n✓ Checking generated files...")
            expected_html_files = [
                'index.html',
                'observation.html',
                'calibration.html',
                'qa_report.html',
                'plots.html'
            ]

            for filename in expected_html_files:
                filepath = weblog_dir / filename
                assert filepath.exists(), f"Missing file: {filename}"
                print(f"  ✓ {filename} created")

            # Verify navigation is present in all pages
            print("\n✓ Checking navigation links...")
            html_files = expected_html_files

            for filename in html_files:
                filepath = weblog_dir / filename
                content = filepath.read_text()

                # Check navigation links present
                nav_links = [
                    'href="index.html"',
                    'href="observation.html"',
                    'href="calibration.html"',
                    'href="qa_report.html"',
                    'href="plots.html"'
                ]

                for link in nav_links:
                    assert link in content, f"Missing nav link in {filename}: {link}"

                print(f"  ✓ {filename} has all navigation links")

            # Verify summary page content
            print("\n✓ Checking summary page content...")
            summary_content = verify_html_file(
                weblog_dir / 'index.html',
                [
                    'TEST2025A-001',  # Project code
                    'Dr. Jane Astronomer',  # PI name
                    'test_observation_2025-01-15.ms',  # SB ID
                    '2025-01-15',  # Observation date
                    'Pipeline Summary',
                    'EVLA Pipeline Report'
                ]
            )

            # Check for active navigation on summary page
            assert 'class="nav-link active"' in summary_content, "No active nav link on summary"
            print("  ✓ Summary page content verified")

            # Verify QA report page
            print("\n✓ Checking QA report page...")
            qa_content = verify_html_file(
                weblog_dir / 'qa_report.html',
                [
                    'Quality Assurance Report',
                    'Data Import',
                    'Hanning Smoothing',
                    'Pass',  # Should have some Pass scores
                    'Partial'  # Should have some Partial scores
                ]
            )

            # Check for polarization section (since do_pol=True)
            assert 'Polarization Calibration Status' in qa_content, "Missing polarization QA"
            assert 'J1331+3030' in qa_content, "Missing pol angle calibrator"
            print("  ✓ QA report content verified")

            # Verify plots page
            print("\n✓ Checking plots page...")
            plots_content = verify_html_file(
                weblog_dir / 'plots.html',
                [
                    'Diagnostic Plots',
                    'bandpass_phase.png',
                    'bandpass_amplitude.png',
                    'gain_phase.png',
                    '<img src='  # At least one image tag
                ]
            )

            # Count plot entries
            plot_count = plots_content.count('<div class="plot-item">')
            assert plot_count == 6, f"Expected 6 plots, found {plot_count}"
            print(f"  ✓ Plots page shows {plot_count} plots")

            # Verify observation and calibration pages exist with content
            print("\n✓ Checking other pages...")
            obs_content = (weblog_dir / 'observation.html').read_text()
            assert 'Observation Details' in obs_content
            print("  ✓ Observation page generated")

            cal_content = (weblog_dir / 'calibration.html').read_text()
            assert 'Calibration Details' in cal_content
            print("  ✓ Calibration page generated")

            # Test JSON export via wrapper function
            print("\n✓ Testing JSON export...")
            import json
            from evla_pipe.modern_weblog import EVLA_pipe_modern_weblog

            # Save JSON via wrapper function
            json_context = EVLA_pipe_modern_weblog(context)
            json_path = weblog_dir / 'weblog_data.json'
            assert json_path.exists(), "weblog_data.json not created by wrapper"

            with open(json_path) as f:
                json_data = json.load(f)
            assert json_data['project_code'] == 'TEST2025A-001'
            assert json_data['overall_qa_score'] == 'Partial'
            print("  ✓ JSON export verified")

            # Verify CSS and JavaScript are embedded
            print("\n✓ Checking embedded assets...")
            for filename in html_files:
                content = (weblog_dir / filename).read_text()
                assert '<style>' in content and 'var(--primary-blue)' in content, f"CSS missing in {filename}"
                assert '<script>' in content and 'DOMContentLoaded' in content, f"JS missing in {filename}"
            print("  ✓ CSS and JavaScript embedded in all pages")

            print("\n" + "="*50)
            print("✅ ALL WEBLOG TESTS PASSED")
            print("="*50)
            print(f"\nGenerated weblog in: {weblog_dir}")
            print(f"Total files created: {len(list(weblog_dir.glob('*')))}")

            return True

        finally:
            # Restore original functions
            if original_get_weblog_path:
                utils.get_weblog_path = original_get_weblog_path
            if original_get_log_path:
                utils.get_log_path = original_get_log_path


def test_template_engine_standalone():
    """Test template engine in isolation."""
    print("\n=== Testing Template Engine ===")

    engine = WeblogTemplateEngine()

    # Test template loading
    assert 'base' in engine.templates
    assert 'navigation' in engine.templates
    assert 'summary' in engine.templates
    assert 'qa_report' in engine.templates
    print("✓ All templates loaded")

    # Test rendering
    context = {
        'pipeline_version': '2.0.0',
        'project_code': 'TEST',
        'pi_name': 'Test User',
        'sb_id': 'test.ms',
        'observation_date': '2025-01-01',
        'qa_score': 'Pass',
        'qa_status_class': 'pass',
        'casa_version': '6.5.0',
        'processing_date': '2025-01-01',
        'frequency_band': 'X',
        'polarization_mode': 'Full',
        'total_time': '3600s',
        'num_spws': '16',
        'total_flagged_percent': '15.2',
        'calibrator_count': '3',
        'target_count': '1',
        'rms_noise': '12.3'
    }

    # Test summary rendering
    summary = engine.render_template('summary', context)
    assert 'TEST' in summary
    assert 'Test User' in summary
    print("✓ Summary template renders")

    # Test navigation rendering
    nav = engine.render_template('navigation', {
        'index_active': 'active',
        'obs_active': '',
        'cal_active': '',
        'qa_active': '',
        'plots_active': ''
    })
    assert 'nav-tabs' in nav
    assert 'active' in nav
    print("✓ Navigation template renders")

    # Test full page generation
    content = '<h1>Test Content</h1>'
    page = engine.generate_full_page('Test', content, context, 'index')

    assert '<!DOCTYPE html>' in page
    assert 'Test Content' in page
    assert 'nav-tabs' in page
    assert 'Pipeline v2.0.0' in page or '2.0.0' in page
    print("✓ Full page generation works")

    print("✅ Template engine tests passed")
    return True


if __name__ == '__main__':
    try:
        # Run tests
        test_template_engine_standalone()
        test_weblog_generation()

        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
