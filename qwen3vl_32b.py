"""
Qwen3-VL-32B Prompt Generation Pipeline
========================================
Reads a JSON file of keyword entries, batches them sequentially (batch_size=35),
uses Qwen3-VL-32B to generate image-generation prompts from the keywords,
and saves results as JSONL with async disk I/O to maximise GPU utilisation.

Usage:
    python qwen3vl_32b.py \
        --input sampled_keywords_7000.json \
        --output generated_prompts.jsonl \
        --batch_size 35 \
        --max_tokens 512 \
        --system_prompt system_prompt_for_human.txt
"""

import argparse
import json
import os
import time
import threading
import queue
from pathlib import Path
from typing import List, Dict, Any

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoProcessor, Qwen3VLForConditionalGeneration


# ─────────────────────────────────────────────────────
#  1.  Dataset — loads the JSON, yields items sequentially
# ─────────────────────────────────────────────────────
class KeywordDataset(Dataset):
    """
    PyTorch Dataset over the sampled_keywords JSON file.
    Each item is a dict:  {"id": str, "filename": str, "keywords": dict}
    Items are stored in the natural key order (1, 2, 3, …).
    """

    def __init__(self, json_path: str):
        with open(json_path, "r", encoding="utf-8") as f:
            raw: Dict[str, Any] = json.load(f)
        # Sort by integer key so iteration is deterministic & sequential
        self.entries: List[Dict[str, Any]] = []
        for key in sorted(raw.keys(), key=lambda k: int(k)):
            entry = raw[key]
            entry["id"] = key
            self.entries.append(entry)
        print(f"[Dataset] Loaded {len(self.entries)} entries from {json_path}")

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.entries[idx]


