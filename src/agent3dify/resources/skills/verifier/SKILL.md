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
- /analysis/view_map.json
- /preprocessed/*_ref.png

## Required outputs
- /review/compare_report.json
- /review/fix_plan.json

## Workflow
1. Read /analysis/view_map.json when it exists
2. If no explicit view map exists, infer simple matches from filenames under /preprocessed/ and /artifacts/projections/
3. For each matched view, call compare_projection_pair
4. If compare output includes a diff board image, inspect it if needed
5. Summarize mismatches into a concise report
6. Create a patch-oriented fix plan for the builder
7. If comparison inputs are insufficient, write a blocked report that recommends running drawing-analyzer

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
