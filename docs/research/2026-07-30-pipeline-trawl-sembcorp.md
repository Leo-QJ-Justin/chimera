# Pipeline Trawl — Sembcorp work notebook (Pass 5 addendum)

> Research artifact for chimera. Mined 2026-07-30 per the trawl plan
> (docs/specs/2026-07-30-pipeline-templates-trawl-plan.md, Pass 5). Source:
> the maintainer's Sembcorp-era work notes (a Notion page: 7 typed code
> blocks plus 66 screenshots, all downloaded and transcribed). Domain: solar
> irradiance forecasting — ConvLSTM over satellite crops + weather feeds
> (Aeris 1h/5min, WeatherAPI) + pvlib features, 12×30-min forecast horizon.
> This is a working scrapbook, not a code artifact: patterns below are
> graded honestly, and several entries are anti-patterns kept as lessons.
> Machine-specific paths are shortened to placeholders. About a third of
> the screenshots are external reference material (a Gaussian Process
> lecture, Wikipedia clippings) with no skeleton value; they are ignored.

## What Pass 5 adds beyond Passes 1-4

- **The ingestion layer the corpus lacked**: glob-a-month → per-file
  normalise → concat → cache-to-parquet materialisation; per-source
  timezone contracts; coordinate rounding as a geospatial join key;
  point-in-time feature lookups with printed lookback windows.
- **A per-feed temporal alignment contract** (hand-drawn, img_63): each
  feed joined at its own cadence with floor-to-native-resolution and an
  explicit inclusive/exclusive-of-t rule per window.
- **A third run-state contract**: one `training_infor` dict that is config
  + live metrics + resume token, re-serialised every epoch.
- **Dual-criterion checkpointing** (best-by-loss and best-by-accuracy as
  separate files) with a NaN guard, plus a rolling per-epoch copy.
- **Partial-checkpoint transfer learning** with `module.` prefix stripping
  and a per-layer "Imported vs Random Initialization" audit report.
- **Tracking with no tracker**: the `.log` file is the experiment backend
  and `plot_log()` recovers curves by string-splitting it — the corpus's
  strongest evidence for the MLflow wrapper.
- **Sub-epoch subsampling** (train on 20% of batches per epoch) as a
  large-data throughput knob no other pass has.
- **Empirical case for schema enforcement**: a 1000× unit mismatch caught
  by residual triage, and a column named `start_time_sgt` carrying UTC
  tzinfo.

## 1. Ingestion: glob → normalise → cache parquet (img_01, img_02)

Aeris feeds are ingested as a loop over monthly glob unions, one normalise
step per file, single concat, cached to parquet — then the whole block is
commented out and replaced by `pd.read_parquet` of the cache:

```python
# aeris_1h_file_paths=glob('/data/.../aeris/SG/1hr/14d_forecast/202406*')+ ...
# for file_path in aeris_1h_file_paths:
#     aeris_file = pd.read_parquet(file_path)
#     aeris_file['queryTimeSgt'] = aeris_file['queryTimeUtc'] + pd.Timedelta(hours = 8)
#     aeris_file['validTime'] = pd.to_datetime(aeris_file['validTime']).dt.tz_localize(None)
#     aeris_file['lat_round']  = aeris_file['lat'].round(2)
#     aeris_file['long_round'] = aeris_file['long'].round(2)
#     aeris_file=aeris_file[['queryTimeSgt','lat_round','long_round','validTime','ghiWM2']]
#     aeris_file=aeris_file[(aeris_file['validTime']-aeris_file['queryTimeSgt'])<=pd.Timedelta(hours = 5)]
#     df_aeris_1h.append(aeris_file)
# df_aeris_1h=pd.concat(df_aeris_1h)
# df_aeris_1h.to_parquet('../../aeris_1h_202406to202408.parquet')
```

The comment-out *is* the cache-invalidation mechanism. Same shape for the
5-min feed and for WeatherAPI CSVs (which arrive already in SGT and join on
raw coordinates — per-feed inconsistency, see §2). Correct micro-patterns
inside it: accumulate-to-list then concat once (never concat in a loop),
project to needed columns early, horizon-filter at ingest.

