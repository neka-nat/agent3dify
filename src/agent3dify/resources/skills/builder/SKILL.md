---
name: cadquery-builder
description: Use this skill when you need to implement a 3D model from the drawing image with optional analyzer and verifier guidance.
---
# cadquery-builder

## Goal
Produce executable CadQuery code and CAD artifacts.

## Required inputs
- /input/reference.png
- /templates/model_template.py

## Optional inputs
- /analysis/analyzer_report.json
- /analysis/view_map.json
- /preprocessed/*.png
- /review/fix_plan.json

## Required outputs
- /generated/model.py
- /artifacts/model.step
- /artifacts/model.stl
- /artifacts/projections/front.svg
- /artifacts/projections/top.svg
- /artifacts/projections/right.svg
- /artifacts/projections/front.png
- /artifacts/projections/top.png
- /artifacts/projections/right.png
- /artifacts/build_report.json

## Workflow
1. Read /input/reference.png with read_file
2. Read optional analyzer and verifier files when they exist
3. Start from the template
4. Write /generated/model.py
5. Execute:
   python generated/model.py --out-dir artifacts
6. If it fails, inspect the error, patch the code, and rerun

## Coding requirements
- The script must print exactly one JSON object to stdout
- The script must be idempotent
- Use readable helper functions
- Keep view export directions stable across revisions

## Important
- Use absolute paths with file tools, for example /input/reference.png and /generated/model.py
- Use relative paths only for shell execution commands
- Treat the drawing image as the primary source of truth
- Analyzer and verifier outputs are optional guidance, not mandatory prerequisites
- Do not return success without actually executing the script
