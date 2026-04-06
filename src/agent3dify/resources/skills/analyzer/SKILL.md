---
name: drawing-and-artifact-analysis
description: Use this skill when you need optional analysis of the drawing image or generated STEP artifact to help the builder make a better model.
---
# drawing-and-artifact-analysis

## Goal
Produce actionable analysis for the builder from the drawing and, when available, from the current STEP artifact.

## Required output
- /analysis/analyzer_report.json

## Optional outputs
- /analysis/view_map.json
- /preprocessed/front_ref.png
- /preprocessed/top_ref.png
- /preprocessed/right_ref.png
- Other helper images under /preprocessed/

## Workflow
1. Read /input/reference.png
2. If helpful, crop or preprocess regions of the drawing with the available tools
3. If /artifacts/model.step exists, inspect it with inspect_step_model
4. If /artifacts/build_report.json exists, read it for additional context
5. Write concrete builder hints and explicit ambiguities to /analysis/analyzer_report.json
6. If view-to-projection matching is clear enough, write /analysis/view_map.json

## analyzer_report.json recommended shape
{
  "drawing_analysis": {
    "views_detected": ["front", "top", "right"],
    "geometry_hints": ["..."],
    "coordinate_assumptions": ["..."],
    "ambiguities": [
      {"issue": "...", "impact": "...", "confidence": 0.0}
    ],
    "overall_confidence": 0.0
  },
  "step_analysis": {
    "step_path": "artifacts/model.step",
    "units_hint": "mm | m | inch | unknown",
    "entity_counts": {"ADVANCED_FACE": 0},
    "notes": ["..."]
  },
  "builder_hints": [
    {"priority": 1, "instruction": "...", "reason": "...", "source": "drawing | step | combined"}
  ]
}

## view_map.json recommended shape
{
  "front": {
    "reference_image": "preprocessed/front_ref.png",
    "candidate_image": "artifacts/projections/front.png"
  },
  "top": {
    "reference_image": "preprocessed/top_ref.png",
    "candidate_image": "artifacts/projections/top.png"
  },
  "right": {
    "reference_image": "preprocessed/right_ref.png",
    "candidate_image": "artifacts/projections/right.png"
  }
}

## Important
Do not write CadQuery code yourself. Be explicit about uncertainty and focus on information that changes what the builder should do next.
