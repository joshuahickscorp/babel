# Babel — Forgiving Speech Engine (Engineering Plan, v4)

A small, fast, locally-deployable speech model that assumes it will mishear you and fixes it. Trained in the cloud at terabyte scale, shipped as a tiny artifact. Built for the accents, dialects, and broken or code-switched speech that normal ASR underserves.

Codename Babel is a placeholder.

> **Revision note (v4).** Extends v3 into a moat-building plan: not only what to train, but what compounds. The moat is a licensed tail-speech corpus, a hard public parity benchmark, an error taxonomy, an active-learning loop, a small local runtime, and a UX feedback loop that makes the system improve exactly where broad ASR products stay weak. Adds an optimization ladder for quality, minimum parameters, speed, memory, data quality, evaluation, product trust, and distribution. The central answer is still maximalist-but-bounded: increase everything only along the Pareto frontier, and stop any lever when it starts buying average-case vanity at the cost of worst-group quality, latency, or local deployability.
>
> **Revision note (v3).** Folds in the instructor-sizing and Mixture-of-Experts conclusions from design discussion, and adopts a maximalist-but-bounded posture throughout. For this project, "maximize without diminishing returns" resolves to maximizing worst-group quality, the parity metric, rather than raw size or raw hours, because the mission is the tail. Every lever now carries an explicit plateau, collected in Section 16 as a decision ledger. Cloud (RunPod) is assigned to the parallelizable, time-bound jobs that gate iteration speed, with an attended-then-unattended split made explicit in Section 7. The thesis, scope, and gate-driven phases are unchanged from v2.
>
> *(v2 added the wide legal data net, global dialect coverage, the audio-inspection pipeline, the N-best inter-stage contract, the encoder-as-param-sink minimization story, and the related-work section.)*

---

## 0. Thesis, the cloud question, and what "maximal" means here

Two custom small models in series:

1. A distilled multilingual acoustic model that transcribes literally, with per-segment language tags.
2. A custom instruction-tuned repair model that reconstructs intent, restores punctuation, and breaks the stream into sentences.

The edge is a custom distillation tuned for the accents and noise that matter, a custom repair model trained on broken-to-clean and unsegmented-to-segmented pairs, and parity training so the system is best, not worst, for speakers who sit in the tail of the data.

**On cloud versus local:** training is firmly cloud, inference stays local. The corpus runs to terabytes and distillation needs datacenter GPUs, but the point of distillation is to compress that into a small model. So the master corpus and all training live on RunPod, and the deployable artifact is a small quantized model that runs locally for the privacy and accessibility benefits. The cloud cost is paid once at training time; users pay nothing and send nothing. An optional cloud inference path exists (serverless, full-fidelity assurance mode), but the design intent is local.

**What "custom" and "maximal" mean, stated up front.** Base Whisper is the teacher, not the product. The shipped artifact is rebuilt and compressed against that teacher. Two refinements define the maximalist posture in v3:

- **The organizing rule: spend parameters where they buy worst-group accuracy, starve them where they only buy average or size.** The encoder (accent robustness), coverage (filling thin accent and fluency cells), and repair-on-broken-input get the budget. Decoder depth, instructor size beyond the task's needs, quantization aggression, and total parameter count do not, because past their plateaus they cost latency, memory, or tail accuracy for no worst-group gain.
- **Two shipped tiers.** A **flagship** tier optimized for quality, which protects the encoder, uses a gentler quantization, and offers a larger instructor option, and which fits an 18GB machine comfortably regardless. A **min-size** tier for constrained devices, which shears the encoder hard and quantizes aggressively. The maximalist directive makes the flagship the primary deliverable; min-size is the secondary export, not the design center. This reverses the v2 default, where size minimization led; here quality leads, and size minimization is a separate export path.

## 1. Scope

The data scope drives everything else, so state it plainly.

- **Primary: comprehensive English, globally.** Regional and national dialects and accent families across every populated continent:
  - **North American:** regional US (including Southern American varieties, AAVE, Appalachian, Chicano English), Canadian, and the broad non-native spread inside North America.
  - **British Isles:** English regional, Scottish, Welsh, Irish.
  - **African:** West, East, Southern, and North African accented English (Nigerian, Ghanaian, Kenyan, South African, and more).
  - **South and Southeast Asian:** Indian and broader South Asian English, plus Filipino, Malaysian, Singaporean, and Indonesian English.
  - **Caribbean:** Jamaican and the wider Caribbean spread.
  - **Antipodean:** Australian and New Zealand.
  - **East Asian and European non-native English** organized by first language.
  This breadth is the reason the corpus is large and the reason average WER is the wrong metric (Section 6).
- **Secondary: multilingual and code-switch.** French and Spanish, and the code-switch boundaries between them and English, retained because that was the original motivation and because immigrant speech is frequently code-switched.
- **A named capability: sentence breaking.** Raw ASR over spontaneous, accented, disfluent speech arrives as an unpunctuated, uncased run-on. Restoring punctuation, casing, and sentence boundaries is a first-class task (Section 4).

## 2. System architecture

```
mic 16kHz (or file)
   -> [Stage A: distilled multilingual acoustic model]  -> literal tokens + per-segment language tags + ASR confidence + N-best
   -> [Stage A.5: segmentation + punctuation restoration] -> punctuated, cased, sentence-split text
   -> [Stage B: repair / instruct model]                -> cleaned intent + normalized text + detected languages + confidence + faithfulness flag
   -> [Stage C: interaction layer]                      -> clarify (low confidence) | act | speak back
```

Stage A.5 can be a dedicated tiny token-classification model or folded into Stage B's responsibilities (Section 4).

**The N-best contract.** Stage A emits its top-N decoding hypotheses, not just the single best transcript, because the Generative Error Correction literature (Section 15) shows the repair model corrects far better when it sees the alternatives, including tokens that never reached the single best path. Stage B treats the N-best list as evidence.

Inter-stage contract is strict JSON, not free text, so every stage is debuggable and benchmarkable:

```json
{
  "literal": "so basically right i went to the the shop innit",
  "nbest": [
    {"text": "so basically right i went to the the shop innit", "score": -0.41},
    {"text": "so basically right i went to the shop in it", "score": -0.55}
  ],
  "segments": [{"text": "...", "lang": "en", "conf": 0.71}],
  "asr_conf": 0.66,
  "provenance": {"sample_rate": 16000, "duration_s": 3.2}
}
```

## 3. Stage A — the distilled acoustic model

Distillation works because of structure: the encoder runs once per clip, but the decoder runs autoregressively per token and dominates inference time, so cutting decoder depth cuts latency without gutting acoustic quality.

The Distil-Whisper template: copy the full encoder and freeze it, keep only two decoder layers initialized from the teacher's first and last decoder layers, discard the rest, train on a weighted sum of KL divergence between student and teacher plus cross-entropy against teacher pseudo-labels. Roughly 5.8x faster at about half the parameters, within about one percent WER out of distribution. That is the baseline to beat.

Worth noting where the teacher sits: large-v3-turbo is itself a distilled large-v3 produced by exactly this move, cutting the decoder from 32 layers to 4 while keeping the full encoder, which is why turbo is still 809M and why the encoder is the parameter sink. Babel's Stage A is "turbo, but redone on our accented tail," with the additions below.

### 3.1 Multi-teacher pseudo-labeling with consensus (maximal label quality)

The student inherits robustness only from what the teacher labels correctly, so label quality on the tail is the highest-leverage cheap lever, and v3 maximizes it:

