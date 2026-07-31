"""Single seed entry point.

One ``run.seed`` config key feeds this once at pipeline start; components
receive the same value as an explicit kwarg where their library requires
it (sklearn ``random_state``, LightGBM ``seed``). The seed used is
persisted into run metadata by the caller.
"""

import logging
import os
import random

import numpy as np

logger = logging.getLogger(__name__)


def set_seed(seed: int = 42, deterministic_cudnn: bool = False) -> int:
    """Seed every RNG source available in the current environment.

    Args:
        seed: The seed value threaded to python, numpy and (if installed)
            torch CPU/CUDA generators, plus ``PYTHONHASHSEED``.
        deterministic_cudnn: Also pin cuDNN to deterministic kernels.
            Slows training and can raise on ops without deterministic
            implementations, so it is opt-in rather than default.

    Returns:
        The seed, so call sites can log it.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        if deterministic_cudnn:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
    return seed


def torch_generator(seed: int):
    """A seeded ``torch.Generator`` for DataLoader shuffling, plus the
    matching ``worker_init_fn`` - the two DataLoader randomness sources a
    bare ``set_seed`` does not cover.

    Returns:
        ``(generator, worker_init_fn)``. Pass both to ``DataLoader``.

    Raises:
        ImportError: If torch is not installed.
    """
    import torch

    generator = torch.Generator()
    generator.manual_seed(seed)

    def worker_init_fn(worker_id: int) -> None:
        worker_seed = (seed + worker_id) % 2**32
        np.random.seed(worker_seed)
        random.seed(worker_seed)

    return generator, worker_init_fn