Candidate for skeleton: **yes** — as a config-driven ingest stage (source
glob patterns, per-source normaliser, output parquet path, skip-if-exists)
that removes the commenting-out ritual and makes the cache a declared
artifact.

## 2. Per-source timezone and join-key contracts (img_01, 02, 04, 52)

- Aeris: `queryTimeSgt = queryTimeUtc + 8h`; `validTime` tz-localised to
  naive. WeatherAPI: already SGT, only `tz_localize(None)`. Every
  timestamp ends tz-naive-in-local before any join.
- The cost of not declaring this: the +8h offset is smeared into magic
  literals (`'2023-03-01 08:00:00'`, `'2024-06-01 07:30:00'` as epoch
  boundaries in the old `get_irr`, img_04), and one payload stores a
  column *named* `start_time_sgt` carrying `+00:00` UTC tzinfo (img_52).
- Coordinates: Aeris joins on `.round(2)` lat/long via a precomputed
  `site_to_aeris_coordinate_map` (nearest grid cell per site); WeatherAPI
  joins on raw coordinates with its own map. The rounding precision
  encodes the feed's grid spacing.

Candidate for skeleton: **yes** — a per-source declaration `{tz_in,
offset, join_keys, coordinate_precision}` plus one shared `to_naive_local`
helper; a schema layer that declares dtype/unit/tz per column and validates
at stage boundaries (see §8 for the empirical case).

## 3. Windowing and the temporal alignment contract (img_06-08, 13, 63)

One idiom appears five times with hand-recomputed arithmetic: anchor
flooring plus a `date_range` membership filter.

```python
query_time = inference_time.floor('H')
time_range = pd.date_range(start=query_time,
                           end=query_time + pd.Timedelta(minutes=num_intervals * 30), freq='30T')
filtered = table[table['validTime'].isin(set(time_range))].sort_values('validTime')
```

The hand-drawn alignment diagram (img_63) is the actual contract, and it
reconciles exactly with the Dataset slice widths:

| window | span | rule |
|---|---|---|
| `past_irr` | t-12 … t-1 (12 pts) | past only, **exclusive** of t |
| `img` | t-11 … t (12 pts) | **inclusive** of t (one-step offset from past_irr, deliberate) |
| `aeris_1hr` | 6 pts / 6h forward | query time **floored to the hour** |
| `aeris_5min` | 48 pts / ~4h forward | floored to the hour; right-padded with zeros to 48 |
| `pvlib`, target | t … t+24 forward | inclusive of t |

Candidate for skeleton: **yes** — a declarative feed spec (name, cadence,
window length, inclusive/exclusive of t, floor rule, expected length,
`on_short: pad|skip|error`) that a windowing helper reads. The
inclusive/exclusive off-by-one between `img` and `past_irr` is exactly the
bug class a declared spec prevents; currently it lives only in a
hand-drawn diagram and comment conventions.

## 4. Sample building: validity checks + parallel fan-out (img_18-21)

Per-site sample construction groups by entity and fans out with joblib:

```python
grouped = irr_table.groupby('subsite_id')
with Parallel(n_jobs=12) as parallel:
    site_sample_dict_list = parallel(delayed(process_grouped)(x) for x in grouped)
site_sample_dict={}
_=[site_sample_dict.update(ele) for ele in site_sample_dict_list if ele]
```

`process_grouped` runs three numbered validity checks — count
(`len(group) != 12`), continuity, asset availability (`len(imgs) != 36`) —
each `print(...) + return None`; the merge drops falsy results. Skip the
sample, never the run.

Weaknesses to fix on the way in: rejections go to stdout (should be a
logger call plus per-reason rejection counters surfaced as run metadata /
MLflow metrics); the continuity check hand-rolls a minutes-since-2023
encoding with `(365*24*60)` — a latent leap-year bug — where
`.diff() == Timedelta('30T')` suffices; a bare `except:` swallows image
read errors; `eval()` unpacks a stringified `pixel_id` tuple; the loader
switch uses `if pred_type == ...` twice with no `else`, so an unknown feed
silently produces an undefined variable.