- **Primary teacher: Whisper large-v3** (1.55B, 32 decoder layers, strong English plus French and Spanish). The student is small regardless of how large the teacher is, so use the largest.
- **Breadth teacher: a very broad multilingual model** (for example Meta's Omnilingual ASR) purely as a labeling teacher for accents large-v3 is weak on. It never ships, so its size is free.
- **Consensus filtering.** Keep clips where the teachers agree (low WER between their transcripts); on sharp disagreement, route the clip to human spot-check or the eval-only pool rather than training on a noisy label. This is the cheapest large gain on hard accented audio, and the disagreement signal also flags which accent cells the teachers themselves struggle with, which feeds acquisition (Section 8).
- **Sequence-level KD.** Distill from the teacher's N-best or output distribution, not only its 1-best, so the student learns the distribution rather than a point estimate.
- **Plateau:** two teachers plus a consensus gate. Requiring three or more teachers to agree starves the corpus of exactly its hardest, most valuable clips, which is a worst-group loss disguised as a quality filter (Section 16).

### 3.2 Encoder posture (the maximalist reversal)

For the flagship tier, **protect the encoder.** It is the organ that carries accent robustness, the artifact fits 18GB whether or not the encoder is sheared, and the disk saved by gutting it costs precisely the robustness the project exists for. So the flagship shears the encoder only modestly, if at all, and spends its parameter budget there.

The decoder is cut aggressively (two to four layers) in both tiers, because that is a near-free latency win that does not touch acoustic quality.

Aggressive encoder shearing, head pruning, and layer merging (the BaldWhisper line) move to the **min-size tier** only, where a smaller device justifies trading some tail robustness for footprint. Section 16 records the boundary: shearing the encoder past roughly a third starts to cost worst-group accuracy.

### 3.3 Routing for parity (a constrained, memory-cheap mixture of experts)

Replace feed-forward blocks with conditional routing modules gated per accent family, with a gate budget so no group starves the others (the Multilingual DistilWhisper approach, generalized from language to accent family since this is an English-primary product). This is the structural lever for cross-group parity.

- **Granularity: one expert per accent family, roughly six to ten families**, not one per individual accent. Per-accent experts starve on thin per-cell data and bloat the model. Family-level grouping is the sensible ceiling.
- This is the correctly-placed version of the Mixture-of-Experts instinct: it is conditional computation *inside* the acoustic model, where accent actually lives, and it adds capacity without the memory cost of a monolithic MoE (Section 10).

### 3.4 The specialist fork (decide in Phase 3)

Recent tiny-ASR work (Moonshine) found that at very small sizes, monolingual or narrowly specialized models beat one multilingual model, because a tiny model lacks the capacity to host many languages well. This opens a fork: instead of one multilingual model with routing gates, ship a small family of accent-family specialists plus a model-level router that loads one on demand. The routing-gate design is the middle path; the specialist extreme is worth a head-to-head benchmark before committing. Model-level routing loads only the expert you need, which saves memory rather than compute and so fits the local budget (Section 10).

**Parity-guaranteed mode (optional).** Distil-Whisper pairs with full Whisper for speculative decoding: the small model proposes, the big model verifies, roughly 2x speedup while mathematically guaranteeing the full model's outputs. Ship as an optional high-assurance mode, the natural home for the optional cloud-inference deployment.

## 4. Stage A.5 / sentence breaking

ASR output for spontaneous accented speech lacks punctuation, casing, and sentence boundaries, and contains disfluencies. Long audio also exceeds Whisper's 30-second window and must be chunked and stitched, creating boundary sentences that span chunks.

- **Punctuation and casing restoration.** A token-classification head labeling each token with trailing punctuation and casing. Dedicated small model or a head on the repair model.
- **Sentence boundary detection.** Falls out of punctuation restoration, with a fallback model for ambiguous run-on boundaries.
- **Long-form stitching.** Chunked long-form decoding (overlapping chunks in parallel, then joined) for speed, or sequential long-form (sliding window guided by timestamps) for accuracy, reconciling sentences that straddle seams.

**Decision in Phase 1:** dedicated segmentation model versus folding it into the repair model. Prototype folded-in (simpler, full context), split out only if the benchmark shows segmentation quality suffering from the repair model's other duties.

## 5. Stage B — the repair model (the instructor)

Job: take the punctuated, segmented transcript plus the N-best list, language tags, and confidence, and return the structured intent object. Clean grammar, resolve slang, untangle code-switching, refuse to invent meaning that was not there. This is an instance of Generative Error Correction (Section 15), a documented field with open datasets and published results.

### 5.1 Sizing (folded in from design discussion)

The instructor is a separate small instruct LLM. Whisper's size does not constrain it; the only shared constraint is local RAM, which the stack splits. On an 18GB machine, after the acoustic model (quantized, roughly half a gigabyte to a gigabyte resident), segmentation (tiny or folded in), and a few gigabytes for KV cache, audio buffers, and the OS, roughly 12GB remains for the instructor. At q4 that maps to 3B near 2GB, 8B near 5GB, 14B near 9GB.

- **Default: a fine-tuned 3 to 4B dense model.** The repair task is narrow, the GER literature got strong results with 7B-class models, and QLoRA does well on smaller models precisely because the task is scoped. The quality curve flattens hard past roughly 4B for this job.
- **Flagship max-quality option: a dense 7 to 8B model**, for harder out-of-distribution input. Fits comfortably alongside a sub-gigabyte acoustic model.
- **Ceiling: do not exceed 8B locally.** 14B is a stretch that costs tokens-to-first-answer for marginal repair gain. Section 16 records the plateau.
- **Dense, not MoE, locally** (Section 10 for the reasoning). Per-accent specialization, if wanted, lives in Stage A routing, not here, because the accent is gone by the time text reaches the repair model. The repair model sees text carrying first-language interference patterns, which one dense fine-tune handles off the per-L1 synthetic pairs.

### 5.2 Adaptation and mechanism

- **Inputs that matter:** feed the full N-best list, not just the top hypothesis. The model recovers tokens missing from the single best path when it can see the alternatives. Close to free accuracy.
- **Adaptation:** QLoRA fine-tune on broken-to-clean, N-best-to-clean, and unsegmented-to-segmented pairs. Where a public GER dataset (for example the HyPoradise N-best corpus) is license-compatible, warm-start on it before fine-tuning on the tail-specific pairs.
- **Optional confidence signal (from RobustGER):** condition the repair on a scalar encoding how much the N-best hypotheses disagree, so the model leans harder on linguistic priors when the acoustic stage was unsure.
- **Quantization:** q4_K_M GGUF for the min-size tier, q5 or q8 for the flagship, reached via quantization-aware fine-tuning rather than post-hoc (Section 10).
- **Faithfulness mechanism:** a round-trip check; re-render the cleaned intent toward the input and compare, tripping a `faithful: false` flag on large semantic drift, forcing a clarify rather than a confident wrong answer.

### 5.3 Synthetic data generation is a cloud time-efficiency job

Generating millions of per-L1 broken-to-clean pairs and synthesizing accented TTS audio is parallel LLM and TTS inference, and it gates how fast Stage B improves. This is RunPod work (Section 7), not a laptop overnight job, and it is where cloud most directly buys wall-clock.

## 6. Parity training (defined four ways)

Parity is the headline requirement. Four senses, all designed for.

1. **Teacher-student parity.** The student reproduces the teacher. Enforced by the KL term during distillation, verifiable exactly by the speculative-decoding mode. The only sense that can be made mathematically exact.
2. **Cross-dialect and cross-lingual parity.** Every accent family, and English, French, and Spanish, should work equally well, not well on average. Enforced by balanced sampling across groups, the conditional routing with a gate budget, and a regularizer penalizing the variance of per-group loss. The metric is the gap between best and worst group, not the mean. The public data shows why: strong models near 3 percent WER on clean US English and near 20 percent on diverse accents, a roughly sevenfold gap the average hides.
3. **Cross-register / fluency parity.** Native and non-native, fluent and broken, clean and noisy served well. Framed as distributionally robust optimization: stratify into fluency and noise tiers and optimize the worst group.
4. **Literal-intent parity (faithfulness).** No hallucination. Penalize output content unsupported by the input.

One-line objective: optimize the worst group, regularize the per-group gap, bound hallucination. Average accuracy is a vanity metric for this product, and "maximize without diminishing returns" means maximizing the worst group until the gap closes or the average starts to collapse, not maximizing the mean.

## 7. Cloud and training infrastructure (RunPod)

### Compute

- **Distillation runs:** A100 80GB or H100 pods. A single-language distil-whisper has been reported around three and a half days on one A100 80GB; broad multi-dialect English with more data and epochs is longer and justifies multi-GPU to cut wall-clock.
- **Pseudo-labeling at scale:** running the teachers over terabytes is a large batch-inference job, likely a bigger cumulative GPU cost than the distillation. Embarrassingly parallel, so it is the ideal candidate for Community Cloud spot with checkpointing.
- **Repair-model QLoRA:** small and cheap, a single mid-tier pod for hours.

### Cost shape (directional, verify before committing; GPU prices drift)

- A100 80GB roughly $1.19/hr Community versus about $1.89/hr Secure; H100 SXM around $2.69/hr on-demand; RTX 4090 around $0.34/hr Community for cheap experiments.
- A 24-hour A100 run lands near $21 on Community Cloud, which makes iteration affordable and means the constraint on iteration is wall-clock, not money.
- Use Community Cloud (spot) for batch jobs and one-off training that can restart from a checkpoint; reserve Secure Cloud for runs that cannot tolerate interruption.
- Default new-account spending cap near $80/hr, fine here but worth knowing before a large multi-GPU launch.

### Storage strategy (the terabyte problem)

Network Volumes run roughly $0.07 to $0.14 per GB per month, so a 10 TB corpus on a network volume is on the order of $700+ per month, and stopped volume disks bill at double. The pattern that avoids that:

- Keep the master corpus in cheap object storage (Cloudflare R2, Backblaze B2, or AWS S3), not on a RunPod volume.
- Shard into WebDataset tar shards so it streams efficiently.
- Stream or stage shards to the pod's local disk on demand, keeping only a working network volume for checkpoints and the small model artifacts.
- Delete network volumes the moment a run ends.

### What goes to cloud, and the attended split (the time-efficiency posture)

The principle: anything embarrassingly parallel, GPU-bound, and time-bound runs on RunPod spot with frequent checkpointing, because wall-clock gates iteration and a full day of A100 is roughly $21.

To cloud, unattended:

- Teacher pseudo-labeling over terabytes (the largest single line item, fully parallel).
- Multi-teacher consensus labeling (more GPU, still parallel).
- Synthetic pair generation and accented TTS synthesis (parallel inference, Section 5.3).
- The multi-dialect distillation run (multi-GPU to push wall-clock from days toward hours).
- Parity training runs.

Attended, human-reviewed:

- Label-quality sampling and the consensus-disagreement triage.
- The parity-gate review at each phase boundary.
- The encoder-shear-versus-robustness call for the flagship.

Run an overnight posture: kick a labeling or distillation job before stopping, checkpoint often so a spot interruption costs minutes, and review the morning readout. Cloud burns wall-clock while you are away; the human-review points sit at the gates, not in the batch loop. This is the attended-then-unattended pattern, applied to a speech pipeline.

## 8. Data procurement (the terabyte bottleneck, with the legal net widened)

The need is the tail: accented, dialectal, non-native, disfluent, code-switched, noisy audio with transcripts. Strategy is broad permissive corpora, plus the widest legally clean harvest, plus heavy synthetic augmentation. The maximalist target is **coverage, not raw hours**: the marginal value is in new accent families and new fluency and noise cells, not more hours of a register already covered (Section 16).

### 8.0 The license-and-provenance gate (runs first)

Every clip enters through a provenance gate before any compute touches it, recording per clip: source, license, license URL, attribution string if required, and a redistribution flag. Anything without a clear permissive basis is tagged eval-only and never enters training. The gate writes a ledger row per clip, which is also the parity-coverage table (Section 8.4). The posture: train only on Creative Commons, public-domain, and explicitly licensed material, treat ambiguous as eval-only, keep the ledger so any clip's basis can be produced on demand. Whether model training itself is fair use is unsettled and being litigated; the permissive-only posture does not depend on that question resolving favorably.

### 8.1 Seed and evaluation corpora (by region)

Each is permissively licensed or has a clearly licensed subset; verify the exact license at ingestion, since some carry share-alike or non-commercial terms that change how the artifact can ship.

- **Backbone and metadata.** Mozilla Common Voice (CC0, rich accent and demographic metadata, the spine of parity stratification). The People's Speech (tens of thousands of hours, permissive, a realistic path to terabyte English scale).
- **British Isles and broad accent.** EdAcc (CC-BY-SA, conversational, first- and second-language varieties, an excellent parity eval because strong models do badly on it). British Isles Speaker dataset. IViE. VCTK.
- **African.** AfriSpeech-200 (around 200 hours, 120 African accents across 13 countries, open source). NCHLT and other African-English sources.
- **South and Southeast Asian.** SVARAH and NPTEL-derived Indian English sets, plus Southeast Asian English where licensing allows.
- **North American, including Southern and AAVE.** CORAAL, Switchboard, Fisher, regional Southern sources. LibriSpeech as clean baseline only.
- **Antipodean and Caribbean.** Australian and New Zealand sources; Caribbean varieties (EdAcc covers some Jamaican).
- **Non-native by first language.** L2-ARCTIC. VoxPopuli (multilingual, accented, European Parliament public proceedings).
- **Code-switch.** Bangor Miami (Spanish-English, word-level tags). Fisher Spanish. SEAME if scope extends to Mandarin-English.
- **General large English.** GigaSpeech, TED-LIUM, AMI (British meetings).

### 8.2 The widest legal harvest (the social-media question, answered honestly)

Off the table: broad scraping of YouTube, TikTok, Instagram, and similar. It violates their terms of service and most of the content is copyrighted. The plan does not do this.

Legitimately harvestable, and genuinely a wide net:

- **Creative Commons media on otherwise-closed platforms.** Creators can license a video CC-BY, and that subset is filterable and reusable with attribution. A harvester restricts strictly to the CC-BY pool and honors attribution and share-alike in the ledger. The legal sliver of social-media audio, real if smaller than the open web implies.
- **Creative Commons and public-domain podcasts.** Many feeds carry CC licenses; spontaneous, conversational, accent-diverse, exactly the register we lack. Harvest by license, not popularity.
- **Public-record government and civic speech.** The underrated jackpot for spontaneous accented speech. US federal works are public domain; many council meetings, hearings, court proceedings, and legislative sessions are public record and openly released. Spontaneous, multi-speaker, accent-rich (real communities), often free of copyright. This is how VoxPopuli was built.
- **Wikimedia Commons and the Internet Archive.** Both host audio under clear, machine-readable licenses; harvest only permissive items, recorded per the ledger.

Synthetic data is the primary scale lever; the harvest fills dialect gaps the licensed corpora miss without touching anything off-limits.

### 8.3 Synthetic data

For the repair and segmentation models, you mostly need text pairs an LLM can generate at scale:

- Perturb clean transcripts deterministically: drop articles, phoneticize, inject first-language interference per L1 (so the broken English is realistic for a given accent group), insert code-switch fragments at realistic boundaries, strip punctuation and casing for segmentation pairs.
- Synthesize audio with accented and multilingual TTS to manufacture pairs in scarce registers; accent-conversion TTS can target specific families on demand to backfill thin cells.
- Round-trip and back-translation tricks for code-switched utterances.

Synthetic data carries its own bias, so the evaluation set is always real and held out, and synthetic volume plateaus when the real held-out eval stops improving (Section 16).

### 8.4 Data parity bookkeeping

Maintain a ledger of hours per accent family by fluency tier by noise level, fed by the pipeline, and fill gaps on purpose. In v2 and onward the coverage table and the license ledger are the same artifact, so legality and parity are tracked together. The consensus-disagreement signal from Section 3.1 flags which cells the teachers themselves find hard, which directs acquisition.

### 8.5 The sorting and inspection pipeline

Every clip runs this gauntlet. Steps 0 and 1 are the audio-inspection gates.

0. **License gate.** No license, no entry.
1. **Acoustic quality inspection.** Reject or quarantine on objective defects (effective bandwidth below roughly 8 kHz, heavy clipping, extreme codec artifacts, music or non-speech dominance, channel dropouts). "Noisy" is not "defective": genuine background noise and far-field speech are kept and tagged as a noise tier, because the product must work there. The filter removes broken files, not hard-but-real audio.
2. **Voice-activity detection and segmentation** into utterance-length clips, retaining timestamps for stitching.
3. **Teacher pseudo-labeling** (multi-teacher, Section 3.1). Keep existing captions where present.
4. **Per-segment language identification**, surfacing code-switch boundaries.
5. **Quality filter by WER heuristic.** Compare existing caption to pseudo-label, discard above a 10 to 20 percent threshold. The single filter that keeps the corpus clean, exactly how Distil-Whisper's data was curated.
6. **Accent and fluency classification** to stratify into the parity tiers.
7. **Deduplication, PII scrubbing, profanity policy.** Content-hash dedup across millions of files, audio fingerprinting for re-uploads, a scrub pass for personal data.

## 9. Rust or Python, honestly, regarding speed

Verdict: Python for everything that touches training and the data pipeline, Rust for the shipped inference engine. Hybrid, split cleanly by component.

**Training and distillation (RunPod): Python.** PyTorch, Transformers, the distillation tooling, the routing-gate surgery, all Python and CUDA. There is no Rust ML training ecosystem worth using. Python's interpreter speed is irrelevant because the work is GPU-bound.

**Data pipeline (terabyte sort and filter): mostly Python.** The expensive steps are GPU-bound (pseudo-labeling, language ID, fluency classification) and I/O-bound (decoding terabytes). Rust helps only at proven pure-CPU streaming hotspots (audio decode and resample at scale, content-hash dedup, sharding into tar shards). ffmpeg plus good Python, or a Rust extension via PyO3 for a proven hotspot, covers it. Build in Python, profile, drop only genuine hotspots into Rust.

**Shipped inference engine: Rust.** For a small, quantized, low-latency, single-binary local app, Rust gives no Python runtime to package, lower memory overhead, predictable latency without garbage-collection pauses, and trivial single-binary distribution. Paths: HuggingFace candle (Rust-native), or GGUF weights through Rust bindings over whisper.cpp and llama.cpp. Both slot into existing instincts (a Go runtime in TailorAI, a Swift and Rust spine in Quintessence), so a Rust inference core could be a shared engine across projects.

**Bottom line.** Python where the GPU dominates, Rust where the user waits.

## 10. Parameter minimization and quantization (two tiers, with the MoE verdict)

The reframing from v2: post-hoc quantization is the easy part, and the higher-leverage work is rebuilding the parts that hold the parameters. v3 organizes this around the two tiers and pins the quantization floor.

### 10.1 Where the parameters are, and the tier split

Distil-Whisper's two-decoder-layer headline is a latency win; it keeps the full encoder, which is the larger share of parameters. So the encoder is the frontier for size, and the two tiers diverge there:

- **Flagship:** protect the encoder (Section 3.2), spend the budget on robustness, accept the larger artifact. It fits 18GB regardless.
- **Min-size:** encoder head shearing and layer merging (BaldWhisper line), plus low-rank factorization, for constrained devices, accepting some tail-robustness loss.

### 10.2 The tokenizer and vocabulary cut (both tiers)

Whisper's multilingual vocabulary, on the order of fifty-thousand tokens, ties up real embedding and output-projection parameters. Scope is English plus French plus Spanish, so prune the vocabulary to the tokens those languages use and re-tie the matrices. A clean parameter cut with near-zero quality loss on in-scope languages, specific to the fact that Babel is not trying to be all of Whisper.

### 10.3 Quantization as training, with a floor

- **Quantization-aware distillation.** Simulate the target quantization during distillation so the student learns weights robust to it, rather than training then quantizing and hoping. The difference between "quantized Whisper" and "a model built to be tiny."
- **Floor: q4 for the min-size tier, q5 or q8 for the flagship.** Below q4 the acoustic model's tail WER drops off a cliff, and the tail is the population that cannot be degraded, so aggressive sub-q4 quantization is reserved for nothing; it sits below the plateau (Section 16). The flagship fits 18GB at q5 or q8, so there is no reason to quantize it harder than quality wants.

### 10.4 The Mixture-of-Experts verdict (folded in from design discussion)

A custom MoE is the wrong bet for the local artifact, and the reason is the constraint that governs the whole project: **MoE saves compute, not memory.** Only a couple of experts fire per token, but every expert sits resident in RAM, because the router cannot know which will fire until it routes. An 8x3B MoE is roughly 24B of weights (about 6B active), needing on the order of 12 to 15GB just for weights at q4, to deliver the latency of a 6B model that a dense 6 to 7B gives at half the memory. Streaming experts off disk to fit limited RAM reintroduces per-token disk latency and kills real-time.

So:

- **Local: dense.** Every parameter does work on every token, and you pay for every byte you load regardless.
- **Cloud assurance tier: MoE is fine and natural**, because memory is plentiful there and compute efficiency at scale is the goal.
- **The local "mixture of experts" is model-level routing among small dense specialists loaded on demand** (Sections 3.3 and 3.4), which saves memory instead of compute, plus the in-model accent-family routing gates. The MoE instinct is right; it belongs in Stage A's conditional computation and in model-level specialist routing, not in a monolithic resident MoE.

### 10.5 An architecture escape hatch for the min-size tier

- **A Moonshine-class architecture** as the target for an English-only or per-accent-family specialist, since tiny specialized ASR around 27M parameters has beaten much larger Whisper variants in its niche, with variable-length windowing that avoids forcing short utterances into a 30-second frame.
- **A CTC encoder-only path** (wav2vec2 or Parakeet-style) as a fast tier: no autoregressive decoder, smallest and fastest acoustic option, at the cost of weaker punctuation, weaker rare-word handling, and less robustness, with Stage B doing more of the linguistic lifting.

### 10.6 Headroom and latency

- **Headroom:** the flagship stack fits inside 18GB with real margin, so real-time on a consumer machine is realistic with room for the assurance mode.
- **Latency to instrument:** real-time factor well under 1.0 for acoustic, tokens-to-first-answer for repair, on fixed hardware. Report parameter count and on-disk size per tier; a claim without the number is marketing.

## 11. Evaluation (this becomes a public bench)

- Intent-match accuracy against gold cleaned intents.
- Per-accent-group and per-language WER, and the parity gap (worst group minus best), against a hard accent benchmark (EdAcc is the obvious reference, since strong models visibly fail on it).
- Worst-group accuracy across fluency and noise tiers.
- Sentence-segmentation quality (boundary F1, punctuation and casing accuracy).
- Over-correction and hallucination rate from the faithfulness check. The number that distinguishes a forgiving system from a confidently-wrong one, reported prominently.
- Tokens-to-first-answer and real-time factor on fixed hardware, plus parameter count and on-disk size per tier.
- A determinism sanity loop run several times before benchmarking, because Metal at temperature zero is only partly byte-identical and a bench assuming determinism it lacks will lie.

Two traps: no evaluation utterances leaking into training, and no trusting a model that emits suspiciously identical outputs across runs or tasks, which is a contamination or grading-artifact smell rather than skill. Novel, held-out, hand-built utterances only.

## 12. Build phases (gate-driven)

- **Phase 0 — glue MVP, no training.** Off-the-shelf distil-whisper plus an off-the-shelf small instruct model plus a prompt, with the N-best contract wired from day one. Lock the JSON contract. Gate: broken speech in, clean segmented intent out, works at all.
- **Phase 1 — synthetic repair and segmentation data, QLoRA.** Generate broken-to-clean, N-best-to-clean, and unsegmented-to-segmented pairs (per-L1), optionally warm-start on a public GER dataset, fine-tune Stage B, decide folded-in versus dedicated segmentation, instrument all parity metrics. Gate: measurable gain over the Phase 0 prompt with the parity gap tracked.
- **Phase 2 — RunPod data pipeline and pseudo-labeling.** Stand up object storage, sharding, the license-and-provenance gate, the acoustic-inspection gate, and the filtering pipeline; run the legal harvest; pseudo-label the terabyte tail with multi-teacher consensus on cheap spot; generate synthetic data in parallel. Gate: a clean, stratified, sharded corpus with an honest coverage-and-license ledger.
- **Phase 3 — custom acoustic distillation on RunPod.** Distill both tiers (flagship protected-encoder, min-size sheared), with accent-family routing, multi-GPU to cut wall-clock, and run the specialist-versus-multilingual fork head-to-head. Gate: custom model matches or beats stock distil-whisper on the held-out accent and dialect set.
- **Phase 4 — parity training.** Group-DRO objective, close the cross-dialect, cross-lingual, and cross-register gaps. Gate: worst-group accuracy and parity gap both improve without average accuracy collapsing.
- **Phase 5 — quantize, minimize, and the Rust runtime.** Quantization-aware fine-tuning (q4 for min-size, q5 or q8 for flagship), the vocabulary cut, the model-level router with a warm generalist fallback; build the Rust inference engine (candle or GGUF bindings); meet RTF, tokens-to-first-answer, and on-disk size targets per tier; wire the optional speculative-decoding assurance mode, with MoE confined to the cloud assurance path. Gate: real-time, single-binary, local, at or under each tier's size budget.
- **Phase 6 — bench and ship.** Publish the benchmark and writeup, parity gap and the size-versus-accuracy curve front and center. Optionally fold into TailorAI as a voice mode, or ship a standalone offline accessibility app.

Cost note: Phases 0 and 1 are cheap and mostly local. Phases 2 and 3 are the cloud spend, and pseudo-labeling terabytes is the largest single line item, which is why it runs on cheap interruptible Community Cloud with checkpointing and the overnight posture (Section 7).

## 13. Accessibility design (the part that makes it matter)

- Interpretive tone, never corrective. The system reconstructs meaning; it does not grade grammar or make anyone feel watched.
- Fully local inference. No data plan required, privacy preserved for users with real reasons to distrust cloud capture. This is also why training is cloud and inference is not: the heavy data work never touches a user.
- The parity guarantee is the ethical spine. The system must work best, not worst, for heavy accents, strong dialects, and broken syntax, because those are the people it exists for.
- Consider a two-way mode: it helps the speaker be understood and helps a listener understand, the actual social situation a non-native or strongly-accented speaker is in.

## 14. Key references

- Distil-Whisper, Robust Knowledge Distillation via Large-Scale Pseudo Labelling: https://arxiv.org/abs/2311.00430 and https://github.com/huggingface/distil-whisper
- Multilingual DistilWhisper (conditional language-specific routing): https://arxiv.org/pdf/2311.01070
- BaldWhisper (head shearing and layer merging): https://arxiv.org/pdf/2510.08599
- Whisper large-v3 and large-v3-turbo (1.55B versus 809M, 32 versus 4 decoder layers, shared encoder, MIT): https://github.com/openai/whisper and https://huggingface.co/openai/whisper-large-v3-turbo
- Moonshine and Flavors of Moonshine (tiny edge ASR, monolingual-beats-multilingual at small scale): https://arxiv.org/abs/2509.02523
- HyPoradise (open GER benchmark, N-best to transcript): https://arxiv.org/abs/2309.15701
- Whispering LLaMA (cross-modal generative error correction): https://aclanthology.org/2023.emnlp-main.618
- Speech Accessibility Project Interspeech 2025 Challenge: https://arxiv.org/abs/2507.22047
- EdAcc, Edinburgh International Accents of English Corpus (CC-BY-SA): https://huggingface.co/datasets/edinburghcstr/edacc
- AfriSpeech-200 (Pan-African accented English): https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00627/118796/
- Mozilla Common Voice: https://commonvoice.mozilla.org
- The People's Speech (MLCommons): https://mlcommons.org/datasets/peoples-speech/
- CORAAL (regional African American Language): https://oraal.uoregon.edu/coraal
- Bangor Miami code-switching corpus: http://bangortalk.org.uk
- HuggingFace candle (Rust inference): https://github.com/huggingface/candle
- RunPod pricing: https://www.runpod.io/pricing

## 15. Related work and positioning

The pieces of Babel exist separately; the integration around the broken-and-non-native population is the open whitespace.

- **Generative Error Correction (GER) is Stage B, already a field.** HyPoradise established the open benchmark for LLM-based ASR correction and showed the model can recover tokens missing from the N-best list. Whispering LLaMA added acoustic features into the LLM and reported large WER improvements over the N-best oracle. RobustGER conditions correction on a noise signal. Implication: Stage B is not a research gamble, the N-best contract is mandatory, and warm-starting on public GER data is sensible. The differentiator is that all of this targets clean or noisy native English; pointing GER at broken, non-native, code-switched intent is the unclaimed direction.
- **Parity-for-accessibility has a flagship, aimed at a different population.** The Speech Accessibility Project, descended from Google's Project Euphonia and backed by an industry coalition (Apple, Google, Amazon, Meta, Microsoft), ran a 2025 challenge on hundreds of hours of disordered-speech data and moved the state of the art. It proves the playbook (a focused dataset plus a public challenge shifts a subfield) and proves the giants invest in this category. It targets speech disability; accent and non-native speech is the adjacent, comparatively open frontier.
- **The accent gap is documented and large.** EdAcc showed strong models near 3 percent WER on clean US English and near 20 percent on diverse accents, worst on Jamaican, Indonesian, Nigerian, and Kenyan English. AfriSpeech-200 supplies 120 African accents. These build the evidence and the eval sets but do not ship a forgiving local fix, which is Babel's lane.
- **Tiny local ASR is proven and sets the target.** Moonshine's tiny models beat much larger Whisper variants in their niche and found small specialists beat small multilingual models, which is why the specialist fork is on the table. Field consensus places Moonshine as the smallest-footprint edge option and large multilingual models (Meta's Omnilingual ASR) as teachers rather than deployables, which is precisely how Babel uses them.