def collate_fn(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identity collate — keeps the list-of-dicts structure."""
    return batch


# ─────────────────────────────────────────────────────
#  2.  Build the user message from keywords
# ─────────────────────────────────────────────────────
def keywords_to_user_message(keywords: Dict[str, str]) -> str:
    """
    Converts the keyword dict into a clean user message for the VLM.
    """
    lines = []
    for k, v in keywords.items():
        pretty_key = k.replace("_", " ").title()
        lines.append(f"- {pretty_key}: {v}")
    return (
        "Generate a detailed image generation prompt for a person photo "
        "using these keywords:\n\n" + "\n".join(lines)
    )


# ─────────────────────────────────────────────────────
#  3.  Async JSONL writer (runs in a background thread)
# ─────────────────────────────────────────────────────
class AsyncJSONLWriter:
    """
    Receives batches of result dicts via a queue and writes them to a
    JSONL file in a background thread, so GPU inference is never blocked
    by disk I/O.
    """

    def __init__(self, output_path: str):
        self.output_path = output_path
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        self.total_written = 0

    def _writer_loop(self):
        with open(self.output_path, "a", encoding="utf-8") as f:
            while True:
                item = self._queue.get()
                if item is None:  # poison pill → stop
                    break
                # item is a list of dicts (one batch)
                for record in item:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                self.total_written += len(item)

    def enqueue_batch(self, batch_records: List[Dict[str, Any]]):
        self._queue.put(batch_records)

    def close(self):
        """Signal the writer to stop and wait for it to flush."""
        self._queue.put(None)
        self._thread.join()


# ─────────────────────────────────────────────────────
#  4.  Model loading
# ─────────────────────────────────────────────────────
def load_model(model_name: str):
    """
    Loads Qwen3-VL-32B-Instruct with bfloat16, Flash Attention 2,
    and auto device map.  We use the VL model class even for text-only
    input because the architecture requires it.
    """
    print(f"[Model] Loading tokenizer from {model_name} …")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="left",        # left-pad for batch generation
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[Model] Loading model from {model_name} …")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="flash_attention_2",
    )
    model.eval()
    print("[Model] Ready.")
    return tokenizer, model


# ─────────────────────────────────────────────────────
#  5.  Batch inference
# ─────────────────────────────────────────────────────
@torch.inference_mode()
def generate_batch(
    tokenizer,
    model,
    system_prompt: str,
    batch: List[Dict[str, Any]],
    max_new_tokens: int = 512,
) -> List[str]:
    """
    Runs batched generation over a list of keyword entries.
    Returns the generated prompt strings (one per entry).
    """
    # Build chat messages for each entry
    conversations = []
    for entry in batch:
        user_msg = keywords_to_user_message(entry["keywords"])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        conversations.append(text)

    # Tokenize with left-padding for batch generation
    encoded = tokenizer(
        conversations,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=4096,
    ).to(model.device)

    # Generate
    outputs = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,           # deterministic greedy for reproducibility
        temperature=1.0,
        top_p=1.0,
        pad_token_id=tokenizer.pad_token_id,
    )

    # Decode only the newly generated tokens
    input_len = encoded["input_ids"].shape[1]
    generated_ids = outputs[:, input_len:]
    prompts = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
    return [p.strip() for p in prompts]


# ─────────────────────────────────────────────────────
#  6.  Main pipeline
# ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate image prompts from keywords using Qwen3-VL-32B-instruct"
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Path to the sampled keywords JSON file",
    )
    parser.add_argument(
        "--output", type=str, default="generated_prompts.jsonl",
        help="Output JSONL file path (default: generated_prompts.jsonl)",
    )
    parser.add_argument(
        "--batch_size", type=int, default=35,
        help="Batch size for sequential dataloader (default: 35)",
    )
    parser.add_argument(
        "--max_tokens", type=int, default=512,
        help="Maximum new tokens to generate per sample (default: 512)",
    )
    parser.add_argument(
        "--system_prompt", type=str, default="system_prompt_for_human.txt",
        help="Path to the system prompt text file",
    )
    parser.add_argument(
        "--model_name", type=str, default="Qwen/Qwen3-VL-32B-Instruct",
        help="HuggingFace model id (default: Qwen/Qwen3-VL-32B-Instruct)",
    )
    parser.add_argument(
        "--no_resume", action="store_true",
        help="Disable auto-resume; overwrite the output file from scratch",
    )
    args = parser.parse_args()

    # ── Load system prompt ───────────────────────────
    system_prompt_path = Path(args.system_prompt)
    if not system_prompt_path.exists():
        raise FileNotFoundError(f"System prompt not found: {system_prompt_path}")
    system_prompt = system_prompt_path.read_text(encoding="utf-8").strip()
    print(f"[Config] System prompt loaded ({len(system_prompt)} chars)")

    # ── Resume logic (ON by default): find already-processed IDs ─
    already_done = set()
    if not args.no_resume and os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    already_done.add(str(record.get("id", "")))
        print(f"[Resume] Found {len(already_done)} already-processed entries, "
              f"will skip them and continue.")
    elif args.no_resume and os.path.exists(args.output):
        # Truncate the file so we start fresh
        open(args.output, "w").close()
        print(f"[Fresh] Overwriting {args.output}")

    # ── Dataset & DataLoader (sequential, no shuffle) ─
    dataset = KeywordDataset(args.input)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,              # ← sequential batches
        num_workers=min(os.cpu_count() or 1, 8),  # max CPU workers (capped at 8)
        collate_fn=collate_fn,
        persistent_workers=True,    # keep workers alive between batches
        drop_last=False,
    )

    # ── Load model ───────────────────────────────────
    tokenizer, model = load_model(args.model_name)

    # ── Async writer ─────────────────────────────────
    writer = AsyncJSONLWriter(args.output)

    # ── Inference loop ───────────────────────────────
    total_batches = len(loader)
    total_samples = len(dataset)
    remaining = total_samples - len(already_done)
    last_batch_size = total_samples % args.batch_size
    if last_batch_size == 0:
        last_batch_size = args.batch_size
    print(f"\n{'='*60}")
    print(f"  Total samples   : {total_samples}")
    print(f"  Already done    : {len(already_done)}")
    print(f"  Remaining       : {remaining}")
    print(f"  Batches         : {total_batches}  (last batch has {last_batch_size} samples)")
    print(f"  Batch size      : {args.batch_size}")
    print(f"  Max new tokens  : {args.max_tokens}")
    print(f"  Output          : {args.output}")
    print(f"  Resume          : {'OFF (fresh start)' if args.no_resume else 'ON (auto)'}")
    print(f"{'='*60}\n")

    global_start = time.time()
    processed = 0

    for batch_idx, batch in enumerate(loader):
        # ── Skip if resuming and entire batch is done ─
        if already_done:
            batch_ids = {entry["id"] for entry in batch}
            if batch_ids.issubset(already_done):
                processed += len(batch)
                print(f"  [Batch {batch_idx+1}/{total_batches}] "
                      f"Skipped (already processed)")
                continue
            # Filter out already-done entries within a partial batch
            batch = [e for e in batch if e["id"] not in already_done]

        batch_start = time.time()

        # ── Generate prompts for this batch ──────────
        generated_prompts = generate_batch(
            tokenizer, model, system_prompt, batch, args.max_tokens
        )

        batch_elapsed = time.time() - batch_start
        processed += len(batch)

        # ── Build output records (same schema + "prompt") ─
        batch_records = []
        for entry, prompt in zip(batch, generated_prompts):
            record = {
                "id": entry["id"],
                "filename": entry["filename"],
                "keywords": entry["keywords"],
                "prompt": prompt,               # ← new key
            }
            batch_records.append(record)

        # ── Enqueue for async writing (non-blocking) ─
        writer.enqueue_batch(batch_records)

        # ── Progress log ─────────────────────────────
        elapsed_total = time.time() - global_start
        rate = processed / elapsed_total if elapsed_total > 0 else 0
        eta = (total_samples - processed) / rate if rate > 0 else 0
        is_last = (batch_idx + 1) == total_batches
        tag = f" (final partial batch)" if is_last and len(batch) < args.batch_size else ""
        print(
            f"  [Batch {batch_idx+1}/{total_batches}] "
            f"{len(batch)} samples{tag} in {batch_elapsed:.1f}s "
            f"| Total: {processed}/{total_samples} "
            f"| Rate: {rate:.1f} samples/s "
            f"| ETA: {eta/60:.1f} min"
        )

    # ── Flush & close writer ─────────────────────────
    writer.close()

    total_elapsed = time.time() - global_start
    print(f"\n{'='*60}")
    print(f"  Done! {processed} prompts generated in {total_elapsed/60:.1f} min")
    print(f"  Output saved to: {args.output}")
    print(f"  Total written to disk: {writer.total_written}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
