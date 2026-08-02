"""The four pipelines: data, training, inference, evaluation.

Each owns one stage and shares everything else through ``core``. Nothing
here re-implements a core helper. Anything that needs ``.fit()`` lives
inside a trainer, not the data pipeline, so fitted state refits per fold
and serializes with the model.

Every pipeline directory has the same shape: ``classes/`` for stateful
objects behind an ABC, ``modules/`` for stateless functions, and a thin
``pipeline.py`` orchestrator that sequences them.
"""