The realistic adoption path is the HyPoradise path, not a licensing fantasy: the benchmark and the parity-first dataset become a reference others cite, and influence (open-source adoption, partnership, or acquisition) follows from being the standard, helped by the largest players already funding the sibling problem.

## 16. Maximalist settings and where they plateau (decision ledger)

The unifying rule: maximize worst-group quality, not average accuracy or raw size. Push each lever to the setting below, and stop at the stated boundary, because past it the lever costs latency, memory, or tail accuracy for no worst-group gain.

- **Teacher count and labeling.** Push to two teachers (large-v3 plus a breadth teacher) with consensus filtering and sequence-level KD. Stop before requiring three or more teachers to agree, which starves the hardest, most valuable accented clips.
- **Coverage.** Push until per-group held-out real eval saturates, filling new accent families and new fluency and noise cells. Stop adding more hours of an already-covered register; raw hours saturate while coverage does not.
- **Encoder capacity (flagship).** Keep the encoder full or near-full. Stop shearing past roughly a third, where worst-group accuracy starts to fall; that loss is the mission failing, not a size win.
- **Decoder depth.** Cut to two to four layers. Stop below two, where coherence degrades. The cut above two is a near-free latency win.
- **Routing experts.** One per accent family, roughly six to ten. Stop at per-individual-accent experts, which starve on thin data and bloat the model.
- **Instructor size.** Default 3 to 4B dense, flagship option 7 to 8B dense. Stop at 8B locally and well short of 14B; the narrow repair task saturates past about 4B and larger models cost tokens-to-first-answer for marginal gain.
- **Synthetic pairs.** Generate heavily across L1 patterns, accent families, and fluency tiers. Stop when the real held-out eval stops improving; that is the synthetic-bias ceiling.
- **Quantization.** q5 or q8 for the flagship, q4 for the min-size tier. Stop below q4, where the acoustic model's tail WER drops off a cliff for the population that cannot be degraded.
- **Parity training.** Push worst-group accuracy up with the Group-DRO objective and the per-group variance penalty. Stop when the best-worst gap closes or the average starts to collapse.
- **Faithfulness pressure.** Tighten the round-trip threshold until the clarify rate becomes annoying in practice; that point is the plateau, because over-caution trades one failure mode for another.
- **Total parameters and MoE, locally.** Do not maximize. Memory is the binding constraint on device, and total parameter count and resident MoE experts cost memory without buying worst-group accuracy. Maximize parameter count only in the optional cloud assurance tier, where memory is not the constraint.

