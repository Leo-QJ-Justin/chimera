"""Torch architectures: the layer-order and init rules made explicit.

Named ``architectures`` rather than ``models`` because "model" already
means the Hydra config group; this module holds only the ``nn.Module``
classes ``TorchTrainer`` can build.

Two prescriptions from the maintainer's notes are encoded here rather
than left to memory:

- **Layer order**: ``Linear -> BatchNorm -> ReLU -> Dropout``. BatchNorm
  before the activation normalises the pre-activations (its stated
  purpose); dropout last so it does not corrupt the batch statistics.
- **Init pairing**: He (Kaiming, ``fan_in``) for ReLU-family hidden
  layers - it compensates for ReLU zeroing about half the activations.
  Xavier for the output layer, whose activation is the loss's (softmax
  inside ``CrossEntropyLoss``, or identity for regression).
"""

import logging

from torch import nn

logger = logging.getLogger(__name__)


class MLP(nn.Module):
    """A plain multilayer perceptron for tabular inputs.

    Args:
        input_dim: Number of input features (from the feature manifest's
            total width - never a hand-typed constant).
        hidden_sizes: Width of each hidden block.
        n_classes: Output width. Use ``1`` for regression / binary
            logits; the head is linear either way (no Softmax in the
            module - ``CrossEntropyLoss`` expects logits).
        dropout: Dropout probability applied after each hidden block.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_sizes: list[int],
        n_classes: int,
        dropout: float = 0.0,
    ):
        super().__init__()
        if input_dim <= 0:
            raise ValueError(f"input_dim must be positive, got {input_dim}")
        if not 0.0 <= dropout < 1.0:
            raise ValueError(f"dropout must be in [0, 1), got {dropout}")

        layers: list[nn.Module] = []
        previous = input_dim
        for width in hidden_sizes:
            layers += [
                nn.Linear(previous, width),
                nn.BatchNorm1d(width),
                nn.ReLU(),
                nn.Dropout(dropout),
            ]
            previous = width
        self.head = nn.Linear(previous, n_classes)
        self.body = nn.Sequential(*layers)
        self._init_weights()

    def _init_weights(self) -> None:
        for module in self.body.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, mode="fan_in", nonlinearity="relu")
                nn.init.zeros_(module.bias)
        nn.init.xavier_uniform_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, x):
        return self.head(self.body(x))


def count_parameters(model: nn.Module) -> int:
    """Trainable parameter count - log it as a run param, not a comment."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
