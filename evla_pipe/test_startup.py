# test_startup.py
from EVLA_pipe_startup import pipeline_startup

initial_context = {}
updated_context = pipeline_startup(initial_context)
print(updated_context)