## 17. Absolute moat strategy

The neglected space is the entry point, not the moat. "Accents and broken speech are underserved" gets the project into an uncrowded lane, but it is not defensible by itself. The moat is the system of assets that compounds around that lane:

- A licensed, queryable tail-speech corpus with provenance and parity metadata.
- A hard benchmark others trust because it is real, held out, and organized around worst-group performance.
- A detailed error taxonomy that turns every failure into a data, model, runtime, or UX decision.
- An active-learning loop that finds the next most valuable hour of audio instead of hoarding raw hours.
- A local runtime that makes the model useful in the settings where cloud speech products are least trusted.
- A confidence-gated architecture that spends compute only where quality needs it.
- A product feedback loop that captures failures respectfully, privately, and with consent.
- Distribution through a clear moral promise: understand me without correcting me, grading me, or sending me to the cloud.

The moat is boring on purpose. Big labs can train bigger models, but they are structurally drawn toward broad averages, generic benchmarks, and cloud APIs. Babel wins by making the tail measurable, making the tail improve, and making the tail experience local.

### 17.1 The compounding loop

The core loop:

1. Find the failure cell.
2. Determine whether it is an acoustic, language, segmentation, repair, faithfulness, or UX failure.
3. Acquire or synthesize data targeted to that cell.
4. Label with multi-teacher consensus and human review where disagreement is high.
5. Train only the model component responsible for that failure.
6. Evaluate on held-out real data for the same cell and neighboring cells.
7. Ship only if worst-group quality improves without violating speed, memory, privacy, or faithfulness gates.
8. Feed the remaining failures back into the acquisition queue.

This loop is the company. The model artifacts are snapshots of the loop, not the permanent advantage.

### 17.2 The defensible assets

**Asset 1: the coverage ledger.** A table of every usable clip, its source, license, speaker/accent metadata, language mix, fluency tier, noise tier, transcript provenance, and split assignment. This is both the legal defense and the product roadmap.

**Asset 2: the hard eval set.** Real, manually checked, speaker-disjoint, source-disjoint, license-clean utterances across the cells that general ASR fails. This eval set is never synthetic, never pseudo-labeled, and never used for training.

**Asset 3: the failure taxonomy.** Every bad output is tagged. Example tags:

- Acoustic miss: phoneme substitution, dropped consonant cluster, vowel shift, prosody confusion.
- Dialect miss: dialect word treated as error, dialect grammar over-corrected, slang mistranscribed.
- L1 interference: article drop, tense transfer, word-order transfer, phonetic spelling.
- Code-switch miss: wrong language tag, boundary missed, borrowed word normalized away.
- Segmentation miss: run-on, false boundary, punctuation that changes meaning.
- Entity miss: name, place, medicine, product, organization, domain term.
- Repair miss: hallucinated meaning, over-cleaned dialect, under-repaired literal transcript.
- UX miss: should have clarified, clarified too often, confidence was wrong.

**Asset 4: the synthetic generator.** A controlled generator for L1-specific broken-to-clean pairs, code-switch patterns, punctuation restoration, and accent-targeted TTS. Its value comes from calibration against real held-out eval, not from volume.

**Asset 5: the runtime Pareto frontier.** The measured size/speed/quality curves for every tier and hardware target. Competitors can say "small" or "fast"; Babel should publish the frontier and make the trade-offs explicit.

**Asset 6: the feedback consent layer.** Opt-in local capture of failures, with redaction and a clear choice about whether audio, transcript, or only error metadata is shared. The default is private; the improvement loop is earned, not extracted.

### 17.3 What is not a moat

- A generic Whisper wrapper.
- A large prompt around a small LLM.
- Average WER improvements on clean English.
- Raw hours without coverage metadata.
- Synthetic volume that is not validated against real held-out speakers.
- Cloud-only quality.
- A monolithic local MoE that looks clever but blows the memory budget.
- A one-time fine-tune with no failure loop.

### 17.4 Moat metrics

Track these like product revenue:

- **License-clean tail hours** by accent family, L1, fluency tier, and noise tier.
- **Coverage entropy:** whether data is spread across cells instead of concentrated in the easiest sources.
- **Hard-cell closure rate:** how many named failure cells improve per month.
- **Worst-group delta:** the gap between best and worst group on WER, intent accuracy, and hallucination.
- **Pareto movement:** quality per resident GB and quality per second of latency.
- **Human-review leverage:** eval gain per hour of human review.
- **Synthetic leverage:** eval gain per million synthetic pairs, measured only on real held-out data.
- **Clarify precision:** how often a clarification was actually needed.
- **Trust incidents:** hallucinations, over-corrections, privacy surprises, or dialect erasure reports.

If a metric does not make the moat harder to copy, it is operational, not strategic.

## 18. How to increase everything at once

The project has several goals that look contradictory:

- Higher quality.
- Smaller resident parameter count.
- Faster response.
- Better privacy.
- Lower cloud cost.
- Broader coverage.
- Better faithfulness.

The way to increase them together is not to maximize every component. It is to route compute by uncertainty and put each parameter where it buys the most worst-group quality per resident byte.

The governing metric should be:

```
moat_gain = worst_group_quality_gain / (resident_memory_gb * latency_seconds * license_risk * hallucination_risk)
```

Not literally as a single scalar for publication, but as an engineering instinct. A change that improves average quality by 1 percent while increasing resident memory by 3GB and worsening a hard accent group is a bad change. A change that improves Nigerian, Jamaican, Indian, and code-switched utterances by 4 percent while adding 100ms only on uncertain segments is a great change.

### 18.1 The Pareto rule

Every experiment must report:

- Worst-group WER.
- Worst-group intent accuracy.
- Parity gap.
- Hallucination or over-correction rate.
- Sentence boundary F1.
- Real-time factor.
- Tokens-to-first-answer for repair.
- Resident memory.
- On-disk size.
- License/provenance impact.

Ship only if the change improves at least one primary metric and violates none of the hard gates. If it violates a gate, it must be tier-specific, not the default.

### 18.2 The hard gates

- **Local-first:** default inference sends no user audio to the cloud.
- **Worst-group protection:** no release can improve average WER while degrading a named hard cell unless that release is explicitly not for that group.
- **Faithfulness:** the repair model must be allowed to say "uncertain" and ask for clarification.
- **License cleanliness:** ambiguous data can be eval-only or research-only, not training for a shipped artifact.
- **Measured speed:** every release reports RTF and repair latency on fixed hardware.
- **Measured size:** every release reports resident memory and on-disk artifact size.

### 18.3 Confidence-gated compute

This is the central trick for quality, speed, and minimum parameters at the same time.

Easy utterances take the cheap path:

```
VAD -> tiny scout -> Stage A small decode -> lightweight repair -> final
```

Hard utterances take the expensive path:

```
VAD -> scout flags uncertainty/accent/noise/code-switch
    -> Stage A with wider beam and N-best
    -> optional specialist acoustic model or protected-encoder flagship
    -> repair model with uncertainty signal
    -> faithfulness check
    -> clarify if needed
```

The expensive path is not a failure. It is the product keeping its promise. The moat is knowing which inputs deserve more compute.

### 18.4 Resident parameters versus shelf parameters

For local inference, the relevant number is not total models on disk. It is resident parameters loaded at once.

Babel can ship a shelf of specialists:

- General English acoustic.
- African-English specialist.
- South Asian English specialist.
- Caribbean/British Isles specialist.
- Code-switch English-Spanish specialist.
- Min-size generic fallback.

Only one or two need to be resident for an utterance. This gives specialization without the RAM cost of a monolithic MoE. It also gives the product an upgrade path: add a specialist for a newly supported population without bloating the default path.

## 19. Quality maximization

Quality means the system correctly understands people who are usually failed by ASR. Average clean-English WER is a sanity check, not the prize.

### 19.1 Quality levers, ranked

1. **Real held-out eval quality.** If the eval is weak, every model decision is theatre.
2. **Label quality on hard cells.** Teacher consensus and human review on disagreement beat more noisy hours.
3. **Coverage of thin cells.** New accent/fluency/noise/code-switch cells beat more hours of already-solved speech.
4. **N-best repair.** The repair model needs the alternatives, not just the top transcript.
5. **Group-aware training.** Balanced sampling, Group-DRO, and variance penalties enforce the mission.
6. **Faithfulness checks.** A model that confidently invents meaning is worse than one that asks.
7. **Calibration.** Confidence must mean something, or the system cannot route compute safely.
8. **Domain personalization.** Names, workplaces, medicines, schools, places, and personal vocabulary often matter more than raw WER.

### 19.2 Gold eval construction

Build the eval before trusting training improvements:

- Speaker-disjoint and source-disjoint from training.
- Real audio only, never synthetic.
- Human transcript plus cleaned-intent target.
- Accent family, L1, fluency tier, noise tier, and code-switch tags.
- Multiple annotators on hard samples.
- A disagreement field, because some utterances are genuinely ambiguous.
- A "should clarify" label for ambiguous audio.

Gold labels should include three targets:

- **Literal transcript:** what was said, including dialect and disfluency.
- **Clean intent:** what the speaker meant, without erasing identity.
- **Interaction decision:** answer, clarify, or abstain.

That third target is the missing product metric. ASR papers usually stop at transcript accuracy; Babel must know when not to act.

### 19.3 Label quality ladder

For each training clip:

1. Existing human transcript, if licensed.
2. Whisper large-v3 pseudo-label.
3. Breadth-teacher pseudo-label.
4. Agreement score between labels.
5. Language and code-switch tags.
6. Acoustic quality tags.
7. Accent/fluency/noise classifier tags.
8. Human review if the clip sits in a high-value cell and teachers disagree.
9. Eval-only quarantine if provenance or label quality is weak.

The expensive human review goes where it buys the most: high-disagreement, under-covered, high-priority cells.

### 19.4 Training quality ladder

- Start with clean supervised distillation.
- Add sequence-level KD from N-best distributions.
- Add balanced sampling so large easy groups cannot dominate.
- Add Group-DRO for worst-group lift.
- Add accent-family routing only after the baseline shows group-specific residual errors.
- Add specialist models only when routing cannot close a hard cell under the resident memory target.
- Add quantization-aware distillation before final export.

No component gets to exist because it is interesting. It earns its place by moving a hard-cell metric.

### 19.5 Repair quality ladder

Stage B is where Babel becomes forgiving rather than merely literal.

Inputs:

- Literal transcript.
- N-best alternatives.
- Segment language tags.
- ASR confidence.
- Disagreement score.
- Optional domain glossary.
- Optional speaker profile, stored locally.

Outputs:

- Cleaned transcript.
- Intent object.
- Sentence boundaries.
- Detected languages.
- Confidence.
- Faithfulness flag.
- Clarifying question if needed.

Training tasks:

- Broken-to-clean correction.
- N-best-to-clean correction.
- Unpunctuated-to-segmented restoration.
- Code-switch preservation.
- Dialect-preserving cleanup.
- Ambiguity detection.
- Entity preservation.
- Refusal to invent unsupported content.

The repair model should not normalize away identity. "Fixing grammar" is not the goal; preserving meaning is.

### 19.6 Quality traps

