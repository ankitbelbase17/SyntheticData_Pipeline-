# AWS S3 Directory Structure Requirements

Based on the current codebase configuration, the system assumes the following structure and conventions for your AWS S3 bucket.

## Directory Layout
The pipeline specifically looks for two root-level folders in your S3 bucket:

```text
s3://{bucket_name}/
├── males/
│   ├── 1.png
│   ├── 2.png
│   └── ...
└── females/
    ├── 1.png
    ├── 2.png
    └── ...
```

## detailed Requirements

### 1. Bucket Name
*   **Default**: `vton-pe`
*   **Configuration**: Can be changed using the `--bucket` argument in the CLI or `.sh` scripts.

### 2. Source Folders
*   **Required Paths**: `/males/` and `/females/`
*   **Behavior**: The script hardcodes checks for these two specific folders. Images placed in the root or other folders will be **ignored**.

### 3. Image Files
*   **Format**: Must be `.png` (Code checks for `key.lower().endswith('.png')`).
*   **Naming Convention**: 
    *   Recommended: `1.png`, `2.png`, `100.png` (Sequence numbers).
    *   Sorting: The script attempts to sort by the numeric value of the filename (`int(Path(x).stem)`).
    *   If filenames are not numeric, it falls back to alphabetical sorting (which may result in `1.png`, `10.png`, `2.png`).

### 4. Output Correspondence
Generated prompt files will mirror the source folder structure locally:
*   Source: `s3://bucket/males/5.png`
*   Output: `./outputs/prompts/males/5_edit.txt`

*   Source: `s3://bucket/females/12.png`
*   Output: `./outputs/prompts/females/12_edit.txt`