Also here: each feed loader shares the signature
`load_<feed>(inference_timestamp, subsite_id_list) -> {site: list}` — a
hand-rolled feature-source registry (img_16, 17); and the recorded rewrite
rationale (img_03-05) for the vectorised `get_irr`: load reference tables
once at init, filter once with `isin`, never concat in a loop.

Candidate for skeleton: **yes** — groupby-fanout-merge with skip-invalid
semantics and a source registry (`load(anchor, entities)` +
`expected_len` per feed, assembly as a loop over the registry); `n_jobs`
from config.

## 5. Dataset / DataLoader (img_53-57; text)

Window validation happens in `__init__`, before any I/O — config typos
fail at construction, not at epoch 3:

```python
if look_back_window <= 0:
    raise ValueError("Please specify a valid timeframe of data to train on")
if look_back_window % 0.5 != 0:
    raise ValueError("Specified timeframe is not in intervals of 0.5 hours")
```

`__getitem__` slices one flat `feat` vector by hard-coded index ranges
with per-block scaling constants:

```python
past_irr_array = features[1:13]  / 1600
pv_array       = features[13:37] / 1600
ghi_hourly     = features[37:43] / 1600
ghi_5min       = features[43:91] / 1600
cloud_hourly   = features[91:]   / 100
```

Verified downstream: batch shapes `(1, 12, 4, 64, 64)` image (3 satellite
bands + 1 synthetic centre-pixel positional channel), `(1, 133)` features,
`(1, 12)` target (img_57) — 133 is exactly the sum of the block widths.
Normalisation is by **fixed physical divisor per feature family** (1600
W/m² irradiance, 100 cloud percent, 255 image) — no fitted scaler, so
train/serve skew is impossible by construction for physically-bounded
feeds. `DataLoader(batch_size=32, shuffle=False, num_workers=10)`;
augmentation applied to all channels except the last (the positional
channel is copied through untransformed).

Candidate for skeleton: **partial** — keep constructor validation, the
tuple multi-input convention (`(image, features) -> model((X, f))`), the
divisor-normalisation mode as a first-class config option, and selective
channel augmentation. Replace magic slices with an ordered block registry
`(name, width, scale)` that derives offsets and asserts total width — the
133 becomes a computed invariant. Fix the bare `except: print('error')`
around `np.load` (leaves the variable unbound; the real error surfaces as
a confusing NameError inside a worker).

## 6. Training harness (typed text; the page's 7 code blocks)

A self-contained MLflow-free PyTorch harness built around one mutable
state dict — the page's distinctive contribution.

- **`training_infor` dict = config + live metrics + resume token.** Seeded
  in the constructor (`break_flag`, `epoch`, `best_valid_loss=1e6`,
  `lr_schd_his=[]`, `save_dir` namespaced by experiment name), written as
  `training_infor.npy` at the end of *every* epoch, reloaded to resume.
  Resume semantics rewind `epoch` to `best_valid_accu_epoch` — "restart
  from the best point", not "continue where I stopped". Mutable default
  argument (`training_infor={}`) on three `__init__` signatures.
- **Trainer utilities as free functions over the state dict**: hand-rolled
  plateau LR scheduler (history buffer cleared on decay, LR written
  straight into `optimizer.param_groups`) and early stopper; `sys.exit()`
  on a bad `watch` argument (fail-fast instinct, wrong mechanism).
- **Dual-criterion checkpointing**: `_model_loss.pth` and
  `_model_accu.pth` as independent bests, each behind a NaN guard so a
  diverged epoch cannot overwrite a good checkpoint; plus a rolling
  per-epoch copy with glob-based single-copy retention. All three savers
  use `torch.save(model, path)` (whole-module pickle) with the correct
  `state_dict` line commented out beneath each.
- **Partial-checkpoint transfer learning**: strip `module.` prefixes from
  both dicts, exclude head layers, `load_state_dict(strict=False)`, then
  audit-print every layer as `Imported` or `Random Initialization`. The
  shape-compatibility filter that would generalise it is commented out.
- **Log file as tracking backend**: `logging.basicConfig` *inside*
  `train()` (silently no-ops on the second run per kernel), `filemode`
  keyed to fresh-vs-continue, a free-text `log_remark` per run, and
  `plot_log()` recovering curves via
  `float(line.split('train loss ')[1].split(',')[0])`.
