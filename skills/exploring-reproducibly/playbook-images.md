# EDA Playbook — Images

Image datasets, typically for classification. Load with
[playbook-generic.md](playbook-generic.md) (five stages, cleaning
workflow, leakage rules) and
[playbook-stat-tests.md](playbook-stat-tests.md).

`[external]` marks published practice adopted here but not yet exercised
in a shipped analysis.

## 1. Metadata table first

Never load the pixels of a whole dataset to describe it. Walk the tree,
open each file, read its properties, and build one frame:

```
for p in DATA_DIR.rglob("*"):
    with Image.open(p) as im:
        im.load()          # forces decode, catches truncated files
        rows.append((p, p.parent.name, im.width, im.height,
                     im.width * im.height, im.width / im.height, im.mode))
```

Catch `(UnidentifiedImageError, OSError, ValueError)` into a `bad` list
and report its length. Corrupt and truncated files are a finding with an
action (drop, re-fetch, or exclude the source), not a silent skip.

The resulting frame — path, label, width, height, area, aspect ratio,
mode — is the equivalent of `df.info()` for images, and every check below
reads from it.

## 2. Class balance

- `value_counts()` per label, plotted with a mean-count reference line,
  plus `imbalance_ratio = max_count / min_count`.
- A ratio around 2.5 is moderate but consequential; state the degree,
  then record all three responses it triggers:
  1. **Stratified split**, so the rare classes appear in every fold.
  2. **Targeted augmentation** on the minority classes.
  3. **Weighted loss or a weighted sampler** during training.
- A balance figure with no downstream decision attached is the
  finding-without-action trap from the generic playbook. Calling a 2.65x
  spread "roughly balanced" and moving on is the failure mode to avoid.

## 3. Resolution and aspect ratio

- `describe()` on width, height, area, and aspect ratio, a 2x2 histogram
  grid, and a width-against-height scatter coloured by aspect ratio.
- The spread chooses the transform, and the choice is recorded with the
  number that drove it:
  - Wide dimension spread (for example 274 to 1300 px) → `Resize` to a
    fixed short side.
  - Wide aspect-ratio spread → `CenterCrop` or `RandomResizedCrop` over
    a naive square resize, which distorts.
  - Narrow spread on both → a fixed resize is safe and cheaper.

## 4. Format, colour mode, channels

- Tally file extensions and PIL `mode` values across the corpus.
  Inconsistent formats and modes are a preprocessing surprise waiting at
  batch time.
- **Force RGB** (`img.convert("RGB")`). Pretrained backbones expect three
  channels; `RGBA`, `P`, `L`, and `CMYK` files otherwise arrive with the
  wrong channel count or an alpha channel the model reads as data.
- Confirm the channel count from the array, not the mode string:
  `np.array(img).shape[-1]`. The mode is metadata; the shape is what the
  tensor will actually carry.

## 5. Colour separability

Accumulate per-class mean R, G, and B (channel sums divided by pixel
count, per class) and bar-plot them. This answers "is colour a usable
signal here" for a few seconds of compute, and it is what justifies or
rules out a colour-based augmentation such as `ColorJitter`. Without it,
a colour augmentation choice rests on impression.

## 6. Physical-quality screens

- **Blur** — variance of the Laplacian; low variance means blurred.
- **Saturation** — mean of the HSV S channel.
- **Contrast** — standard deviation of the HSV V channel.

Report P5 and P95 for each rather than the mean alone, and build small
filter functions that surface the images at each extreme for inspection.
The decision each screen feeds is whether to drop the tail, keep it and
augment toward it, or leave it alone.

## 7. Sampling and the sample grid

- Sample with a scoped generator: `rng = np.random.default_rng(42)`.
  Never `random.seed()`, which mutates global interpreter state and
  makes the sample depend on execution order elsewhere in the notebook.
- Draw a labelled grid, one row per class and about three columns, and
  print each sampled image's `(format, size, mode)` beside it. This
  catches per-sample inconsistency the corpus-wide tallies average away.
- Answer a fixed question list per class, so a visual skim becomes a
  comparable record:
  - Is colour informative for this class?
  - Where does the object sit, and is it centred?
  - How large is the object relative to the frame?
  - What orientations appear?
  - What features distinguish this class from its neighbours?

## 8. From observation to augmentation

Every augmentation is one numbered row tying one observation to one
named technique with concrete parameters and an expected effect:

| # | Observation | Technique | Expected effect |
|---|---|---|---|
| 1 | Counts span 2.5x | `WeightedRandomSampler` | Minority recall up |
| 2 | Width 274 to 1300 px | `RandomResizedCrop(224)` | Scale invariance |
| 3 | Objects rotated | `RandomRotation(20)` | Orientation robustness |
| 4 | Brightness spread | `ColorJitter(0.2, 0.2, 0.2)` | Lighting robustness |
| 5 | Objects occluded | `RandomErasing` | Less whole-shape reliance |

Instantiate the pipelines as named transforms and compare them in one
before/after grid over the sampled images. Techniques that contradict
the domain are ruled out here with the reason (a vertical flip on food
or document imagery produces images the task will never see).

## 9. Tensor audit before training

`[external]` The image analogue of `df.info()` and `df.describe()`, run
on one batch as it reaches the model: `arr.shape`, `arr.dtype`,
`arr.min()`, `arr.max()`, and per-channel means.

| State | dtype | Range |
|---|---|---|
| Raw | `uint8` | 0 to 255 |
| Normalised | `float32` | 0 to 1 |
| Standardised | `float32` | roughly -2 to +2 |

Check the layout too (HWC against CHW). A `uint8` tensor passed where
the model expects standardised `float32` raises no error and simply
produces poor metrics, which makes this a silent failure worth one
explicit cell.
