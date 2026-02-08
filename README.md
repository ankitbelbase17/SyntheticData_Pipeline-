# Closed-Loop Feedback Try-On System

This project implements a closed-loop feedback system for virtual try-on using **Flux 2 Klein 9B** for generation and **Qwen 3 VL 32B** for evaluation.

## System Overview

1.  **Input**: Person Image + Cloth Image.
2.  **Generation**: Flux model generates a try-on image.
3.  **Evaluation**: Qwen VLM analyzes the result against the inputs and providing feedback based on 7 hierarchical constraints.
4.  **Feedback Loop**:
    - If successful, saves to `output/correct_try_on`.
    - If failed, saves to `output/incorrect_try_on_X` and generates a new prompt.
    - Repeats up to 4 iterations.

## Directory Structure

```
local_data_pipeline/
├── input/
│   ├── person/             # Place person images here
│   └── cloth/              # Place cloth images here
├── output/
│   ├── correct_try_on/     # Successful generations
│   ├── incorrect_try_on_1/ # Failed Iteration 1
│   ├── incorrect_try_on_2/ # Failed Iteration 2
│   ├── incorrect_try_on_3/ # Failed Iteration 3
│   └── incorrect_try_on_4/ # Failed Iteration 4 (Max attempts)
├── models.py               # Flux and Qwen wrappers
├── feedback_loop.py        # Core logic
├── dataloader.py           # Data loading logic
├── utils.py                # Helper functions
├── main.py                 # Entry point
└── requirements.txt
```

## Setup

1.  Install requirements:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Model Integration**:
    - The current `models.py` uses **mock implementations** to demonstrate the logic and allow running on standard hardware without the heavyweight models.
    - To use the REAL models:
        1. Open `models.py`.
        2. Uncomment the `diffusers` / `transformers` loading code in `__init__`.
        3. Implement the actual inference calls in `generate()` and `evaluate()`.
        4. Ensure you have the model weights (e.g., HuggingFace cache or local path).

## Running

Run the main script:
```bash
python main.py
```

It will automatically create dummy data in `input/` if none exists.
