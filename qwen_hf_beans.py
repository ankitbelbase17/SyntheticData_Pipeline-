"""
Qwen3-VL-32B Beans Pathology — Multi-GPU Inference (DDP style, torchrun)
=========================================================================
Each GPU:
  - Loads the FULL model independently
  - Gets its own shard of the dataset (every 4th sample starting at rank)
  - Saves results to beans_predictions_rankN.jsonl
  - Prints per-batch and per-sample latency

Run with:
    torchrun --nproc_per_node=4 qwen_hf_beans.py --batch_size 32
"""

import argparse
import json
import os
import sys
import time
import traceback as tb
from typing import List, Dict, Any

# Force unbuffered output — critical for SLURM log visibility
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ─────────────────────────────────────
# Read rank info — works with both torchrun and srun
# torchrun sets: RANK, LOCAL_RANK, WORLD_SIZE
# srun sets:     SLURM_PROCID, SLURM_LOCALID, SLURM_NTASKS
# ─────────────────────────────────────
RANK       = int(os.environ.get("RANK",       os.environ.get("SLURM_PROCID",  "0")))
LOCAL_RANK = int(os.environ.get("LOCAL_RANK", os.environ.get("SLURM_LOCALID", "0")))
WORLD_SIZE = int(os.environ.get("WORLD_SIZE", os.environ.get("SLURM_NTASKS",  "1")))
IS_MAIN    = (RANK == 0)

def log(msg: str):
    """Print with rank prefix so logs from different GPUs are distinguishable."""
    print(f"[GPU {LOCAL_RANK}] {msg}", flush=True)

# ─────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────
try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    from datasets import load_dataset
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
except ImportError as e:
    print(f"[GPU {LOCAL_RANK}] CRITICAL IMPORT ERROR: {e}", flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
IMAGE_SIZE = 512
LABELS = {0: "angular_leaf_spot", 1: "bean_rust", 2: "healthy"}

USER_PROMPTS = [
    "Describe this image in detail.",
    "What objects can you identify?",
    "What is the plant condition?",
    "Is disease visible?",
]

SYSTEM_PROMPT = (
    "You are an expert agricultural vision-language analysis system designed for "
    "high precision plant pathology and crop health diagnostics. You must produce "
    "detailed, structured, technically grounded observations when analyzing plant "
    "images. Always examine morphology, texture variation, color gradients, "
    "disease markers, lesion boundaries, fungal or bacterial signatures, "
    "environmental stress indicators, and spatial distribution patterns.\n\n"
    "Your responses must include visible structural elements, abnormal "
    "pigmentation patterns, necrotic regions, chlorosis signals, lesion geometry, "
    "spread patterns, severity estimation, biological plausibility, and uncertainty "
    "notes when evidence is weak. You should reason visually and avoid guessing "
    "beyond observable evidence. Do not hallucinate objects not present.\n\n"
    "Prefer measurable descriptions over vague language. Use structured "
    "multi-sentence outputs with technical vocabulary and analytical tone. "
    "When unsure, state uncertainty explicitly and explain why."
)

# ─────────────────────────────────────────────
# Dataset (sharded per rank)
# ─────────────────────────────────────────────
class BeansDS(Dataset):
    """
    Loads the beans dataset and returns only this rank's shard.
    Shard logic: indices where (idx % WORLD_SIZE == RANK)
    """
    def __init__(self, split="train", max_samples=None, rank=0, world_size=1):
        log(f"Loading HF dataset split='{split}'...")
        ds = load_dataset("AI-Lab-Makerere/beans", split=split)
        if max_samples is not None:
            ds = ds.select(range(min(max_samples, len(ds))))

        # Select this GPU's shard
        all_indices = list(range(len(ds)))
        self.my_indices = [i for i in all_indices if i % world_size == rank]
        self.ds = ds
        log(f"Shard: {len(self.my_indices)} samples out of {len(ds)} total "
            f"(rank={rank}, world_size={world_size})")

    def __len__(self):
        return len(self.my_indices)

    def __getitem__(self, i):
        global_idx = self.my_indices[i]
        row = self.ds[global_idx]
        img = row["image"].convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE))
        return {
            "image":        img,
            "prompt":       USER_PROMPTS[global_idx % len(USER_PROMPTS)],
            "label":        LABELS[row["labels"]],
            "global_idx":   global_idx,   # original dataset index
        }