- **Loop mechanics worth keeping**: sample-weighted metric accumulation
  (correct for ragged final batches), per-phase wall-time logging,
  sub-epoch subsampling (`RandomSampler(num_samples=len(ds)//rate)` in one
  class; a `break`-based variant in the other), optimizer constructed
  after `DataParallel` wrap + `.to(device)`.
- **Experiment naming as the only registry**:
  `test_name = 'multiple_sites_indiv_data_input_enhanced_convlstm_with_aeris_v5'`
  encodes six dimensions (sites × input mode × architecture × feed ×
  modality × version) in a string that also determines `save_dir`, log
  filename, and every artifact name.

Candidate for skeleton: **partial** — keep the pure-functions-over-state
shape, dual-criterion bests generalised to `monitor: {name, mode}`, the
NaN guard, `resume: continue|from_best` as a named config choice, the
transfer-learning util (with the shape filter enabled), `log_remark`, and
`subsample_frac` via sampler. Replace `np.save`-pickled state with typed
config + JSON metadata (Pass 1's envelope), `state_dict` over
whole-module pickle, `ReduceLROnPlateau` over the hand-rolled scheduler,
and log-scraping with a metrics sink.

## 7. Inference pipeline (img_22-29; img_51)

- **Feed-keyed model registry in dict form** (img_25): `checkpoint_path`
  and `num_additional_features` (`weatherapi: 31`, `aeris: 79`) both keyed
  by feed name — the hand-rolled version of config-driven variant
  selection. Checkpoint loading handles the DataParallel case
  (`isinstance(...) -> .module.state_dict()`), then `eval()` +
  `.to(device)`.
- **Batched no-grad inference** with tuple inputs and `shuffle=False`,
  `np.concatenate` of per-batch outputs.
- **Wide-to-long horizon expansion**: `reshape(n, 12)` predictions →
  `forecast_time = inference_time + 30min * i` → the 4-column output
  contract `['site_id', 'inference_timestamp_local',
  'forecast_timestamp_local', 'pred_convlstm']` — matching the deployed
  payload (img_51, staggered per-site-group inference batches). Currently
  built with `iterrows()` and positional `iloc[:, 1:-2]` slicing.
- **De-normalisation by re-typed constant**: `* 1600` at inference,
  annotated `#wrong?` by the maintainer — the argument for persisting the
  target scaler with the checkpoint rather than re-typing it.
- **Physics post-processing hook**: `make_night_zero_1` applied to raw
  model output before emission; empty-input guard returns an empty
  DataFrame (should carry the declared output schema).
- Commented-out `time.time()` stage stopwatches at every stage — stage
  timing was wanted and repeatedly hand-rolled; a skeleton should ship a
  `stage_timer` context manager logging to logger + MLflow.

Candidate for skeleton: **yes** — `load_checkpoint` (DataParallel-safe),
`predict(model, dataloader, device)`, a `wide_to_long_forecast(preds,
keys, anchor, step, horizon)` helper emitting the 4-column contract, and
declared post-prediction constraint hooks.

## 8. Cleaning DAGs and QA evidence (img_14, 15, 58-65)

The hand-drawn pipeline diagrams (img_64, 65) are design documents for
power-data cleaning and scale-factor derivation:

- **Every join carries its key AND its duplicate policy**: `merge on
  ['site_code']` → `drop_duplicates(subset=('site_code','meter_id'))`
  with "keep original meter_id" noted; `merge solaris_mapping on
  ['site_object_id']` with "multiple subsites can share a site_id" noted.
- **Cleaning order is load-bearing**: `make_night_zero` → per-group
  z-score anomaly detection → interpolate missing → red-ink invariant
  "*should have no NAs*". Zero the physically-known-zero region *before*
  computing z-scores, or night zeros poison the distribution.
- **Collapse subsites to site grain** by `groupby(site_id, timestamp)` +
  median (robust to one bad sensor).
- **Nearest-neighbour hazards documented**: the site mapping self-matches
  (`90_1 → 90_1`) and is non-symmetric; the fix ("retain first record,
  drop the rest") silently picks an arbitrary winner — should be a
  logged, explicit tie-break.
- **Point-in-time lookup that prints its own window**:
  `retrieve_scale_factor(meter_id, ts)` echoes the resolved one-month
  lookback before computing — an audit-friendly habit worth standardising.
- **Residual triage caught a 1000× unit bug** (img_58-62): `diff` +
  `abs_difference` + sort-descending + drill into the worst
  `(meter_id, inference_timestamp)` surfaced `343877.33` vs `343.877` for
  the same quantity across two derivations — a scale-factor unit
  mismatch, not a model error. Together with the `_sgt`-named UTC column,
  this is the empirical case for per-column unit/tz schema validation.
- Stuck-sensor detection (img_15): sentinel-diff → cumsum run-id →
  group-count run-length → NaN-out runs ≥ n during daytime. The
  run-length idiom is a reusable data-quality primitive; the daytime mask
  and `-100` sentinel are domain parameters.

Candidate for skeleton: **yes** — join-with-declared-dedupe steps, ordered
cleaning stages with post-condition assertions, the run-length flatline
detector (parameterised), top-N residual triage in the evaluation module,
and column-level unit/tz schema checks.

## 9. Anti-pattern inventory (kept as lessons)

1. ~300-line commented-out duplicate of the trainer class next to the live
   one — manual versioning by comment block.
2. `torch.save(model)` over `state_dict` in all three savers.
3. Bare `except:` twice (image reads; `np.load` in `__getitem__`).
4. `logging.basicConfig` inside `train()`; mutable default args.
5. Magic constants everywhere: `/1600` (annotated `#wrong?` at inference),
   `/255`, `/100`, `n_jobs=12`, `num_workers=10` vs `0` in twin classes,
   `Const=1000` in inverted-loss metrics.
6. Metrics as `Const - error` nn.Modules to reuse higher-is-better
   bookkeeping — the right fix is `monitor: {name, mode}`.
7. Hand-rolled minutes-since-2023 continuity encoding with a latent
   leap-year bug.
8. Filename templating with an inline naming-convention cutover date
   (`if check_time > '2024-04-22'`) — should be config as
   `(effective_from, template)` rules; the backward time-walk fallback
   (`[0, -10, -20]` minutes) is itself a keeper.
9. Three near-identical trainer classes with no shared base.
10. An abandoned non-running cell (typos, `np.array()` with no args)
    copied from the solar Dataset for a finance experiment and never
    finished.

## Open questions for synthesis

1. **Which run-state contract wins?** Three now exist: `metadata.json` +
   timestamped dirs (Pass 1), torch checkpoint dicts (Pass 2),
   `training_infor.npy` (Pass 5). Pass 5's claim — config, metrics, and
   resume token as *one* object — is worth keeping as a concept, but as
   typed config + JSON, never a pickled dict.
2. **Resume semantics need a name**: `resume: continue|from_best` — Pass 5
   rewinds to best, Pass 2 implies continue-from-last. Different products.
3. **Dual-criterion bests vs a single `monitor: {name, mode}`** — is
   keeping two best files worth the API surface?
4. **Sub-epoch subsampling** (`train_frac`/`val_frac` per epoch,
   sampler-based) — expose in the skeleton? No other pass has it.
5. **Fixed-divisor normalisation vs fitted scalers** — for
   physically-bounded sensor feeds the divisor mode eliminates
   train/serve skew and scaler persistence entirely. First-class
   `normalization: {feature_group: divisor}` config mode?
6. **Feature manifest**: the flat-vector-with-magic-slices problem
   recurs (133-dim vector, `features[43:91]`). Should every assembled
   feature array ship a manifest (name, slice, source, dtype, scale) as a
   logged artifact?
7. **Log-scraping fallback**: should the MLflow-optional mode write a
   structured CSV/JSONL metrics sidecar (so no one ever parses prose logs
   again), with a `plot_log` equivalent reading it?
8. **Run naming**: derive run names from config keys (generated, never
   typed) — does that break the maintainer's habit of grepping directory
   names by hand-typed `test_name`?
9. **Screenshots vs code**: the ingestion evidence here is transcribed
   from images and hand-drawn diagrams — intent more than implementation.
   If the underlying notebooks ever become available, the transcriptions
   in this doc should be checked against them before any verbatim lift.