- Over-cleaning dialect into standardized English.
- Converting code-switching into monolingual English.
- Treating accent metadata as identity truth rather than noisy stratification.
- Letting synthetic pairs define the eval.
- Rewarding the repair model for making fluent nonsense.
- Optimizing WER while harming intent accuracy.
- Improving clean English and calling it accessibility.

## 20. Minimum parameter strategy

The goal is not "fewest parameters." It is "fewest resident parameters that preserve worst-group quality."

### 20.1 Parameter doctrine

- Cut decoder depth before cutting encoder robustness.
- Cut vocabulary before cutting acoustic capacity.
- Cut resident models before cutting shelf models.
- Cut average-case compute before cutting hard-case compute.
- Use specialist routing when specialization saves resident memory.
- Use quantization-aware training, not blind post-hoc compression.
- Keep a protected flagship so the min-size tier has a quality reference.

### 20.2 Parameter levers

**Vocabulary pruning.** Limit token embeddings and output projection to English, French, Spanish, code-switch markers, punctuation, timestamps, and domain tokens. This is a clean cut because the product has a scoped language promise.

**Decoder thinning.** Keep two to four decoder layers. This is the best latency-per-quality trade in Whisper-style models.

**Encoder preservation for flagship.** The encoder holds accent robustness. Protect it unless a measured pruning pass proves a safe cut.

**Structured pruning for min-size.** Prune heads, merge layers, and factorize matrices only under a worst-group eval gate. Unstructured sparsity is less useful unless the runtime actually accelerates it.

**Low-rank factorization.** Apply where matrices are large and sensitivity is low. Measure by layer; do not assume uniform compression is safe.

**Adapter merge.** Fine-tune with LoRA/QLoRA, then merge or export adapters in a way that does not add runtime complexity unless adapters are used for on-demand specialists.

**Shared components.** Specialists can share tokenizer, pre/post-processing, VAD, segmentation, and repair infrastructure. Do not duplicate the pipeline around each model.

**Delayed loading.** Load Stage B only when the utterance needs repair beyond punctuation, or keep a tiny repair head for easy cases and load the larger instructor for hard cases.

**External glossary instead of parameters.** Names, places, domain words, and personal vocabulary should live in a local glossary/retrieval layer where possible, not in model weights.

### 20.3 Tier targets

These are engineering targets, not promises:

| Tier | Purpose | Acoustic posture | Repair posture | Quantization | Main metric |
| --- | --- | --- | --- | --- | --- |
| Scout | Route and early confidence | Tiny VAD/lang/accent/noise classifier | None | int8 or smaller | Correct routing, near-zero latency |
| Min-size | Constrained devices | Sheared/pruned acoustic or tiny specialist | 3B q4 or smaller task model | q4 floor | Lowest resident memory without tail collapse |
| Flagship | Default quality | Protected encoder, thin decoder | 3-4B q5 or q8 | q5/q8 | Worst-group quality per GB |
| Max-quality local | Hard utterances | Protected encoder plus wider beam/specialist | 7-8B dense | q5/q8 | Hard-cell rescue rate |
| Cloud assurance | Optional verifier | Large teacher/speculative verifier | Larger dense or MoE allowed | flexible | Highest confidence, not default privacy path |

The scout tier is important. It lets the product avoid loading or running the expensive path for easy input while still detecting when the hard path is needed.

### 20.4 Parameter experiments to run

- Full encoder versus 75 percent versus 67 percent versus 50 percent on hard-cell eval.
- Two decoder layers versus four decoder layers on latency and rare-word recovery.
- Full vocabulary versus scoped vocabulary.
- One multilingual model versus family specialists loaded on demand.
- 3B repair versus 7B repair on only the hard repair subset.
- q8 versus q5 versus q4 for acoustic and repair, measured by group.
- Dedicated segmentation head versus repair-model segmentation.
- Glossary retrieval versus baked-in domain fine-tune for entity recovery.

Every compression experiment should produce a curve, not a yes/no. The moat is knowing the frontier.

## 21. Speed strategy

Speed is not just runtime vanity. In speech, latency changes whether the tool feels like understanding or translation delay.

### 21.1 Latency doctrine

- Stream everything that can stream.
- Emit partials quickly, revise carefully.
- Run cheap detection before expensive decoding.
- Spend beam width only on uncertain segments.
- Run repair on completed segments, not entire long recordings when avoidable.
- Use overlap and stitching for long-form audio.
- Keep models memory-mapped and warm.
- Make slow paths explicit in the UI when quality requires them.

### 21.2 Speed levers

**VAD first.** Remove silence and non-speech before any model sees it. The cheapest audio is audio not decoded.

**Chunking strategy.** Use short streaming chunks for responsiveness, overlapping chunks for accuracy, and sentence-aware stitching so boundaries do not break meaning.

**Beam gating.** Low beam for high-confidence easy speech, wider beam and richer N-best only when the scout or Stage A confidence says it matters.

**Selective re-decode.** If a long recording has three uncertain segments, re-decode those segments with the expensive path, not the whole file.

**Speculative decoding.** Use the small model to propose and the larger verifier only where assurance mode is requested or confidence is low.

**Batch pseudo-labeling, not batch UX.** Training jobs should batch heavily; live inference should optimize perceived latency.

**Rust runtime.** Keep the shipped path free of Python startup, dependency sprawl, and unpredictable memory behavior.

**Memory mapping.** GGUF-style mmap loading helps startup and lets the OS page efficiently.

**Threading discipline.** Audio capture, VAD, acoustic decode, repair, and UI should not block one another.

**Hardware feature detection.** Metal, CUDA, CPU AVX/AMX, and quantization kernels should be chosen at startup, then logged with the benchmark result.

### 21.3 Reference latency targets

Targets should be reported on named hardware, for example "M-series laptop," "consumer RTX desktop," and "CPU-only laptop."

- Partial caption appears fast enough to feel live.
- Acoustic real-time factor comfortably below 1.0 for the default tier.
- Repair response for short utterances stays below the threshold where conversation feels stalled.
- Hard-path rescue is allowed to be slower, but should be visible and rare.
- Long-form files prioritize total throughput and stitching quality over instant final text.

Do not publish speed without saying the hardware, quantization, beam, model tier, and audio duration distribution.

### 21.4 The two-pass product path

For live use:

1. **Pass 1: fast literal.** Produce a rough transcript and confidence quickly.
2. **Pass 2: selective repair.** Clean, segment, and correct as confidence arrives.
3. **Pass 3: hard rescue.** Only uncertain spans go through wider beam, specialist, or cloud assurance if enabled.

This gives users immediacy without forcing the hardest cases through the cheapest path.

## 22. Data moat

The data moat is not "we have a lot of audio." It is "we know exactly which underserved speech cells we cover, which we do not, and what each clip is legally allowed to do."

### 22.1 Coverage grid

Every clip should land in a grid:

- Accent family.
- Region.
- First language, if known.
- Native/non-native/fluent/broken fluency tier.
- Age band, if licensed and ethical to store.
- Gender presentation, if volunteered and useful for parity.
- Noise tier.
- Microphone/channel tier.
- Register: read, conversational, meeting, phone, classroom, public speech, command, dictation.
- Language mix: English-only, English-French, English-Spanish, other code-switch.
- Transcript type: human, caption, pseudo-label, synthetic.
- License class and redistribution status.

The grid tells the project what to do next. Empty or weak cells drive acquisition; saturated cells do not.

### 22.2 High-value hard cells

Initial priority cells:

- Jamaican and broader Caribbean English.
- Nigerian, Ghanaian, Kenyan, South African, and broader African English.
- Indian and broader South Asian English.
- Filipino, Singaporean, Malaysian, and Indonesian English.
- AAVE and regional Southern/Appalachian/Chicano English.
- Scottish, Irish, Welsh, and regional British English.
- English with Mandarin, Arabic, Spanish, French, Hindi/Urdu, Tagalog, and Portuguese L1 interference.
- English-Spanish and English-French code-switching.
- Far-field public meetings with multiple speakers.
- Phone-quality speech and compressed audio.
- Broken, hesitant, false-start-heavy speech.

These cells are not merely "hard." They are where the product's promise becomes visible.

### 22.3 Acquisition ladder

1. Public permissive corpora with metadata.
2. Public-record civic speech where legal status is clear.
3. CC podcasts and interviews.
4. Wikimedia/Internet Archive permissive audio.
5. Partnerships with schools, community groups, accessibility orgs, and language-learning programs.
6. Opt-in user failure donations, with redaction and clear consent.
7. Targeted paid recording for cells that remain thin.
8. Synthetic augmentation to fill patterns, never to replace real eval.

The partnership layer may become the strongest moat. It gives legally clean, mission-aligned data that broad scrapers will not have.

### 22.4 Data quality scoring

Each clip gets scores:

- License confidence.
- Transcript confidence.
- Acoustic usability.
- Accent metadata confidence.
- Speaker uniqueness.
- Cell rarity.
- Teacher agreement.
- Human-review priority.
- Training eligibility.
- Eval eligibility.

Training samplers should prefer high-value, high-confidence, under-covered clips. Eval should prefer high-confidence real clips and preserve hard ambiguity labels.

## 23. Evaluation and benchmark moat

The benchmark is how Babel becomes legible. The market already understands WER; the neglected population needs a benchmark that punishes systems for failing them.

### 23.1 Babel Bench

Build a public-facing benchmark with these tasks:

- Literal ASR WER by accent family and language mix.
- Clean-intent accuracy.
- Code-switch boundary F1.
- Language-tag accuracy.
- Sentence boundary F1.
- Punctuation and casing accuracy.
- Entity preservation.
- Hallucination and over-correction rate.
- Clarify/answer decision accuracy.
- Real-time factor.
- Resident memory.
- On-disk size.
- Local/offline capability.

The leaderboard should sort by worst-group quality first, then average. That single choice communicates the whole thesis.

### 23.2 Benchmark splits

- **Public dev:** enough examples for people to understand the task.
- **Public test:** labels hidden or delayed.
- **Private hard test:** never released, used for internal release gates.
- **Regression bank:** every real failure that mattered and can be legally retained.
- **Canary set:** newly collected samples used to detect contamination or overfitting.

### 23.3 Anti-cheating and anti-self-deception

- Speaker-disjoint splits.
- Source-disjoint splits.
- Synthetic excluded from test.
- Near-duplicate audio fingerprinting.
- Text search against training transcripts.
- Model output sanity checks across repeated runs.
- Human spot checks of suspicious gains.

The first user of the benchmark is Babel itself. Public credibility comes later.

## 24. Product moat

The product moat is emotional as much as technical: people who are misheard all the time can tell whether a system is helping them or correcting them.

### 24.1 Product principles

- **Forgiving, not corrective.** The system should never make the speaker feel graded.
- **Local by default.** Privacy is part of accessibility.
- **Clarify respectfully.** When uncertain, ask a short question instead of hallucinating.
- **Preserve identity.** Dialect and code-switching are not errors.
- **Let users teach names.** Personal vocabulary should be easy and local.
- **Show confidence carefully.** Expose uncertainty without shaming the speaker.
- **Do not over-automate.** If the system might act on the wrong intent, it should confirm.

### 24.2 First product surfaces

- **Local dictation.** Speak messy, get clean text in any app.
- **Live captions.** Better captions for accents and code-switching, offline.
- **Meeting notes.** Local-first transcription plus intent cleanup.
- **Developer API.** A local JSON contract for applications that need forgiving speech.
- **Accessibility companion.** Two-way mode for a speaker and listener in person.
- **Call-center or support assist.** Agent-side understanding aid, with strict privacy controls.

The fastest wedge is likely dictation plus live captions, because the value is obvious and the system can avoid risky autonomous actions at first.

### 24.3 Trust features

- Local glossary.
- Local speaker profile.
- Optional cloud assurance toggle.
- "Ask me before changing meaning" mode.
- Failure reporting with redaction preview.
- Clear history deletion.
- Per-session privacy indicator.
- Exportable transcript plus confidence metadata.

Trust features are not polish. They are what lets the target users actually use the thing.

## 25. Distribution and business moat

Babel can be open, commercial, or hybrid, but the moat should survive any of those choices.

### 25.1 Open what increases trust

Strong candidates to open:

- The JSON inter-stage contract.
- The benchmark methodology.
- The eval reporting template.
- The Rust runtime shell, if it helps adoption.
- Small demo models or adapters for non-sensitive cells.

Keep controlled:

- The full licensed corpus when licenses do not allow redistribution.
- The private hard eval.
- Partnership data.
- The active-learning queue.
- The best specialist weights if commercialization requires it.

### 25.2 Partnership wedges

- Language schools and immigrant-serving organizations.
- Universities with speech and linguistics labs.
- Accessibility nonprofits.
- Public-interest legal and civic transcription groups.
- Healthcare communication support, carefully scoped.
- Customer-support teams serving multilingual populations.
- Local governments with public meeting transcription needs.

The best partnerships create both distribution and data, with consent and clear benefit to the speakers.

