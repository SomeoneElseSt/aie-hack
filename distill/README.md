# Local distillation: your repetitive work moves off the cloud

The lane router watches which turns you repeat. For routine git mechanics it mines your real sessions, distills a
tiny local model from the cloud model's *verified* answers, and admits it to the lane roster only if it proves itself
on held-out work. Failed candidates are rolled back; runtime failures fall back to the cloud and become training data.

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 1. Mine | `mine.py` | Keyword prefilter over Claude Code / Codex / OpenCode history, then SubQ classifies each short message: git mechanics? which intent? |
| 2. Dataset | `gen_data.py` | Real phrasings + teacher paraphrases in the same voice. Muse Wonder writes commands for fresh sandbox repos; only answers that pass an executable check are kept. |
| 3. Fine-tune | `mlx_lm.lora` | LoRA on Qwen2.5-Coder-1.5B-Instruct (4-bit), locally on Apple Silicon, ~2 min. Each adapter is a versioned file. |
| 4. Gate | `evaluate.py` | Held-out cases (real phrasings, unseen repo seeds), commands executed and checked. Adopt only if ≥ floor, within 5 pts of the cloud teacher, and no regression vs the active model. Decision history in `roster.json`. |
| 5. Serve | `mlx_lm.server` + `extensions/lane-router/local-lane.ts` | When a model is adopted, SubQ checks each short message; matching git requests run on the local model before any cloud model sees them. |

## Results

| Model | Held-out pass | commit | commit+push | push | undo | Avg latency | Decision |
|---|---|---|---|---|---|---|---|
| Muse Wonder (cloud teacher) | 65% | 70% | 80% | 100% | 10% | 5.9s | reference |
| Qwen 1.5B, untrained | 48% | 80% | 50% | 60% | 0% | 0.3s | reference |
| **Qwen 1.5B + v1** | **100%** | 100% | 100% | 100% | 100% | **0.4s** | **adopted** |
| Qwen 1.5B + v2 candidate (under-trained) | 88% | 100% | 80% | 100% | 70% | 0.4s | rolled back |

Mining found 104 messages mentioning git, 17 of them routine git mechanics. 128 of 160 teacher examples passed
execution and were used for training. The student beats its teacher because it only learned from answers that
worked (e.g. undo = `git reset --soft HEAD~1`, where the teacher often reverted instead).

Live in Pi: "commit and push it in my style, no coauthor" → SubQ (commit_push, 99.6%) → local v1 →
`git add ledger.py settle.py` / `git commit -m "add settle script and update ledger"` / `git push origin main`,
1.6s end to end, no cloud model call.

## Run

```bash
python3 distill/mine.py                      # needs SUBQ_API_KEY
python3 distill/gen_data.py                  # needs META_API_KEY
mlx_lm.lora --model mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit --train --data distill/data \
  --iters 200 --batch-size 4 --learning-rate 1e-4 --mask-prompt --adapter-path distill/adapters/v1
~/.local/share/uv/tools/mlx-lm/bin/python distill/evaluate.py v1 --adapter adapters/v1
mlx_lm.server --model mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit --adapter-path distill/models/v1 --port 8089
./run.sh --model lanes/auto                  # git requests now run locally
```

Raw mined messages stay local (`distill/data/` is gitignored); `results/summary.json` has the numbers.
