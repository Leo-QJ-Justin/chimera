"""Device selection, GPU pinning, and multi-GPU wrapping.

**Import-ordering constraint (the reason torch is imported inside the
functions here, not at module top):** ``CUDA_VISIBLE_DEVICES`` and
``CUDA_DEVICE_ORDER`` are read by the CUDA driver when the CUDA context
is first initialised. Setting them after ``import torch`` has already
initialised CUDA is a silent no-op - the process keeps the device set it
started with, and a run pinned to "GPU 3" quietly trains on GPU 0. This
module therefore reads config, writes the environment, and only *then*
imports torch. Every other module in this package imports torch at the
top, which is fine: they are only ever imported after ``setup_device``
has run in the entry path, and importing torch elsewhere first still
leaves the *device-visibility* decision correct as long as this function
is the first thing that touches CUDA.

``PCI_BUS_ID`` ordering makes ``cuda:0`` mean the same physical card as
``nvidia-smi`` reports; the torch default (fastest-first) does not.
"""

import logging
import os

logger = logging.getLogger(__name__)


def setup_device(cfg) -> "torch.device":  # noqa: F821 (torch imported lazily)
    """Resolve the training device, pinning GPUs before torch loads CUDA.

    Args:
        cfg: Device config section with attributes (or mapping keys)
            ``device`` (``"auto" | "cuda" | "cuda:N" | "mps" | "cpu"``),
            ``visible_devices`` (a ``CUDA_VISIBLE_DEVICES`` string such as
            ``"0,1"``, or None to leave the environment alone), and
            ``device_order`` (default ``"PCI_BUS_ID"``).

    Returns:
        The selected ``torch.device``. Selection cascade for ``"auto"``:
        cuda -> mps -> cpu.
    """
    visible = _cfg_get(cfg, "visible_devices", None)
    if visible is not None:
        # Must precede the torch import below; see the module docstring.
        os.environ["CUDA_DEVICE_ORDER"] = str(_cfg_get(cfg, "device_order", "PCI_BUS_ID"))
        os.environ["CUDA_VISIBLE_DEVICES"] = str(visible)
        logger.info(
            "Pinned CUDA_VISIBLE_DEVICES=%s (%s ordering)",
            visible,
            os.environ["CUDA_DEVICE_ORDER"],
        )

    import torch  # noqa: PLC0415 (deliberate: must follow the env writes)

    requested = str(_cfg_get(cfg, "device", "auto"))
    if requested != "auto":
        device = torch.device(requested)
        if device.type == "cuda" and not torch.cuda.is_available():
            # Fail loudly rather than silently training 50x slower on CPU.
            raise RuntimeError(
                f"Config requested device {requested!r} but CUDA is not available"
            )
        logger.info("Using device: %s (explicitly requested)", device)
        return device

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif (
        getattr(torch.backends, "mps", None) is not None
        and torch.backends.mps.is_available()
    ):
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info("Using device: %s (auto-selected)", device)
    return device


def wrap_model(model, device):
    """Move a model to ``device`` and wrap it in ``DataParallel`` on multi-GPU.

    Call this **before** constructing the optimizer: the optimizer must
    own the parameters of the object that is actually stepped, and both
    ``.to(device)`` and the ``DataParallel`` wrap change that object.

    Args:
        model: The bare ``nn.Module``.
        device: Device from :func:`setup_device`.

    Returns:
        The moved (and possibly wrapped) model.
    """
    import torch  # noqa: PLC0415 (kept lazy for symmetry with setup_device)
    from torch import nn

    model = model.to(device)
    if device.type == "cuda" and torch.cuda.device_count() > 1:
        logger.info(
            "Wrapping model in DataParallel over %d GPUs", torch.cuda.device_count()
        )
        model = nn.DataParallel(model)
    return model


def describe_device(device) -> str:
    """A short, param-able device string for run metadata and MLflow.

    ``str(device)`` alone loses the card model and the GPU count, which
    are exactly what one wants when comparing two runs' throughput.
    """
    import torch  # noqa: PLC0415

    if device.type == "cuda":
        index = device.index or 0
        name = torch.cuda.get_device_name(index)
        return f"cuda:{index} ({name}) x{torch.cuda.device_count()}"
    return str(device)


def _cfg_get(cfg, key: str, default):
    """Read a key from a pydantic model, dataclass, DictConfig or dict."""
    if hasattr(cfg, key):
        return getattr(cfg, key)
    try:
        return cfg[key]
    except (TypeError, KeyError):
        return default
