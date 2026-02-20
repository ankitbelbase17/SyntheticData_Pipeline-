"""
Qwen3-VL-32B Edit Prompt Generator
====================================
For each entry in the keyword JSON files (medium/hard × female/male),
feed the VLM the paired person image + keyword description and ask it to
write a precise image-editing instruction.

Parallel inference across N GPUs using srun (RANK/LOCAL_RANK from SLURM env).

Output per entry:
  /iopsstor/scratch/cscs/dbartaula/edit_prompts/{file_name}.txt
  /iopsstor/scratch/cscs/dbartaula/edit_prompts/edit_prompts_rank{N}.jsonl
"""

import argparse
import json
import os
import queue
import sys
import threading
import time
import traceback as tb
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Unbuffered output — critical for SLURM log visibility
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ─────────────────────────────────────────────────────────────
# Rank info — works with both srun and torchrun
# srun sets:     SLURM_PROCID / SLURM_LOCALID / SLURM_NTASKS
# torchrun sets: RANK / LOCAL_RANK / WORLD_SIZE
# ─────────────────────────────────────────────────────────────
RANK       = int(os.environ.get("RANK",       os.environ.get("SLURM_PROCID",  "0")))
LOCAL_RANK = int(os.environ.get("LOCAL_RANK", os.environ.get("SLURM_LOCALID", "0")))
WORLD_SIZE = int(os.environ.get("WORLD_SIZE", os.environ.get("SLURM_NTASKS",  "1")))
IS_MAIN    = (RANK == 0)

def log(msg: str):
    print(f"[GPU {LOCAL_RANK} | RANK {RANK}] {msg}", flush=True)

