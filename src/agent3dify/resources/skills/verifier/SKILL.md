---
name: projection-verification
description: Use this skill when you need to compare rendered projections against the reference drawing and propose concrete fixes.
---
# projection-verification

## Goal
Evaluate whether the current model matches the drawing closely enough.

## Required inputs
- spec/view_map.json
- artifacts/projections/*.png
- preprocessed/*_ref.png (if available)

## Required outputs
- review/compare_report.json
- review/fix_plan.json

## Workflow
1. Read spec/view_map.json
2. For each mapped view, call compare_projection_pair
3. If compare output includes a diff board image, inspect it if needed
4. Summarize mismatches into a concise report
5. Create a patch-oriented fix plan for the modeler

## compare_report.json recommended shape
{
  "status": "PASS | WARN | FAIL",
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
  "status": "PASS | FIX_REQUIRED",
  "edits": [
    {"priority": 1, "instruction": "...", "reason": "...", "affected_views": ["front"]}
  ]
}
