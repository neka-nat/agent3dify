---
name: projection-verification
description: Use this skill when you need to compare rendered projections against the reference drawing and propose concrete fixes.
---
# projection-verification

## Goal
Evaluate whether the current model matches the drawing closely enough.

## Required inputs
- /artifacts/projections/*.png

## Optional inputs
- /input/reference.png
- /preprocessed/outline_only.png
- /preprocessed/*_ref.png

## Required outputs
- /review/compare_report.json
- /review/fix_plan.json

## Workflow
1. Read any extracted reference views under /preprocessed/
2. If the needed reference views are missing, call image_editor to extract them from /input/reference.png when possible
3. If no explicit extracted views exist, infer simple matches from filenames under /preprocessed/ and /artifacts/projections/
4. For each matched view, call compare_projection_pair
5. If compare output includes a diff board image, inspect it if needed
6. Summarize mismatches into a concise report
7. Create a patch-oriented fix plan for the builder
8. If comparison inputs are insufficient, write a blocked report that says which reference view could not be established

## compare_report.json recommended shape
{
  "status": "PASS | WARN | FAIL | BLOCKED",
  "views": {
    "front": {"score": 0.0, "mse": 0.0, "pixel_iou": 0.0, "edge_iou": 0.0, "diff_path": "..."},
    "top": {...},
    "right": {...}
  },
  "summary": ["..."],
  "overall_score": 0.0
}

## fix_plan.json recommended shape
{
  "status": "PASS | FIX_REQUIRED | BLOCKED",
  "edits": [
    {"priority": 1, "instruction": "...", "reason": "...", "affected_views": ["front"]}
  ],
  "recommendation": "..."
}