### 25.3 Positioning

Do not position against generic ASR on average accuracy. Position against the actual pain:

- "For people speech tools mishear."
- "Offline speech understanding for accents, dialects, and code-switching."
- "A forgiving layer between what was heard and what was meant."

The wording matters because the product is built for people who may already feel judged by language tools.

## 26. Implementation blueprint

The repo should eventually split into clear artifacts, even if it starts as one workspace.

### 26.1 Core packages

- `babel-contract`: JSON schema, examples, validators.
- `babel-eval`: benchmark runner, metrics, reports, contamination checks.
- `babel-ledger`: license/provenance/coverage database tools.
- `babel-data`: ingestion, VAD, sharding, pseudo-labeling, filtering.
- `babel-train-acoustic`: distillation, routing gates, pruning, QAT.
- `babel-train-repair`: synthetic generation, QLoRA, faithfulness training.
- `babel-runtime`: Rust inference engine.
- `babel-cli`: local command-line tool for files and microphone.
- `babel-ui`: thin local app for dictation/captions and feedback.

### 26.2 First concrete artifact

The first artifact should be the contract plus eval harness, not the custom model.

Why:

- It prevents the project from becoming an unmeasured demo.
- It makes every later model comparable.
- It forces the faithfulness and clarify behavior into the design from day one.
- It creates the public benchmark path.

Minimum contract examples:

- Clean easy English.
- Heavy accent.
- Broken English.
- Code-switch.
- Noisy audio.
- Ambiguous utterance that should clarify.
- Dialect that should not be normalized away.
- Entity-heavy utterance.

### 26.3 Thirty-day build plan

**Week 1: contract and baseline.**

- Freeze the Stage A -> A.5 -> B JSON contract.
- Wire off-the-shelf Whisper/distil-whisper to emit N-best.
- Wire a small instruct model prompt for repair.
- Build a tiny hand-labeled eval set.
- Report WER, intent, segmentation, hallucination, latency, memory.

**Week 2: repair data and eval.**

- Generate L1-specific broken-to-clean pairs.
- Generate punctuation/sentence-boundary pairs.
- Fine-tune or prompt-tune Stage B.
- Add faithfulness and clarify labels.
- Build the first failure taxonomy dashboard.

**Week 3: data pipeline.**

- Implement license ledger.
- Ingest one or two permissive corpora.
- Add VAD, sharding, acoustic inspection, pseudo-labeling.
- Build coverage table by accent/fluency/noise cell.

**Week 4: first moat report.**

- Publish internal Pareto table: baseline versus repair fine-tune.
- Publish coverage gaps.
- Pick top five hard cells.
- Decide first specialist versus routing experiment.
- Start first RunPod pseudo-labeling batch.

### 26.4 Ninety-day build plan

- Build a real held-out eval set with enough hard-cell coverage to steer decisions.
- Complete first Stage B fine-tune.
- Complete first custom acoustic distillation.
- Run vocabulary-pruned and quantization-aware variants.
- Benchmark min-size and flagship tiers.
- Prototype Rust runtime around the best available weights.
- Start two data partnerships.
- Produce a public writeup with the parity gap as the headline.

### 26.5 Six-month build plan

- Ship local dictation/live-caption alpha.
- Ship Babel Bench v0.
- Ship first protected-encoder flagship acoustic model.
- Ship min-size tier if it passes hard-cell gates.
- Add at least one specialist model loaded on demand.
- Build opt-in failure reporting.
- Publish a technical report on worst-group gains and the Pareto frontier.

## 27. Experiment ledger

Every experiment should be written in this format:

```md
### Experiment: short name

Hypothesis:
Expected moat gain:
Data:
Model/component:
Training cost:
Inference cost:
Metrics:
Worst-group result:
Average result:
Latency:
Resident memory:
Faithfulness:
Decision:
Follow-up:
```

This prevents the project from drifting into model tinkering. If an experiment cannot name its expected moat gain, it waits.

## 28. Immediate backlog

Highest leverage next actions:

1. Create the JSON schema for Stage A, A.5, B, and C.
2. Build a 50 to 100 item hand-labeled eval set across the target failure modes.
3. Run stock Whisper or distil-whisper through the eval and record the failure taxonomy.
4. Add an N-best repair prompt and measure the lift over 1-best.
5. Generate the first synthetic broken-to-clean pairs for five L1 groups.
6. Build the license/provenance ledger schema.
7. Ingest Common Voice and one hard accent corpus into the ledger.
8. Add VAD and acoustic quality inspection.
9. Build the coverage dashboard.
10. Decide reference hardware and benchmark format.
11. Prototype q4/q5/q8 repair model latency locally.
12. Prototype Rust or GGUF runtime with an off-the-shelf model.
13. Write the first public-facing benchmark spec.
14. Identify the first two partnership targets.
15. Start the first RunPod pseudo-labeling dry run on a small shard.

The first milestone is not a perfect model. It is a loop that can make the model better every week.

## 29. The strategic answer in one page

Babel wins by refusing to play the broad-ASR game.

Broad ASR optimizes mean performance across enormous generic data. Babel optimizes the people hidden by that mean: accents, dialects, code-switching, broken grammar, noisy civic speech, and speakers who are tired of being misunderstood. The technical strategy follows from that:

- Use giant teachers in the cloud, but ship small local students.
- Spend parameters on the encoder and hard-case rescue, not generic size.
- Use N-best and repair because literal ASR is not enough.
- Optimize worst-group quality, not average WER.
- Build a legal coverage ledger, not a vague pile of audio.
- Build a benchmark that makes the failure visible.
- Route compute by uncertainty so easy speech stays fast and hard speech gets care.
- Keep inference local so the target users can trust it.
- Treat clarification as success when the alternative is confident hallucination.

The absolute moat is the compounding loop around an ignored distribution. Every month the system should know more about where it fails, own more legally clean data for those failures, improve a harder benchmark, and move the local Pareto frontier forward. That is much harder to copy than a model checkpoint.

## 30. Contract v0

The contract is the spine. It lets training, eval, runtime, and product move independently without turning the pipeline into prompt soup.

### 30.1 Stage A output

```json
{
  "schema_version": "babel.stage_a.v0",
  "audio": {
    "source_id": "clip_000001",
    "sample_rate_hz": 16000,
    "duration_s": 3.42,
    "channels": 1
  },
  "decode": {
    "model_id": "stage-a-baseline",
    "tier": "flagship",
    "beam_size": 5,
    "temperature": 0.0,
    "rtf": 0.34
  },
  "literal": "i went to the pharmacy but they dont have my medicine innit",
  "nbest": [
    {
      "rank": 1,
      "text": "i went to the pharmacy but they dont have my medicine innit",
      "score": -0.41
    },
    {
      "rank": 2,
      "text": "i went to the pharmacy but they don't have my medicine in it",
      "score": -0.55
    }
  ],
  "segments": [
    {
      "start_s": 0.0,
      "end_s": 3.42,
      "text": "i went to the pharmacy but they dont have my medicine innit",
      "lang": "en",
      "confidence": 0.72
    }
  ],
  "signals": {
    "asr_confidence": 0.72,
    "nbest_disagreement": 0.31,
    "noise_tier": "real_background",
    "possible_code_switch": false,
    "accent_family_hint": "caribbean_or_british_isles",
    "needs_hard_path": true
  }
}
```

### 30.2 Stage A.5 output

```json
{
  "schema_version": "babel.stage_a5.v0",
  "source_id": "clip_000001",
  "punctuated": "I went to the pharmacy, but they don't have my medicine, innit?",
  "sentences": [
    {
      "index": 0,
      "text": "I went to the pharmacy, but they don't have my medicine, innit?",
      "start_s": 0.0,
      "end_s": 3.42,
      "confidence": 0.78
    }
  ],
  "tokens": [
    {
      "token": "I",
      "source_token": "i",
      "punct_after": "",
      "case": "upper",
      "confidence": 0.97
    }
  ],
  "signals": {
    "boundary_confidence": 0.81,
    "punctuation_confidence": 0.74,
    "needs_repair": true
  }
}
```

### 30.3 Stage B output

```json
{
  "schema_version": "babel.stage_b.v0",
  "source_id": "clip_000001",
  "cleaned": "I went to the pharmacy, but they don't have my medicine.",
  "preserved_literal": "I went to the pharmacy, but they don't have my medicine, innit?",
  "intent": {
    "type": "statement",
    "summary": "The speaker went to the pharmacy and the medicine was unavailable.",
    "entities": [
      {
        "text": "pharmacy",
        "type": "place_generic",
        "confidence": 0.86
      },
      {
        "text": "medicine",
        "type": "item_generic",
        "confidence": 0.82
      }
    ]
  },
  "languages": [
    {
      "lang": "en",
      "span": [0, 65],
      "confidence": 0.96
    }
  ],
  "faithfulness": {
    "faithful": true,
    "risk": "low",
    "unsupported_claims": []
  },
  "decision": {
    "action": "answer",
    "clarifying_question": null
  },
  "confidence": {
    "overall": 0.81,
    "intent": 0.84,
    "entities": 0.78
  }
}
```

### 30.4 Clarification output

```json
{
  "schema_version": "babel.stage_b.v0",
  "source_id": "clip_000042",
  "cleaned": null,
  "preserved_literal": "can you book it for four or for fourteen",
  "intent": null,
  "faithfulness": {
    "faithful": false,
    "risk": "ambiguous_audio",
    "unsupported_claims": []
  },
  "decision": {
    "action": "clarify",
    "clarifying_question": "Did you mean four or fourteen?"
  },
  "confidence": {
    "overall": 0.42,
    "intent": 0.39,
    "entities": 0.31
  }
}
```

The clarify path must be first-class in tests. It is how Babel avoids turning uncertainty into wrong action.

## 31. Ledger schema v0

The ledger should start as a simple table or SQLite database and graduate only when scale demands it.

### 31.1 Clip table

| Field | Purpose |
| --- | --- |
| `clip_id` | Stable internal ID |
| `source_id` | Original source item |
| `source_url` | Where the audio came from |
| `source_type` | corpus, podcast, public_record, partnership, synthetic, user_opt_in |
| `license_name` | License label |
| `license_url` | License proof |
| `attribution` | Required attribution string |
| `redistribution_allowed` | true/false/unknown |
| `training_allowed` | true/false |
| `eval_allowed` | true/false |
| `duration_s` | Clip duration |
| `sample_rate_hz` | Sample rate |
| `audio_hash` | Content hash |
| `speaker_hash` | Speaker identity hash if known and ethical |
| `split` | train/dev/test/private_eval/quarantine |
| `transcript_type` | human, caption, pseudo, synthetic |
| `transcript_confidence` | Numeric confidence |
| `teacher_agreement` | Agreement score |
| `accent_family` | Broad family tag |
| `accent_confidence` | Tag confidence |
| `l1_hint` | First-language hint if known |
| `fluency_tier` | fluent, disfluent, broken, unknown |
| `noise_tier` | clean, real_background, far_field, phone, defective |
| `register` | read, conversation, meeting, public_speech, command, dictation |
| `language_mix` | en, en-es, en-fr, multilingual |
| `cell_rarity` | How under-covered this cell is |
| `human_review_priority` | Queue score |
| `pii_status` | clean, redacted, needs_review |
| `notes` | Freeform audit notes |

### 31.2 Coverage query examples

Questions the ledger must answer quickly:

- Which accent/noise/fluency cells have less than ten minutes of gold eval?
- Which cells have high teacher disagreement and low training volume?
- Which sources produce the highest human-review leverage?
- Which clips are legal for training but not redistribution?
- Which speakers or sources risk leakage between train and eval?
- Which hard cells improved after the last training run?

If the ledger cannot answer those, the project is flying blind.

## 32. Metrics and formulas

### 32.1 Core metrics

```text
WER = (substitutions + deletions + insertions) / reference_words

parity_gap = worst_group_metric - best_group_metric

worst_group_quality = min(group_quality_scores)

hallucination_rate = unsupported_outputs / total_outputs

clarify_precision = useful_clarifications / total_clarifications

clarify_recall = useful_clarifications / cases_that_should_clarify

rtf = decode_time_seconds / audio_duration_seconds

quality_per_gb = worst_group_quality / resident_memory_gb

quality_per_second = worst_group_quality / end_to_end_latency_seconds
```

For error metrics where lower is better, keep the direction explicit. A "quality score" can be `1 - WER`, `intent_accuracy`, or a composite, but the release report should show raw metrics too.

### 32.2 Release scorecard

Every model release gets a scorecard:

