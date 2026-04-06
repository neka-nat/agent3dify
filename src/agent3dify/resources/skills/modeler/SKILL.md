---
name: cadquery-codegen
description: Use this skill when you need to implement a 3D model from the structured plan and reference images using CadQuery.
---
# cadquery-codegen

## Goal
Produce executable CadQuery code and artifacts.

## Required inputs
- /input/reference.png
- /preprocessed/front_ref.png, /preprocessed/top_ref.png, /preprocessed/right_ref.png (if available)
- /spec/part_plan.json
- /spec/view_map.json (if available)
- /review/fix_plan.json (if available)
- /templates/model_template.py

## Required outputs
- generated/model.py
- artifacts/model.step
- artifacts/model.stl
- artifacts/projections/front.svg
- artifacts/projections/top.svg
- artifacts/projections/right.svg
- artifacts/projections/front.png
- artifacts/projections/top.png
- artifacts/projections/right.png
- artifacts/build_report.json

## Workflow
1. Read /input/reference.png with read_file
2. Read any cropped reference views under /preprocessed/
3. Read the plan and latest fix plan
4. Start from the template
5. Write /generated/model.py
6. Execute:
   python generated/model.py --out-dir artifacts
7. If it fails, inspect the error, patch the code, and rerun

## Coding requirements
- The script must print exactly one JSON object to stdout
- The script must be idempotent
- Use readable helper functions
- Keep view export directions stable across revisions

## Important
- Use absolute paths with file tools, for example /input/reference.png and /generated/model.py
- Use relative paths only for shell execution commands
- Treat the drawing image as a first-class input. If the plan conflicts with the image, prefer the image and preserve the ambiguity in comments or reports.
- Do not return success without actually executing the script.
