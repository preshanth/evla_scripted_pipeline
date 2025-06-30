#!/usr/bin/env python3

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Import version from the package
import sys
sys.path.insert(0, str(this_directory / "evla_pipe"))
from evla_pipe import __version_str__, __author__, __email__, __description__

setup(
    name="evla-pipe",
    version=__version_str__,
    author=__author__,
    author_email=__email__,
    description=__description__,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/evla-scripted-pipeline",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Astronomy",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        # CASA dependencies would go here, but they're complex
        # For now, assume CASA is installed separately
    ],
    entry_points={
        "console_scripts": [
            "evla-pipeline=evla_pipe.run_pipeline:main",
        ],
    },
    include_package_data=True,
    package_data={
        "evla_pipe": ["*.py", "*.list"],
    },
)