| Metric | Min-size | Flagship | Max-quality local | Previous flagship |
| --- | --- | --- | --- | --- |
| Average WER |  |  |  |  |
| Worst-group WER |  |  |  |  |
| Parity gap |  |  |  |  |
| Intent accuracy |  |  |  |  |
| Worst-group intent accuracy |  |  |  |  |
| Hallucination rate |  |  |  |  |
| Clarify precision |  |  |  |  |
| Clarify recall |  |  |  |  |
| Boundary F1 |  |  |  |  |
| Code-switch boundary F1 |  |  |  |  |
| RTF |  |  |  |  |
| Tokens-to-first-answer |  |  |  |  |
| Resident memory |  |  |  |  |
| On-disk size |  |  |  |  |
| License-clean training hours |  |  |  |  |

The most important column is "Previous flagship." It keeps the team honest about regressions.

### 32.3 Composite release gate

A release passes only if:

- Worst-group WER improves or stays flat.
- Worst-group intent accuracy improves or stays flat.
- Hallucination rate does not increase.
- Clarify precision and recall stay within target range.
- RTF and resident memory stay within the tier budget.
- No license or privacy regression is introduced.

Average WER can improve and still fail the release. That is the correct posture.

## 33. First experiment matrix

Run these experiments before inventing new architecture.

| ID | Experiment | Why it matters | Success |
| --- | --- | --- | --- |
| E01 | 1-best repair prompt vs N-best repair prompt | Proves the inter-stage contract | N-best improves hard-cell intent without hallucination |
| E02 | Small repair model prompt vs QLoRA fine-tune | Shows whether Stage B needs training | Fine-tune improves repair and segmentation |
| E03 | Folded segmentation vs dedicated token classifier | Decides Stage A.5 shape | Dedicated model wins only if it improves boundary F1 enough |
| E04 | Beam 1/3/5 by confidence bucket | Speed-quality trade | Wider beam used only where it helps |
| E05 | q8/q5/q4 acoustic comparison | Quantization floor | q4 acceptable only for min-size |
| E06 | Full vocab vs scoped vocab | Clean parameter cut | Same in-scope quality with smaller model |
| E07 | Protected encoder vs sheared encoder | Confirms flagship posture | Tail quality justifies encoder protection |
| E08 | Generalist vs first specialist | Tests shelf-specialist strategy | Specialist helps hard cell without bloating resident memory |
| E09 | Synthetic volume sweep | Finds synthetic plateau | Real eval improves then saturates |
| E10 | Human review on teacher disagreement | Measures review leverage | Reviewed disagreement clips beat random review |
| E11 | Glossary retrieval for entities | Avoids baking names into weights | Entity accuracy improves with no model growth |
| E12 | Rust runtime vs Python prototype | Packaging and latency | Rust path wins startup/memory without quality drift |

### 33.1 First hand-built eval examples

These are text sketches; the real eval needs audio.

| Case | Literal-ish input | Desired behavior |
| --- | --- | --- |
| Dialect preservation | "I been told him already" | Preserve meaning, do not mark as bad grammar |
| Code-switch | "Can you move la cita to Friday?" | Keep Spanish entity, infer appointment |
| Ambiguous number | "Book it for four/fourteen" | Clarify |
| L1 article drop | "I need go hospital tomorrow" | Repair intent without adding unsupported detail |
| Noisy entity | "My medicine is metformin" | Preserve entity or clarify if uncertain |
| False start | "I was, I mean she was waiting outside" | Resolve speaker's correction |
| Caribbean tag | "They closed already, innit?" | Preserve pragmatic tag or clean only when requested |
| Public meeting | "The motion passes, item seven is tabled" | Correct domain meaning |

## 34. Moat checklist

Babel has a real moat when these are true:

- The benchmark shows failures that generic ASR vendors do not optimize for.
- The ledger contains legally clean, high-value tail data that cannot be recreated by casual scraping.
- The training loop improves named hard cells monthly.
- The local runtime is fast enough that users choose it over cloud tools.
- The repair model improves intent without erasing dialect or hallucinating.
- The product has a respectful clarify loop.
- The team can explain every model trade-off in quality-per-GB and quality-per-second terms.
- Partnerships create new data and distribution at the same time.
- The public story is not "our model is bigger"; it is "the people normally hidden by the average are the metric."

## 35. Skeleton doctrine: density over bloat

The first repo shape should stay almost aggressively small. Babel is easy to over-folder because the long-term system has acoustic training, repair training, eval, runtime, data ingestion, ledgering, UI, and partnerships. Do not create that structure before the code earns it.

The rule:

- One folder for executable Python until a second language or deployment boundary forces a split.
- One core module until a file becomes hard to scan.
- One test file until tests become meaningfully separate domains.
- No framework until plain functions fail.
- No schema directory until the JSON contract needs machine-readable external publication.
- No data pipeline package until ingestion has at least two real sources.
- No runtime folder until Rust code exists.
- No generated abstractions around a database that SQLite can already answer.
- No "utils" module. Name the domain or keep the function where it is.

The repo starts with the spine only:

```text
babel.md
pyproject.toml
src/babel/__init__.py
src/babel/core.py
tests/test_core.py
```

That gives the project:

- Contract validation.
- WER and parity-gap metrics.
- A SQLite clip ledger.
- Coverage queries over accent, fluency, and noise cells.
- A test harness.

Current production code budget: keep `src/babel` dense and explainable. The first scaffold is allowed to grow past the original 150-line seed only when a function removes an entire future tool boundary. The current local target is still small: one core module, one CLI module, one test file, and no runtime/data/eval subpackages until the gates below are hit.

### 35.1 Folder creation gates

Create a new folder only when one of these is true:

- **`schemas/`**: external tools need JSON Schema files rather than Python validation.
- **`data/`**: at least two real licensed sources are ingested through the same path.
- **`eval/`**: benchmark fixtures or reports become too large for tests.
- **`runtime/`**: Rust inference code begins.
- **`models/`**: local model manifests are needed; never commit large weights by accident.
- **`docs/`**: `babel.md` becomes a published spec plus separate operational notes.

Until then, fewer files is a feature. Dense code keeps the shape of the system visible.

### 35.2 Line-of-code pressure

The density target is not code golf. It is pressure against premature architecture.

Good density:

- Functions with clear domain names.
- Standard library first.
- Tables and schemas represented once.
- Tests that cover behavior rather than mocks.
- Plain SQLite before services.
- Plain JSON before generated clients.

Bad density:

- Clever one-liners.
- Hidden global state.
- Repeated stringly typed contracts.
- Condensed code that makes auditability worse.
- Skipping tests to keep counts low.

The score is not "few lines." The score is moat per line.

## 36. Pre-cloud scaffold

Before RunPod is necessary, the local repo should prove the loop on toy data and small real clips. The current skeleton does that with one package and no third-party dependencies.

Current local surface:

```text
babel.md
RUNPOD.md
pyproject.toml
src/babel/__init__.py
src/babel/__main__.py
src/babel/cli.py
src/babel/core.py
tests/test_core.py
eval/README.md
eval/contract/stage_a_{fast,hard,codeswitch}.json
eval/contract/stage_a5_{clean,runon}.json
eval/contract/stage_b_{answer,clarify,faithfail}.json
eval/{eval,nbest_eval,repair_eval,segmentation_eval,clips.seed}.jsonl
eval/{targets,metrics.baseline,tiers.example}.json
```

`eval/` holds data only (no Python): the contract examples and the hand-built
eval seed, which is the project's first concrete moat artifact (§26.2). `RUNPOD.md`
is the production-cycle runbook (the §35.1 `docs/`-style operational notes,
kept as a single file to stay dense).

Commands:

```bash
PYTHONPATH=src python3 -m babel validate-stage stage_b sample_stage_b.json
PYTHONPATH=src python3 -m babel validate-dir eval/contract
PYTHONPATH=src python3 -m babel route sample_stage_a.json
PYTHONPATH=src python3 -m babel inspect-wav sample.wav
PYTHONPATH=src python3 -m babel manifest-wavs ./clips --db ledger.sqlite --license-name CC0 --training-allowed
PYTHONPATH=src python3 -m babel ledger-upsert ledger.sqlite clips.jsonl
PYTHONPATH=src python3 -m babel coverage ledger.sqlite accent_family fluency_tier noise_tier
PYTHONPATH=src python3 -m babel coverage-gaps ledger.sqlite targets.json
PYTHONPATH=src python3 -m babel ledger-stats ledger.sqlite
PYTHONPATH=src python3 -m babel split-leaks ledger.sqlite
PYTHONPATH=src python3 -m babel audit ledger.sqlite --metrics-json current_metrics.json
PYTHONPATH=src python3 -m babel assign-splits ledger.sqlite --group-key auto
PYTHONPATH=src python3 -m babel export-shard ledger.sqlite --split train --training-allowed
PYTHONPATH=src python3 -m babel review-queue ledger.sqlite --limit 20
PYTHONPATH=src python3 -m babel eval-asr eval.jsonl --group-key accent_family
PYTHONPATH=src python3 -m babel eval-nbest nbest_eval.jsonl --group-key accent_family
PYTHONPATH=src python3 -m babel eval-repair repair_eval.jsonl --group-key accent_family
PYTHONPATH=src python3 -m babel eval-segmentation segmentation_eval.jsonl --group-key accent_family
PYTHONPATH=src python3 -m babel release-gate current_metrics.json --previous-json previous_metrics.json
PYTHONPATH=src python3 -m babel scorecard tiers.json --previous-json previous_flagship.json
PYTHONPATH=src python3 -m babel phase-status ledger.sqlite --metrics-json current_metrics.json
PYTHONPATH=src python3 -m babel report ledger.sqlite --metrics-json current_metrics.json --targets-json targets.json
PYTHONPATH=src python3 -m babel experiment-record ledger.sqlite experiment.json
PYTHONPATH=src python3 -m babel experiments ledger.sqlite
```

What this enables locally:

- Deeply validate the inter-stage JSON contract (types, enums, numeric ranges, and cross-field invariants), one file or a whole directory of examples.
- Decide fast path versus hard path from Stage A confidence signals.
- Inspect WAV files for sample rate, duration, clipping, silence, and defect flags.
- Turn a folder of WAVs into ledger-ready rows with hashes and conservative eligibility.
- Create and update the SQLite clip ledger.
- Query coverage by accent, fluency, and noise cells.
- Find coverage gaps against target cells.
- Detect split leakage across audio hashes, speaker hashes, and source IDs.
- Audit license issues, defect issues, unassigned eligible clips, and split leaks.
- Assign deterministic group-safe splits.
- Export train/dev/test shards from the ledger.
- Rank human-review candidates.
- Evaluate normalized grouped WER, CER, and parity gap from JSONL.
- Measure N-best recoverable headroom.
- Evaluate repair/clarify behavior, clean WER, and hallucination rate.
- Evaluate sentence-boundary F1, punctuation accuracy, casing accuracy, and code-switch boundary F1.
- Gate releases against previous metrics, and render a multi-tier release scorecard.
- Check phase readiness, including coverage entropy as a moat metric.
- Emit a Markdown local report.
- Record experiment hypotheses, metrics, and decisions.

This is enough to run Phase 0 and most of Phase 1 locally. Cloud becomes necessary when teacher labeling, synthetic generation at scale, or acoustic distillation becomes the bottleneck. Until then, the goal is to make the local loop sharp enough that cloud time is never exploratory in the vague sense; it should execute a named experiment with a ledger, an eval, and a release gate already waiting.

### 36.1 Local file formats

`clips.jsonl` rows are sparse ledger rows. Only `clip_id` is required, but useful rows include:

```json
{"clip_id":"c1","duration_s":4.2,"accent_family":"caribbean","fluency_tier":"fluent","noise_tier":"phone","training_allowed":1}
```

`eval.jsonl` rows are ASR eval records:

```json
{"reference":"book it for four","hypothesis":"book it for fourteen","accent_family":"caribbean"}
```

`experiment.json` records the why, what, and result:

```json
{
  "experiment_id": "E01",
  "hypothesis": "N-best repair improves hard-cell intent",
  "component": "repair",
  "data": "50 hand-built eval cases",
  "metrics_json": {"worst_group_wer": 0.2, "intent_accuracy": 0.84},
  "decision": "keep"
}
```

### 36.2 Next local gates

Allowed next additions before cloud:

- A tiny hand-built `eval.jsonl` checked into the repo only if it contains no sensitive or licensed audio-derived text.
- Machine-readable JSON Schema files only when another tool needs them.
- A real fixture-free smoke test for the CLI if command behavior becomes more complex.
- A local prompt runner for Stage B only when a model backend is chosen.
- A Rust `runtime/` folder only when the Python CLI can hand it a stable contract.

Not allowed yet:

- A broad `data/` folder with speculative scripts.
- A model abstraction layer before two real model backends exist.
- A service/server wrapper before the CLI loop proves value.
- Any committed audio corpus or model weights.

## 37. Local phase buildout to the RunPod boundary

This is the concrete local loop. The aim is to exhaust every cheap, deterministic, inspectable step before renting GPUs. RunPod should be used only after the local repo can name the exact job, the exact input shards, the exact eval gate, and the expected moat gain.