# ─────────────────────────────────────────────
# Collate function (tokenize + prepare images)
# ─────────────────────────────────────────────
def make_collate_fn(processor):
    pad_id = processor.tokenizer.pad_token_id or 0

    def collate_fn(items: List[Dict]) -> Dict:
        encoded = []
        for it in items:
            msgs = [
                {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
                {"role": "user",   "content": [
                    {"type": "image", "image": it["image"]},
                    {"type": "text",  "text":  it["prompt"]},
                ]},
            ]
            enc = processor.apply_chat_template(
                msgs,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            )
            encoded.append(enc)

        # Left-pad to max length
        max_len = max(e["input_ids"].shape[-1] for e in encoded)

        def lpad(t, fill):
            gap = max_len - t.shape[-1]
            return t if gap == 0 else torch.cat(
                [torch.full((1, gap), fill, dtype=t.dtype), t], dim=-1
            )

        return {
            "input_ids":      torch.cat([lpad(e["input_ids"],      pad_id) for e in encoded]),
            "attention_mask": torch.cat([lpad(e["attention_mask"], 0)      for e in encoded]),
            "pixel_values":   torch.cat([e["pixel_values"]                 for e in encoded]),
            "image_grid_thw": torch.cat([e["image_grid_thw"]               for e in encoded]),
            # Metadata (strings/ints, not tensors)
            "global_indices": [it["global_idx"] for it in items],
            "labels":         [it["label"]       for it in items],
            "prompts":        [it["prompt"]       for it in items],
        }
    return collate_fn

# ─────────────────────────────────────────────
# Load model — always flash_attention_2
# (qwen3vl-fa2 environment guarantees flash_attn 2.7.2+)
# ─────────────────────────────────────────────
def load_model(model_name: str, device: torch.device):
    log(f"Loading model with flash_attention_2 ...")
    try:
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            device_map=None,
            trust_remote_code=True,
        )
        model.to(device)
        model.eval()
        log(f"Model loaded on {device} with flash_attention_2 ✓")
        return model
    except torch.cuda.OutOfMemoryError as e:
        log(f"FATAL: CUDA OOM loading model on {device}. "
            f"Free VRAM: {torch.cuda.mem_get_info(device)[0] / 1e9:.1f} GB "
            f"/ Total: {torch.cuda.mem_get_info(device)[1] / 1e9:.1f} GB")
        raise
    except Exception as e:
        log(f"FATAL: Failed to load model with flash_attention_2: {e}")
        raise

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_size",    type=int, default=32,
                        help="Per-GPU batch size")
    parser.add_argument("--max_samples",   type=int, default=240,
                        help="Total samples to process (split across all GPUs)")
    parser.add_argument("--max_new_tokens",type=int, default=512)
    parser.add_argument("--model_name",    type=str,
                        default="Qwen/Qwen3-VL-32B-Instruct")
    parser.add_argument("--output_dir",    type=str, default=".",
                        help="Directory to save per-GPU output files")
    args = parser.parse_args()

    # With srun --gpus-per-task=1, SLURM remaps each task's GPU to cuda:0
    # via CUDA_VISIBLE_DEVICES. Using cuda:{LOCAL_RANK} would crash on ranks 1/2/3.
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)

    import socket
    from datetime import datetime
    JOB_START_TIME = datetime.now()

    # Every rank announces itself (confirms 2-node spread)
    log(f"Running on host={socket.gethostname()}  "
        f"RANK={RANK}  LOCAL_RANK={LOCAL_RANK}  WORLD_SIZE={WORLD_SIZE}  "
        f"start={JOB_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}")

    if IS_MAIN:
        print(f"\n{'='*60}", flush=True)
        print(f"Qwen3-VL Beans Inference  |  {WORLD_SIZE} GPUs across nodes", flush=True)
        print(f"Per-GPU batch: {args.batch_size}  |  "
              f"Total samples: {args.max_samples}  |  "
              f"Max new tokens: {args.max_new_tokens}", flush=True)
        print(f"Job start: {JOB_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"{'='*60}\n", flush=True)

    # 1. Processor
    log(f"Loading processor: {args.model_name}")
    processor = AutoProcessor.from_pretrained(args.model_name, trust_remote_code=True)
    processor.tokenizer.padding_side = "left"
    log("Processor ready.")

    # 2. Dataset (this rank's shard)
    dataset = BeansDS(
        max_samples=args.max_samples,
        rank=RANK,
        world_size=WORLD_SIZE,
    )

    # 3. DataLoader
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        collate_fn=make_collate_fn(processor),
        num_workers=2,
        pin_memory=True,
        drop_last=False,
    )
    log(f"Batches for this GPU: {len(loader)}")

    # 4. Model — load on all GPUs in parallel, then sync before inference.
    #    Since each GPU needs the full model, they all load from disk simultaneously.
    #    A barrier afterwards ensures all GPUs START INFERENCE at the same time,
    #    so no GPU races ahead while others are still loading.
    log(f"Loading model (all GPUs in parallel)...")
    model = load_model(args.model_name, device)

    # Barrier: wait for all ranks to finish loading before starting inference
    # This ensures true parallel inference across all 4 GPUs.
    import torch.distributed as dist
    if not dist.is_initialized():
        dist.init_process_group(backend="nccl", init_method="env://")
    log(f"Model ready. Waiting for all GPUs to finish loading...")
    dist.barrier()
    log(f"All GPUs ready — starting inference NOW in parallel!")

    # 5. Output file — one per GPU, clearly named
    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir,
                            f"beans_predictions_rank{RANK}.jsonl")
    log(f"Saving results to: {out_path}")

    # ─────────────────────────────────────────
    # Inference loop
    # ─────────────────────────────────────────
    total_start = time.perf_counter()
    batch_latencies: List[float] = []
    sample_latencies: List[float] = []
    total_samples_done = 0

    log("Starting inference loop...")

    with open(out_path, "w", encoding="utf-8") as f_out:
        for batch_idx, batch in enumerate(loader):
            bsz = batch["input_ids"].shape[0]

            # Move tensors to this GPU
            ids   = batch["input_ids"].to(device)
            mask  = batch["attention_mask"].to(device)
            pix   = batch["pixel_values"].to(device)
            grid  = batch["image_grid_thw"].to(device)

            # Sync before timing
            torch.cuda.synchronize(device)
            t0 = time.perf_counter()

            with torch.inference_mode():
                gen_ids = model.generate(
                    input_ids=ids,
                    attention_mask=mask,
                    pixel_values=pix,
                    image_grid_thw=grid,
                    max_new_tokens=args.max_new_tokens,
                    use_cache=True,
                    do_sample=False,
                )

            torch.cuda.synchronize(device)
            batch_time  = time.perf_counter() - t0
            per_sample  = batch_time / bsz

            batch_latencies.append(batch_time)
            sample_latencies.append(per_sample)
            total_samples_done += bsz

            # Decode (trim prompt tokens)
            input_len = ids.shape[1]
            new_ids   = gen_ids[:, input_len:]
            texts     = processor.tokenizer.batch_decode(
                new_ids, skip_special_tokens=True
            )

            # Latency log
            log(f"Batch {batch_idx+1}/{len(loader)} | "
                f"Samples: {bsz} | "
                f"Batch time: {batch_time:.2f}s | "
                f"Per-sample: {per_sample:.3f}s")

            # Save results
            for i in range(bsz):
                record = {
                    "global_idx":      batch["global_indices"][i],
                    "label":           batch["labels"][i],
                    "prompt":          batch["prompts"][i],
                    "output":          texts[i].strip(),
                    "gpu_rank":        RANK,
                    "local_rank":      LOCAL_RANK,
                    "batch_idx":       batch_idx,
                    "batch_time_s":    round(batch_time, 4),
                    "per_sample_s":    round(per_sample, 4),
                }
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ─────────────────────────────────────────
    # Per-GPU Latency Summary (each GPU prints)
    # ─────────────────────────────────────────
    total_time = time.perf_counter() - total_start
    avg_batch  = sum(batch_latencies) / len(batch_latencies) if batch_latencies else 0
    avg_sample = sum(sample_latencies) / len(sample_latencies) if sample_latencies else 0
    throughput_local = total_samples_done / total_time if total_time > 0 else 0

    log(f"\n{'─'*50}")
    log(f"PER-GPU LATENCY  (Rank {RANK} / GPU {LOCAL_RANK})")
    log(f"{'─'*50}")
    log(f"  Samples processed       : {total_samples_done}")
    log(f"  Batches                 : {len(batch_latencies)}")
    log(f"  Total wall time         : {total_time:.2f}s")
    log(f"  Avg batch latency       : {avg_batch:.3f}s")
    log(f"  Avg per-sample latency  : {avg_sample:.4f}s")
    log(f"  Min/Max batch latency   : {min(batch_latencies, default=0):.3f}s / {max(batch_latencies, default=0):.3f}s")
    log(f"  GPU throughput          : {throughput_local:.3f} samples/sec")
    log(f"  Output file             : {out_path}")
    log(f"{'─'*50}\n")

    # ─────────────────────────────────────────────────────
    # Combined Summary (GPU 0 only, after gathering stats)
    # All GPUs ran in parallel → effective latency = wall_time / total_all_gpus_samples
    # ─────────────────────────────────────────────────────

    # Use all_reduce to sum total samples and find max wall time across all ranks
    t_tensor       = torch.tensor([total_time],          dtype=torch.float64, device=device)
    samples_tensor = torch.tensor([total_samples_done],  dtype=torch.int64,   device=device)

    dist.barrier()
    dist.all_reduce(t_tensor,       op=dist.ReduceOp.MAX)   # max wall time (slowest GPU)
    dist.all_reduce(samples_tensor, op=dist.ReduceOp.SUM)   # sum of all samples

    if IS_MAIN:
        combined_wall   = t_tensor.item()
        combined_samples= samples_tensor.item()
        effective_per_sample  = combined_wall / combined_samples if combined_samples > 0 else 0
        combined_throughput   = combined_samples / combined_wall if combined_wall > 0 else 0

        JOB_END_TIME = datetime.now()
        total_job_s  = (JOB_END_TIME - JOB_START_TIME).total_seconds()

        print(f"\n{'='*60}", flush=True)
        print(f"COMBINED LATENCY SUMMARY  ({WORLD_SIZE} GPUs across {WORLD_SIZE//4} nodes)", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"  Job start                : {JOB_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"  Job exit                 : {JOB_END_TIME.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"  Total job wall time      : {total_job_s:.1f}s  "
              f"({int(total_job_s//60)}m {int(total_job_s%60)}s)", flush=True)
        print(f"  ─────────────────────────────────────────────", flush=True)
        print(f"  Total samples (all GPUs) : {int(combined_samples)}", flush=True)
        print(f"  Inference wall time      : {combined_wall:.2f}s  (slowest GPU)", flush=True)
        print(f"  Effective per-sample     : {effective_per_sample:.4f}s  "
              f"[wall_time / {int(combined_samples)} samples / {WORLD_SIZE} GPUs]",
              flush=True)
        print(f"  Combined throughput      : {combined_throughput:.3f} samples/sec  "
              f"({WORLD_SIZE}× parallel speedup)", flush=True)
        print(f"{'='*60}\n", flush=True)





if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(f"FATAL EXCEPTION:")
        tb.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)