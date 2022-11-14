The test-suite is written against the results of the EVLA scripted pipeline
v1.4.2 on the test L Band dataset
`15A-397.sb31019491.eb31020561.57236.7198700463`. The SDM-BDF is about 7 GB in
size and can be downloaded from the NRAO [archive](https://data.nrao.edu). The
script assumes that the SDM-BDF has been renamed to `test.sdm`.

To run the test-suite, call `pytest <path-to-"run_tests.py">` from the command
line in the directory where the pipeline has been run. The test-suite requires
Python v3.8 and the `pytest`, `numpy`, and `casatools` modules to be installed.