### 37.0 Phase 0A: contract hardening

Goal: make the inter-stage contract boring enough that every later model can plug into it.

Local artifacts:

- `stage_a.json` examples for fast, hard, code-switch, and low-confidence utterances.
- `stage_a5.json` examples for clean segmentation and ambiguous run-ons.
- `stage_b.json` examples for answer, clarify, and faithfulness-fail decisions.

Commands:

```bash
PYTHONPATH=src python3 -m babel validate-stage stage_a stage_a.json
PYTHONPATH=src python3 -m babel validate-stage stage_a5 stage_a5.json
PYTHONPATH=src python3 -m babel validate-stage stage_b stage_b.json
PYTHONPATH=src python3 -m babel route stage_a.json
```

Gate:

- Every example validates.
- Low confidence routes to `hard`.
- Code-switch routes to `hard`.
- The clarify object is valid Stage B output, not a side channel.

Stop condition:

- Do not add JSON Schema files until an external tool needs schema publication. Python validation is enough locally.

### 37.1 Phase 0B: hand-built eval seed

Goal: make the neglected space measurable before model work begins.

Create a tiny text-only `eval.jsonl` and `repair_eval.jsonl` with no sensitive or licensed audio-derived content. Start with 50 to 100 cases. These can be hand-written sketches of expected behavior until real audio is available.

ASR eval row:

```json
{"reference":"book it for four","hypothesis":"book it for fourteen","accent_family":"caribbean","fluency_tier":"fluent","noise_tier":"phone"}
```

Repair eval row:

```json
{"reference_clean":"I need to go to the hospital.","hypothesis_clean":"I need to go to hospital.","decision":"answer","should_clarify":false,"accent_family":"south_asian"}
```

Commands:

```bash
PYTHONPATH=src python3 -m babel eval-asr eval.jsonl
PYTHONPATH=src python3 -m babel eval-repair repair_eval.jsonl
```

Gate:

- Overall WER reported.
- Per-group WER reported.
- Clean repair WER reported.
- Clarify precision and recall reported.
- Hallucination rate reported.

Stop condition:

- Do not fine-tune anything until this seed catches obvious regressions.

### 37.2 Phase 0C: N-best proof

Goal: prove that the N-best contract has recoverable value before building around it.

`nbest_eval.jsonl` row:

```json
{"reference":"book it for four","nbest":["book it for fourteen","book it for four"],"accent_family":"caribbean"}
```

Command:

```bash
PYTHONPATH=src python3 -m babel eval-nbest nbest_eval.jsonl
```

Gate:

- First-best WER is worse than oracle WER on at least some hard cases.
- The recoverable gap is large enough to justify feeding N-best into Stage B.
- If the recoverable gap is near zero, fix Stage A decoding diversity before repair-model work.

Stop condition:

- Do not spend model complexity on Stage B if the acoustic stage never exposes the missing alternatives.

### 37.3 Phase 1A: local audio hygiene

Goal: catch broken files before they poison pseudo-labeling.

Commands:

```bash
PYTHONPATH=src python3 -m babel inspect-wav sample.wav
PYTHONPATH=src python3 -m babel manifest-wavs ./clips --db ledger.sqlite --license-name CC0 --training-allowed --eval-allowed
```

What gets measured:

- Duration.
- Sample rate.
- Channels.
- RMS and peak.
- Silence ratio.
- Clipping ratio.
- Defect flags.
- SHA-256 audio hash.

Gate:

- Low sample-rate, clipped, and near-silent clips are flagged.
- Flagged clips default to `split=quarantine`.
- Flagged clips are not marked train/eval eligible even if requested.

Stop condition:

- Do not add ffmpeg, resampling, or decoding machinery until there is a real non-WAV source that needs it.

### 37.4 Phase 1B: ledger and coverage

Goal: prove the data moat locally: source, license, quality, and coverage in one table.

Commands:

```bash
PYTHONPATH=src python3 -m babel ledger-init ledger.sqlite
PYTHONPATH=src python3 -m babel ledger-upsert ledger.sqlite clips.jsonl
PYTHONPATH=src python3 -m babel ledger-stats ledger.sqlite
PYTHONPATH=src python3 -m babel coverage ledger.sqlite accent_family fluency_tier noise_tier
PYTHONPATH=src python3 -m babel coverage-gaps ledger.sqlite targets.json
PYTHONPATH=src python3 -m babel audit ledger.sqlite
```

`targets.json`:

```json
[
  {"accent_family":"caribbean","fluency_tier":"fluent","noise_tier":"phone","target_hours":2},
  {"accent_family":"south_asian","fluency_tier":"broken","noise_tier":"real_background","target_hours":2}
]
```

Gate:

- Ledger stats show clips, train hours, eval clips, coverage cells, experiments.
- Coverage table can group by the target parity dimensions.
- Gap report ranks the next cells to acquire.
- Audit shows no train/eval-eligible clips with missing license metadata.
- Audit shows no defective clips marked train/eval eligible.

Stop condition:

- Do not scrape broadly. Acquire the top gap cells only.

### 37.5 Phase 1C: split hygiene

Goal: prevent fake gains before any model work.

Commands:

```bash
PYTHONPATH=src python3 -m babel assign-splits ledger.sqlite --group-key auto
PYTHONPATH=src python3 -m babel split-leaks ledger.sqlite
PYTHONPATH=src python3 -m babel export-shard ledger.sqlite --split train --training-allowed
```

Gate:

- No audio hash appears in multiple splits.
- No speaker hash appears in multiple splits.
- No source ID appears in both train and eval unless that source is explicitly safe and speaker-disjoint.
- Split assignment is deterministic from speaker hash, then source ID, then audio hash, then clip ID.
- Quarantine rows stay quarantined.
- Exported train/dev/test shards come only from the ledger, not ad hoc file lists.

Stop condition:

- If split leakage exists, fix the ledger before running eval. A contaminated eval is worse than no eval because it teaches false confidence.

### 37.6 Phase 1D: human review queue

Goal: spend human attention where it compounds.

Command:

```bash
PYTHONPATH=src python3 -m babel review-queue ledger.sqlite --limit 50
```

Ranking logic:

- Highest human-review priority first.
- Then rarest cells.
- Then lowest teacher agreement.

Gate:

- Review queue produces clips from hard, under-covered, high-disagreement cells.
- Reviewed clips become either training-clean, eval-clean, or quarantine.

Stop condition:

- Do not randomly review clips. Random review is how human time disappears without moat gain.

### 37.7 Phase 1E: experiment memory

Goal: make every iteration auditable.

Command:

```bash
PYTHONPATH=src python3 -m babel experiment-record ledger.sqlite experiment.json
PYTHONPATH=src python3 -m babel experiments ledger.sqlite
```

Gate:

- Every experiment has an ID, hypothesis, component, data note, metrics, and decision.
- No model or prompt change counts as "done" until it is recorded.

Stop condition:

- If the experiment cannot name the expected moat gain, do not run it.

### 37.8 Phase 1F: release and phase gates

Goal: prevent local regressions and decide whether cloud is justified.

Commands:

```bash
PYTHONPATH=src python3 -m babel release-gate current_metrics.json --previous-json previous_metrics.json
PYTHONPATH=src python3 -m babel phase-status ledger.sqlite --metrics-json current_metrics.json
PYTHONPATH=src python3 -m babel report ledger.sqlite --metrics-json current_metrics.json --targets-json targets.json
```

Gate:

- Release gate passes: no worse worst-group WER, hallucination, latency, memory, or intent metrics.
- Phase status shows which local gates remain.
- Audit passes: no missing-license eligible clips, no defective eligible clips, no split leaks.
- Report is generated and readable.

Stop condition:

- Do not start a cloud job while the local report still has unresolved split leaks, no eval seed, no experiment record, or no named target cells.

## 38. Phase-by-phase local completion criteria

### Phase 0 complete: glue MVP ready

Completion means:

- Stage A/A.5/B examples validate.
- Fast versus hard routing works on confidence/disagreement/code-switch signals.
- A hand-built eval seed exists.
- ASR, repair, and N-best eval commands run locally.
- At least one baseline experiment is recorded.

Output:

- `current_metrics.json`.
- `ledger.sqlite`.
- A local report.

Cloud needed: no.

### Phase 1 complete: repair and eval loop ready

Completion means:

- Repair eval reports clean WER, decision accuracy, clarify precision/recall, and hallucination rate.
- N-best oracle gap is measured.
- Boundary F1 can be measured for sentence segmentation cases.
- Release gate compares current versus previous local metrics.
- Phase status names remaining blockers.

Output:

- A ranked list of repair failures.
- A decision on prompt-only versus fine-tune.
- A decision on folded segmentation versus dedicated segmentation.

Cloud needed: maybe for large synthetic generation, but not for the local proof. Generate small synthetic examples locally or by hand first.

### Phase 2 complete: data moat local pilot ready

Completion means:

- WAV inspection works on local clips.
- Manifesting creates hash-backed ledger rows.
- Coverage and coverage-gap queries work.
- Split leakage check passes.
- Human review queue ranks useful clips.
- Ledger contains at least one train-eligible and one eval-eligible source, even if tiny.

Output:

- `ledger.sqlite` with real rows.
- `targets.json` for next acquisition.
- Human review queue.
- Split-leak report.

Cloud needed: no for a pilot, yes for pseudo-labeling a real corpus.

### Phase 3 ready: first RunPod job justified

RunPod is justified only when:

- The local report shows no split leakage.
- The target cells are explicit.
- The clips to pseudo-label are ledgered and license-clean.
- The eval set is held out.
- The experiment has a recorded hypothesis.
- The success metric is named before the pod starts.

First RunPod job should not be acoustic distillation. It should be a small pseudo-labeling dry run over a shard:

- Input: one ledgered shard.
- Teachers: selected teacher models.
- Output: pseudo-label JSONL plus agreement scores.
- Local follow-up: ledger update, review queue, eval impact.

Only after that loop works should multi-GPU distillation start.

## 39. What remains impossible locally

These are the true cloud boundary items:

- Teacher pseudo-labeling across many hours or terabytes.
- Multi-teacher consensus at scale.
- Large synthetic pair generation with LLM/TTS throughput.
- Acoustic distillation.
- Quantization-aware distillation for the acoustic model.
- Broad parity training sweeps.
- Specialist-versus-generalist training comparisons.
- Cloud assurance verifier experiments.

Everything else should be locally defined before the pod launches.

Cloud job template:

```md
Job:
Hypothesis:
Input ledger query:
Input shard IDs:
Teacher/model:
Expected output:
Success metric:
Worst-group gate:
Faithfulness gate:
Cost cap:
Checkpoint path:
Resume strategy:
Local command to ingest output:
Local command to evaluate output:
Decision owner:
```

If any line is blank, the job is not ready.

## 40. Current local build state

Implemented locally:

- Deep contract validation: types, enums, numeric ranges, and cross-field invariants for Stage A/A.5/B, table-driven from one declarative spec.
- Directory validation that infers the stage from `schema_version` and reports per-file pass/fail.
- Stage A fast/hard routing.
- JSON and JSONL loading.
- WAV inspection.
- WAV manifesting with SHA-256 hashes.
- License-aware manifest eligibility.
- SQLite clip ledger.
- SQLite experiment ledger.
- Normalized WER and CER.
- Coverage, coverage-gap, and coverage-entropy reports.
- Split leakage detection.
- Deterministic group-safe split assignment.
- Train/dev/test shard export.
- Ledger audit for license, defect, and split blockers.
- Human review queue.
- ASR WER eval.
- N-best oracle eval.
- Repair/clarify/hallucination eval.
- Segmentation eval: boundary F1, punctuation accuracy, casing accuracy, code-switch boundary F1.
- Release regression gate and multi-tier release scorecard.
- Phase readiness gate.
- Markdown local report.
- CLI over all of the above.
- Unit tests over the loop.
- The hand-built eval seed (`eval/`): contract examples plus ASR/N-best/repair/segmentation cases that surface a worst-group gap, and an illustrative ledger seed that drives the full data loop.
- The RunPod production-cycle runbook (`RUNPOD.md`): every cloud cycle pre-specified as a fillable job template with local ingest/eval commands and gates.

Still deliberately not implemented:

- Model backend abstraction.
- Server.
- UI.
- A committed audio corpus or model weights.
- RunPod execution scripts (the *plan* exists in `RUNPOD.md`; the scripts wait until Cycle 1 names the exact shard interface).
- Rust runtime folder.

Reason: each would add mass before the local loop proves the exact interface it needs. The current code is the pre-cloud nervous system, and it now runs the full Phase 0 → local Phase 1/2 loop on the seed with `runpod_ready` flipping green. The next real step is not more architecture; it is feeding the loop a real held-out eval and one legal audio source, then executing Cycle 1 of `RUNPOD.md`.
