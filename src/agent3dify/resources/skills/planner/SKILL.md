---
name: drawing-analysis
description: Use this skill when you need to analyze a mechanical drawing image and turn it into a structured modeling plan.
---
# drawing-analysis

## Goal
Turn the drawing image into an explicit modeling specification.

## Required file outputs
- spec/part_plan.json
- spec/view_map.json

## Workflow
1. Read input/reference.png
2. Identify likely views and the part's main body
3. Infer dimensions and features with confidence values
4. If view regions are obvious enough, crop them with crop_reference_view
5. Save a structured plan

## part_plan.json recommended shape
{
  "units": "mm | inch | unknown",
  "overall_shape": "...",
  "overall_dimensions": {"x": null, "y": null, "z": null},
  "coordinate_assumptions": ["..."],
  "views_detected": ["front", "top", "right"],
  "features": [
    {
      "id": "feat_1",
      "type": "extrude | hole | pocket | fillet | chamfer | revolve | cut",
      "description": "...",
      "dimensions": {},
      "position": {},
      "order": 1,
      "confidence": 0.0
    }
  ],
  "ambiguities": [
    {"issue": "...", "impact": "...", "confidence": 0.0}
  ],
  "overall_confidence": 0.0
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
Be explicit about unknowns. Do not hide uncertainty.