# ─────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────
try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    from PIL import Image
except ImportError as e:
    print(f"[RANK {RANK}] CRITICAL IMPORT ERROR: {e}", flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a vision-language assistant. Given an image of a person and a JSON of keyword attributes, produce one natural-prose editing prompt for FLUX.2 Klein 9B distilled. This model executes literally. You are the only reasoning layer. Output serves a virtual try-on dataset so face and garment clarity must be protected.

Flux edits images and can add objects, obstacles, and scene elements not present in the source. The source image provides identity and body reference only.


OBSERVE (silent, never output)

Catalogue: functional arms, hands, legs, feet; mobility aids; body type and build; skin tone; face structure, expression, facial hair; hair color, style, length; age; every garment by name, color, fabric, fit; footwear; accessories; background; lighting source, quality, direction, temperature; camera angle.

Preserve clothing identity only: name, color, fabric, fit. Never preserve wrinkles. Pose changes alter drape and Flux handles it.


ANATOMY CONSTRAINTS (hard, no exceptions)

Only three things are anatomy constraints: a keyword requires a limb visibly absent from the subject, the subject uses a wheelchair and a keyword requires standing, or a required limb is fully out of frame. Scene context is never an anatomy constraint.

Adapt to available limbs if a limb is missing. Convert pose to seated if wheelchair-bound. Leave out-of-frame limbs unmentioned.


CONFLICT RESOLUTION (silent, never output)

POSE IS PRIORITY. Describe the pose fully and completely first. Then fit the occlusion around what the pose leaves available.

2-HAND BUDGET: Count hands used by pose and hands used by occlusion. If 2 or fewer, proceed. If more than 2, keep the pose intact and adapt the occlusion to the remaining free hands. If the pose uses both hands and the occlusion also needs both, reduce the occlusion to a single-hand equivalent, for example a bundle carried in one arm rather than two. Never compromise the pose to fit the occlusion.

BODY STATE: If pose and occlusion conflict on standing versus sitting, pose wins. If pose implies movement, preserve it even if the occlusion implies stationary. Resolve to whichever state best preserves the pose.


OCCLUSION SIZE

Estimate body coverage. Examples below are illustrative only.

Less than 15 percent is small, for example a phone or wallet. Use as-is. 15 to 40 percent is medium, for example a handbag or backpack. Use as-is. 40 to 70 percent is large, for example a big box or suitcase. Reduce by tilting to the side or lowering to hip level so torso stays partially visible. More than 70 percent or covering the face is extreme. Reinterpret as a medium equivalent at waist level.

Face must stay forward-facing and visible unless a keyword explicitly targets it such as a mask or sunglasses. Occlusions must not rise above the collarbone. Partial torso or lower-body occlusion is fine. Full-body occlusion is not acceptable.


WRITE THE PROMPT

Order: pose and body position first, then scene elements added, then occlusion placed, then every limb accounted for, then face anchored, then preserved attributes named one by one, then scene and lighting.

POSE FIRST: Describe the full body position from the pose keyword with commitment. If the pose says wide stance stepping over an obstacle, write that stance fully and with energy. Do not hedge or soften the pose.

SCENE ELEMENTS: If the pose or occlusion implies an object or surface not in the source, name it and place it explicitly. If the pose says stepping over an obstacle, place a named concrete object such as a low concrete barrier or a wooden beam on the ground and describe the subject stepping over it directly. The specific object is your choice based on scene plausibility but it must be named.

LIMB PLACEMENT: Every hand must be described as doing something. Every foot stance must be stated. Describe limbs by location and action, never by joint angle. These are examples only since actual descriptions depend on the input: correct language sounds like "right foot planted behind the barrier, left leg raised and crossing over"; incorrect language sounds like "leg raised at 90 degrees." Apply the 5-second test: can a healthy person hold this for 5 seconds? If yes, use it. If borderline, soften it. If impossible, use the nearest natural resting position. Safe defaults when no instruction exists: free hand hangs at side; standing feet shoulder-width apart. Avoid these because Flux 9B renders them poorly: individual finger descriptions, arms behind the back, legs crossed while standing, arms fully extended overhead. Never repeat a body part word more than twice.

FACE ANCHOR: Unless a keyword changes face direction or adds a face-region occlusion, end the subject description with: face forward, features clearly visible.

PRESERVATION: Never write "keep everything else the same." Name every preserved attribute explicitly: skin tone, hair color and style and length, facial structure and expression, every garment by name and color and fit, footwear, body type and build, background elements, lighting quality and direction and temperature, camera angle.

PROSE: Natural flowing prose only. No lists or tags. Positive assertions only since Flux ignores negatives. Hard token limit: under 300 tokens.


CHECKLIST (silent, fix before outputting, never mention)

Pose described fully and first. Scene elements from keywords named and placed. Both hands placed. Foot stance stated. Face anchored. Limbs pass 5-second test. No joint mechanics. No body part word more than twice. Occlusion adapted to pose, not the other way. Occlusion below collarbone unless keyword says otherwise. No invented limbs. Clothing identity preserved without wrinkle state. All preserved attributes named. All positive assertions. Under 300 tokens.


OUTPUT

Output only the final prose prompt. No preamble, explanation, or checklist.

ANATOMY CONFLICT exception: use only when a limb required by a keyword is physically absent and no adaptation exists. Prepend "ANATOMY CONFLICT:" and one sentence, then write the best prompt without the impossible keyword. Use sparingly.
"""

def build_user_prompt(entry: Dict) -> str:
    """Pass keyword attributes as a JSON object — the system prompt handles all reasoning."""
    # Build the keyword JSON: only include fields that exist in the entry
    keywords = {}
    if "pose" in entry:
        keywords["pose"] = entry["pose"]
    if "occlusion" in entry:
        keywords["occlusion"] = entry["occlusion"]
    return json.dumps(keywords, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────
# Dataset — keyword entries sharded by rank
# ─────────────────────────────────────────────────────────────
class KeywordDataset(Dataset):
    """
    Loads all 4 keyword JSON files, pairs each entry with its gender image,
    and returns this rank's shard (interleaved by rank index).
    """
    def __init__(
        self,
        json_dir: str,
        image_dir: str,
        rank: int = 0,
        world_size: int = 1,
        max_samples: int = 3000,   # total across ALL GPUs
    ):
        self.image_dir = image_dir

        # All 4 JSON files and their gender pairing
        json_files = [
            ("medium_female_keywords.json", "female"),
            ("medium_male_keywords.json",   "male"),
            ("hard_female_keywords.json",   "female"),
            ("hard_male_keywords.json",     "male"),
        ]

        all_entries = []
        for fname, gender in json_files:
            fpath = os.path.join(json_dir, fname)
            if not os.path.exists(fpath):
                if IS_MAIN:
                    log(f"WARNING: JSON not found: {fpath} — skipping")
                continue
            with open(fpath, encoding="utf-8") as f:
                entries = json.load(f)
            for entry in entries:
                all_entries.append({
                    **entry,
                    "gender": gender,
                    "source_file": fname,
                })
            if IS_MAIN:
                log(f"  Loaded {len(entries)} entries from {fname}")

        # Cap total entries to max_samples (trim before sharding)
        if len(all_entries) > max_samples:
            all_entries = all_entries[:max_samples]

        # Shard by rank (interleaved)
        self.my_entries = [e for i, e in enumerate(all_entries) if i % world_size == rank]

        if IS_MAIN:
            log(f"Total entries (capped at {max_samples}): {len(all_entries)} | "
                f"Per-GPU shard: {len(self.my_entries)}")

    def __len__(self):
        return len(self.my_entries)

    def __getitem__(self, i):
        entry = self.my_entries[i]
        img_path = os.path.join(self.image_dir, f"{entry['gender']}.png")
        image = Image.open(img_path).convert("RGB")
        return {
            "image":       image,
            "entry":       entry,
            "user_prompt": build_user_prompt(entry),
        }

# ─────────────────────────────────────────────────────────────
# Collate function — build model inputs per batch
# ─────────────────────────────────────────────────────────────
def make_collate_fn(processor):
    pad_id = processor.tokenizer.pad_token_id or 0

    def collate_fn(items: List[Dict]) -> Dict:
        encoded = []
        for it in items:
            msgs = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": it["image"]},
                        {"type": "text",  "text":  it["user_prompt"]},
                    ],
                },
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
            "pixel_values":   torch.cat([e["pixel_values"]   for e in encoded]),
            "image_grid_thw": torch.cat([e["image_grid_thw"] for e in encoded]),
            # Metadata (not tensors)
            "entries":        [it["entry"]       for it in items],
            "user_prompts":   [it["user_prompt"] for it in items],
        }
    return collate_fn

# ─────────────────────────────────────────────────────────────
# Async Disk Writer
# GPU puts (entry, text, metadata) into a queue immediately after
# decoding, then continues to the next batch. A background thread
# drains the queue and writes .txt + .jsonl to disk.
# ─────────────────────────────────────────────────────────────
_WRITER_SENTINEL = None   # signals the writer thread to stop

class AsyncWriter:
    """
    Background thread that writes results to disk so the GPU
    never blocks on file I/O.
    """
    def __init__(self, output_dir: str, jsonl_path: str, queue_maxsize: int = 512):
        self.output_dir = output_dir
        self.jsonl_path = jsonl_path
        self._q: queue.Queue = queue.Queue(maxsize=queue_maxsize)
        self._errors: List[Exception] = []
        self._thread = threading.Thread(
            target=self._worker, name=f"disk-writer-rank{RANK}", daemon=True
        )
        self._thread.start()

    def put(self, record: Dict):
        """Non-blocking enqueue from the main (GPU) thread."""
        self._q.put(record)   # blocks only if queue is full (512 items)

    def _worker(self):
        """Background thread: drain queue and write to disk."""
        with open(self.jsonl_path, "w", encoding="utf-8", buffering=1) as f_jsonl:
            while True:
                record = self._q.get()
                if record is _WRITER_SENTINEL:
                    break
                try:
                    # Write individual .txt
                    txt_path = os.path.join(self.output_dir, f"{record['file_name']}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f_txt:
                        f_txt.write(record["edit_prompt"])
                    # Append to JSONL
                    f_jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
                except Exception as e:
                    self._errors.append(e)
                    log(f"[AsyncWriter] ERROR writing {record.get('file_name')}: {e}")
                finally:
                    self._q.task_done()

    def close(self):
        """Wait for all queued writes to finish, then stop the thread."""
        self._q.join()                  # blocks until queue is empty
        self._q.put(_WRITER_SENTINEL)   # signal thread to exit
        self._thread.join(timeout=60)
        if self._errors:
            log(f"[AsyncWriter] {len(self._errors)} write error(s) occurred.")
        return len(self._errors) == 0

# ─────────────────────────────────────────────────────────────
# Load model — always flash_attention_2
# ─────────────────────────────────────────────────────────────
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
    except torch.cuda.OutOfMemoryError:
        log(f"FATAL: CUDA OOM. Free: {torch.cuda.mem_get_info(device)[0]/1e9:.1f}GB "
            f"/ Total: {torch.cuda.mem_get_info(device)[1]/1e9:.1f}GB")
        raise
    except Exception as e:
        log(f"FATAL: Model load failed: {e}")
        raise

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_dir",   type=str,
                        default="/capstor/store/cscs/swissai/a168/dbartaula",
                        help="Directory containing the 4 keyword JSON files")
    parser.add_argument("--image_dir",  type=str,
                        default="/capstor/store/cscs/swissai/a168/dbartaula",
                        help="Directory containing female.png and male.png")
    parser.add_argument("--output_dir", type=str,
                        default="/iopsstor/scratch/cscs/dbartaula/edit_prompts",
                        help="Output directory for .txt and .jsonl files")
    parser.add_argument("--max_samples",    type=int, default=3000,
                        help="Total generations across all GPUs (trimmed before sharding)")
    parser.add_argument("--batch_size",     type=int, default=48,
                        help="Per-GPU batch size  (3000/16 GPUs=188/GPU → ceil(188/48)=4 batches)")
    parser.add_argument("--max_new_tokens", type=int, default=256,
                        help="Max tokens for the generated edit prompt")
    parser.add_argument("--model_name",     type=str,
                        default="Qwen/Qwen3-VL-32B-Instruct")
    args = parser.parse_args()

    import socket
    device     = torch.device("cuda:0")
    torch.cuda.set_device(device)
    JOB_START  = datetime.now()

    log(f"host={socket.gethostname()} | RANK={RANK} LOCAL_RANK={LOCAL_RANK} "
        f"WORLD_SIZE={WORLD_SIZE} | start={JOB_START.strftime('%Y-%m-%d %H:%M:%S')}")

    if IS_MAIN:
        print(f"\n{'='*60}", flush=True)
        print(f"Edit Prompt Generator  |  {WORLD_SIZE} GPUs", flush=True)
        print(f"Per-GPU batch: {args.batch_size} | Max new tokens: {args.max_new_tokens}", flush=True)
        print(f"JSON dir   : {args.json_dir}", flush=True)
        print(f"Image dir  : {args.image_dir}", flush=True)
        print(f"Output dir : {args.output_dir}", flush=True)
        print(f"Job start  : {JOB_START.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"{'='*60}\n", flush=True)

    # 1. Output dir
    os.makedirs(args.output_dir, exist_ok=True)

    # 2. Processor
    log(f"Loading processor: {args.model_name}")
    processor = AutoProcessor.from_pretrained(args.model_name, trust_remote_code=True)
    processor.tokenizer.padding_side = "left"
    log("Processor ready.")

    # 3. Dataset (this rank's shard)
    log("Loading keyword datasets ...")
    dataset = KeywordDataset(
        json_dir=args.json_dir,
        image_dir=args.image_dir,
        rank=RANK,
        world_size=WORLD_SIZE,
        max_samples=args.max_samples,
    )
    log(f"Dataset: {len(dataset)} entries for this rank  "
        f"| batch_size={args.batch_size}  "
        f"| batches={-(-len(dataset)//args.batch_size)} (ceil)")

    # 4. DataLoader
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        collate_fn=make_collate_fn(processor),
        num_workers=8,
        pin_memory=True,
        drop_last=False,
    )
    log(f"DataLoader ready: {len(loader)} batches for this GPU.")

    # 5. Model (all GPUs load in parallel)
    model = load_model(args.model_name, device)

    # 6. Barrier — start inference simultaneously on all GPUs
    import torch.distributed as dist
    if not dist.is_initialized():
        dist.init_process_group(backend="nccl", init_method="env://")
    log(f"Waiting for all GPUs to finish loading ...")
    dist.barrier()
    log(f"All GPUs ready — starting inference in parallel!")

    # ─────────────────────────────────────────────────────────
    # Inference loop
    # ─────────────────────────────────────────────────────────
    total_start          = time.perf_counter()
    batch_latencies: List[float] = []
    total_samples_done   = 0
    jsonl_path           = os.path.join(args.output_dir, f"edit_prompts_rank{RANK}.jsonl")

    log(f"JSONL output: {jsonl_path}")

    # Each GPU process has its OWN independent AsyncWriter + queue.
    # No sharing between GPUs — this is purely per-process/per-GPU.
    # queue_maxsize = batch_size * 4 → holds 4 batches worth of results
    # (= 4 × 48 = 192 slots), so the GPU can push all 4 batches ahead
    # without ever blocking on the queue, even if the disk writer is slow.
    writer = AsyncWriter(
        output_dir=args.output_dir,
        jsonl_path=jsonl_path,
        queue_maxsize=args.batch_size * 4,   # 4 batches worth per GPU
    )
    log(f"Async disk writer started  "
        f"(per-GPU queue, maxsize={args.batch_size * 4} = {args.batch_size} × 4 batches).")

    for batch_idx, batch in enumerate(loader):
        bsz = batch["input_ids"].shape[0]

        ids  = batch["input_ids"].to(device)
        mask = batch["attention_mask"].to(device)
        pix  = batch["pixel_values"].to(device)
        grid = batch["image_grid_thw"].to(device)

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
        batch_time = time.perf_counter() - t0
        per_sample = batch_time / bsz
        batch_latencies.append(batch_time)
        total_samples_done += bsz

        # Decode — remove prompt tokens
        input_len = ids.shape[1]
        new_ids   = gen_ids[:, input_len:]
        texts     = processor.tokenizer.batch_decode(
            new_ids, skip_special_tokens=True
        )

        # Latency log
        log(f"Batch {batch_idx+1}/{len(loader)} | "
            f"Samples: {bsz} | "
            f"Batch time: {batch_time:.2f}s | "
            f"Per-sample: {per_sample:.3f}s | "
            f"Writer queue: {writer._q.qsize()}")

        # ── Async write: enqueue all items, GPU moves to next batch immediately
        for entry, text in zip(batch["entries"], texts):
            writer.put({
                "file_name":     entry["file_name"],
                "serial_number": entry.get("serial_number"),
                "gender":        entry.get("gender"),
                "source_file":   entry.get("source_file"),
                "pose":          entry.get("pose"),
                "occlusion":     entry.get("occlusion"),
                "edit_prompt":   text.strip(),
                "gpu_rank":      RANK,
                "batch_idx":     batch_idx,
                "batch_time_s":  round(batch_time, 4),
                "per_sample_s":  round(per_sample, 4),
            })
        # ← GPU immediately fetches next batch; writer thread handles disk in background

    # Wait for all pending writes to land before moving to summary
    log("Inference done — flushing writer queue to disk ...")
    ok = writer.close()
    log(f"Writer finished. {'All files written OK.' if ok else 'Some write errors occurred!'}")

    # ─────────────────────────────────────────────────────────
    # Per-GPU latency summary
    # ─────────────────────────────────────────────────────────
    total_time  = time.perf_counter() - total_start
    avg_batch   = sum(batch_latencies) / len(batch_latencies) if batch_latencies else 0
    throughput  = total_samples_done / total_time if total_time > 0 else 0

    log(f"\n{'─'*50}")
    log(f"PER-GPU LATENCY  (Rank {RANK} / GPU {LOCAL_RANK})")
    log(f"{'─'*50}")
    log(f"  Prompts generated       : {total_samples_done}")
    log(f"  Batches                 : {len(batch_latencies)}")
    log(f"  Total wall time         : {total_time:.2f}s")
    log(f"  Avg batch latency       : {avg_batch:.3f}s")
    log(f"  Avg per-sample latency  : {total_time/total_samples_done:.4f}s")
    log(f"  GPU throughput          : {throughput:.3f} prompts/sec")
    log(f"  JSONL output            : {jsonl_path}")
    log(f"{'─'*50}\n")

    # ─────────────────────────────────────────────────────────
    # Combined summary (rank 0 only, after all_reduce)
    # ─────────────────────────────────────────────────────────
    t_tensor       = torch.tensor([total_time],         dtype=torch.float64, device=device)
    samples_tensor = torch.tensor([total_samples_done], dtype=torch.int64,   device=device)
    dist.barrier()
    dist.all_reduce(t_tensor,       op=dist.ReduceOp.MAX)
    dist.all_reduce(samples_tensor, op=dist.ReduceOp.SUM)

    if IS_MAIN:
        wall           = t_tensor.item()
        total_samples  = samples_tensor.item()
        JOB_END        = datetime.now()
        job_wall_s     = (JOB_END - JOB_START).total_seconds()

        print(f"\n{'='*60}", flush=True)
        print(f"COMBINED SUMMARY  ({WORLD_SIZE} GPUs across {WORLD_SIZE//4} nodes)", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"  Job start                : {JOB_START.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"  Job exit                 : {JOB_END.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"  Total job wall time      : {job_wall_s:.1f}s  "
              f"({int(job_wall_s//60)}m {int(job_wall_s%60)}s)", flush=True)
        print(f"  ─────────────────────────────────────────────", flush=True)
        print(f"  Total prompts generated  : {int(total_samples)}", flush=True)
        print(f"  Inference wall time      : {wall:.2f}s  (slowest GPU)", flush=True)
        print(f"  Effective per-prompt     : {wall/total_samples:.4f}s",     flush=True)
        print(f"  Combined throughput      : {total_samples/wall:.3f} prompts/sec  "
              f"({WORLD_SIZE}× parallel speedup)", flush=True)
        print(f"  Output dir               : {args.output_dir}", flush=True)
        print(f"{'='*60}\n", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL EXCEPTION:")
        tb.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)
