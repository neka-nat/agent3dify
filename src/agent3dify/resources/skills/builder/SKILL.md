---
name: cadquery-builder
description: Use this skill when you need to implement a 3D model from the drawing image with optional preprocessed views and verifier guidance.
---
# cadquery-builder

## Goal
Produce executable CadQuery code and CAD artifacts.

## Required inputs
- /input/reference.png

## Optional inputs
- /preprocessed/outline_only.png
- /preprocessed/*.png
- /review/fix_plan.json
- /templates/model_template.py

## Required outputs
- /generated/model.py
- /artifacts/model.step

## Optional outputs
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
2. Read optional preprocessed images when they exist
3. If /review/fix_plan.json exists, read it before revising the model and treat it as the detailed source of revision edits
4. If the raw drawing is cluttered, call image_editor to create a cleaner outline or extract a target view
5. Either start from /templates/model_template.py or write from scratch
6. Write /generated/model.py
7. Execute:
   python generated/model.py --out-dir artifacts
8. If it fails, inspect the error, patch the code, and rerun
9. First make sure /artifacts/model.step is produced
10. Add STL, projections, or reports only when they are clearly useful for the next step

## Important
- Use absolute paths with file tools, for example /input/reference.png and /generated/model.py
- Use relative paths only for shell execution commands
- Treat the drawing image as the primary source of truth
- Preprocessed images are optional guidance, not mandatory prerequisites
- If /review/fix_plan.json exists, it is the primary source for detailed revision targets
- The supervisor task description may summarize the current revision focus, but it is not a substitute for reading /review/fix_plan.json
- A first working STEP export matters more than polished reporting or full projection coverage
- The template is optional. Do not force yourself to fit the shape into it if starting fresh is simpler.
- Do not return success without actually executing the script
