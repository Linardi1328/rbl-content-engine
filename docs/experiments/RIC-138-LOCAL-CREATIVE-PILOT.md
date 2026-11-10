# RIC-138 — Local Creative Provider Experiment (Voicebox + Open Generative AI)

**Status:** EXPERIMENT READY FOR OWNER SETUP; **not installed, tested or production-integrated**.  
**Linear:** https://linear.app/rbl-productions/issue/RIC-138  
**Bounded scope:** RBL Content Engine creative assets only. No change to live paid Higgsfield generator, V1 weekly runner, Phase 5 publication, or existing approval gates.

## Why this is an experiment, not a provider migration

The existing V1 media path uses a job-scoped, verified Seedance/Higgsfield workflow with spend and human-approval constraints; the priority is still one genuine Customer Zero production-and-publication pass (RIC-63). Do **not** divert engineering time into swapping media backends while that milestone is blocked by human creative inputs.

- **Voicebox** can be evaluated as an *optional local voiceover source*. It has a local-first REST interface (the backend project documents `localhost:17493` in current builds), but its precise runtime/API version must be checked after installation. It is **not** automatically a replacement for the selected Higgsfield video model.
- **Open Generative AI** has a bundled `sd.cpp` local image engine on supported Mac hardware. The advertised cloud models and remote Wan2GP server are **not** free local inference by default. Evaluate the exported still image manually; do not assume a compatible CLI API.
- **Higgsfield stays the reference renderer** until manually accepted outputs demonstrate a benefit. No default provider switch.
- Compare the entire time-to-accepted-asset, not just software licence cost; model weights, compute, editor time, and commercial rights matter.

## Isolation and safety

1. Install only through verified project sites/releases:
   - Voicebox: https://github.com/jamiepine/voicebox/releases
   - Open Generative AI: https://github.com/Anil-matcha/Open-Generative-AI/releases
2. Verify Mac architecture, RAM, OS, and free storage first; **never** tell the owner to disable Gatekeeper or bypass a security warning. Stop on unidentified/unsigned builds and verify provenance.
3. Generate only from a generic synthetic script/prompt at first. No confidential projects, athlete/minor/customer data, proprietary assets or voice cloning without documented permission.
4. For each underlying model, verify its commercial-use licence separately from the app's software licence, including any model weights or bundled assets.
5. No cloud API credentials, paid credits, GPU rental or recurring subscription changes. Explicit owner approval required for any paid service, account permissions, or publication.
6. Store experimental outputs locally under ignored `.production/experiments/ric-138/` only; no app secrets, raw voice samples or media in Git, Linear or CI. Preserve evidence/reference links for factual claims; none are needed for the synthetic benchmark.
7. RBL's verified-claims, SceneCard, storyboard, review/QC, per-job media output, exact-byte approval and publication safety gates remain unchanged.
8. No code changes to production media runners in this first experiment. If a local adapter is justified, implement it via a separate PR after the benchmark, with a deterministic fallback and negative tests.

## Installation / smoke checklist (on owner's Mac)

Record these **non-secret** results in RIC-138:

```bash
uname -m
system_profiler SPHardwareDataType | grep -E 'Chip:|Processor Name:|Memory:'
sw_vers -productVersion
df -h "$HOME" | tail -n 1
```

If the hardware supports it:

**Voicebox**
- Install the official macOS build. Start with a bundled preset voice rather than cloning anyone.
- Choose a lightweight local model compatible with the Mac; finish any model download.
- Confirm speech generation from the same 20–30s benchmark script; export the audio to `.production/experiments/ric-138/voicebox/`.
- Record app version, engine/model version, language, output format, CPU/GPU/runtime, number of generations, accepted/rejected status and approximate human editing time.
- Do **not** wire a local REST endpoint into a repo runner unless the app's current version/docs and tests establish compatibility.

**Open Generative AI**
- Install the official macOS build. Select **Settings → Local Models → sd.cpp**; use a local model that fits the Mac.
- Check that the **Local** toggle is enabled. Hosted/cloud models are out of scope.
- Generate a 9:16 still concept for one approved generic storyboard beat and export to `.production/experiments/ric-138/open-generative-ai/`.
- Log app/model version, prompt, seed if exposed, dimensions, model licence, generation time, accepted/rejected status, revisions. Do not overwrite production keyframe/shot files.
- Local video generation on a Mac is *not* presumed supported/economic; Wan2GP normally needs separate CUDA/ROCm resources.

## Fair benchmark

**Synthetic narration brief** (contains no project performance claims):

> A small idea becomes a story through clear choices. Start with one message, create a focused visual, and let every second earn its place. Build a draft, review it carefully, and keep what works. A better workflow should save time without sacrificing quality.

**Synthetic still-image prompt:**

> Vertical 9:16 cinematic editorial illustration, abstract layered paper shapes and soft studio lighting, one bold central focal point, crisp composition with generous safe margins, premium contemporary palette, no text, no logos, no people.

Where an existing paid baseline is available **without incurring new spend**, use the same script or prompt and record the same outcome measures. Do not claim a head-to-head cost saving if no paid baseline exists.

| Metric | Current tool baseline | Free local candidate |
|---|---|---|
| Model/app and licence | NOT MEASURED | NOT MEASURED |
| Total time to accepted asset | NOT MEASURED | NOT MEASURED |
| Number of attempts | NOT MEASURED | NOT MEASURED |
| Human edit/rework time | NOT MEASURED | NOT MEASURED |
| Accepted output? (yes/no) | NOT MEASURED | NOT MEASURED |
| Cash cost per accepted asset | NOT MEASURED | NOT MEASURED |
| Hardware and storage burden | NOT MEASURED | NOT MEASURED |
| Voice consistency / image coherence | NOT MEASURED | NOT MEASURED |
| Commercial publication permitted? | NOT VERIFIED | NOT VERIFIED |

Scoring: human listens/views full output and scores intelligibility/visual craft/brand fit/consistency 1–5 with concrete reasons. **No fabricated results.**

## Decision gate

- **KEEP LOCAL CANDIDATE AS OPTIONAL** only if the output is publishably good after human review, licences are acceptable, quality is repeatable, and end-to-end cost/time is genuinely better.
- **KEEP PAID DEFAULT** if the free candidate introduces significant rework, inconsistent quality, operational friction or uncertain licensing.
- **DO NOT SWITCH** production defaults, cancel a subscription, publish media, or approve provider migration based on one synthetic test.
- Capture real pilot result in RIC-138 and only then decide whether a tiny optional media-import or Voicebox REST adapter PR is warranted.

## Next human action

Owner verifies Mac hardware and installs **Voicebox first** from official releases, then produces **one synthetic narration**. The visual experiment comes second. Stop if setup is costly or blocks higher-priority KYNEXA/RIVORA and RBL-CZ-001 shipping.
