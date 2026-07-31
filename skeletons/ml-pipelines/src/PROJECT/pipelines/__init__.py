"""The four pipelines: data, training, inference, evaluation.

Each owns one stage of the D5 boundary and shares everything else through
``core``. Nothing here re-implements a core helper.

Every pipeline directory has the same shape (R1.4): ``classes/`` for
stateful objects behind an ABC, ``modules/`` for stateless functions, and
a thin ``pipeline.py`` orchestrator that sequences them.
"""
