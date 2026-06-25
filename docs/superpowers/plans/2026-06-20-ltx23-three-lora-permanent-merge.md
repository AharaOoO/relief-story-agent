# LTX 2.3 Three-LoRA Permanent Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create verified BF16 and FP8 E4M3 rank-concatenated LTX 2.3 LoRAs equivalent at strength 1.0 to OmniNFT 1.50 + OmniCine 0.55 + VBVR 0.73, without modifying the source files.

**Architecture:** A small Python package reads safetensors lazily, validates paired Diffusers LoRA tensors, copies and hashes sources, merges one module at a time in FP32 using balanced square-root scaling, writes BF16 and FP8 outputs, and emits machine-readable manifests and numerical validation reports. All writes are confined to `D:\codex工作区\ltx23_lora_merge`.

**Tech Stack:** Python 3.12, PyTorch 2.6, safetensors 0.5.3, unittest, PowerShell SHA-256 verification.

---

### Task 1: Establish the isolated workspace and source manifest

**Files:**
- Create: `ltx23_lora_merge/tests/test_merge.py`
- Create: `ltx23_lora_merge/ltx23_merge/__init__.py`
- Create: `ltx23_lora_merge/ltx23_merge/core.py`
- Create: `ltx23_lora_merge/merge_config.json`

- [ ] Write failing tests for SHA-256 calculation, safe copy behavior, and refusal to overwrite an existing mismatched copy.
- [ ] Run `python -m unittest discover -s ltx23_lora_merge/tests -v` and confirm failure because `ltx23_merge.core` is absent.
- [ ] Implement `sha256_file`, `copy_verified`, and manifest serialization.
- [ ] Run the tests and require zero failures.

### Task 2: Validate and normalize LoRA modules

**Files:**
- Modify: `ltx23_lora_merge/tests/test_merge.py`
- Modify: `ltx23_lora_merge/ltx23_merge/core.py`

- [ ] Write failing tests for Diffusers A/B pairing, rank extraction, incompatible shapes, unknown tensor rejection, and missing alpha semantics.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement header inspection and module indexing without loading the whole file into RAM.
- [ ] Run the complete suite and require zero failures.

### Task 3: Implement exact rank concatenation

**Files:**
- Modify: `ltx23_lora_merge/tests/test_merge.py`
- Modify: `ltx23_lora_merge/ltx23_merge/core.py`

- [ ] Write failing tests proving that balanced rank concatenation reproduces weighted `B @ A` sums for full overlap and partial module coverage.
- [ ] Confirm the tests fail because merge functions do not yet exist.
- [ ] Implement FP32 balanced scaling and concatenation; omit alpha for inputs with ComfyUI's implicit scale 1.0.
- [ ] Run all tests and require zero failures.

### Task 4: Add BF16 and FP8 serialization

**Files:**
- Modify: `ltx23_lora_merge/tests/test_merge.py`
- Modify: `ltx23_lora_merge/ltx23_merge/core.py`
- Create: `ltx23_lora_merge/merge_ltx23_loras.py`

- [ ] Write failing round-trip tests for BF16 and `float8_e4m3fn` safetensors output and metadata.
- [ ] Confirm expected failures.
- [ ] Implement atomic temporary-file writes, dtype conversion, and CLI orchestration.
- [ ] Run all tests and require zero failures.

### Task 5: Copy, merge, and validate the real LoRAs

**Files:**
- Create: `ltx23_lora_merge/source_copies/*.safetensors`
- Create: `ltx23_lora_merge/output/LTX2.3-OmniNFT150-OmniCine055-VBVR073-CAT-BF16-v1.safetensors`
- Create: `ltx23_lora_merge/output/LTX2.3-OmniNFT150-OmniCine055-VBVR073-CAT-FP8E4M3-v1.safetensors`
- Create: `ltx23_lora_merge/manifests/source_manifest.json`
- Create: `ltx23_lora_merge/manifests/merge_report.json`

- [ ] Run the CLI against the three absolute source paths.
- [ ] Verify source-copy hashes before merging.
- [ ] Reopen both outputs and validate all keys, dtypes, ranks, finite values, and metadata.
- [ ] Compute deterministic per-module numerical comparisons and aggregate error metrics.
- [ ] Recompute original source hashes and require exact equality with the initial manifest.

### Task 6: Final independent verification

**Files:**
- Create: `ltx23_lora_merge/README.md`

- [ ] Run `python -m unittest discover -s ltx23_lora_merge/tests -v`.
- [ ] Run the CLI in `--verify-only` mode against both outputs.
- [ ] Record file sizes and SHA-256 values in the README.
- [ ] Confirm no files were created or changed in the original ComfyUI LoRA directory.

No git commit steps are included because `D:\codex工作区` is not a Git repository.
