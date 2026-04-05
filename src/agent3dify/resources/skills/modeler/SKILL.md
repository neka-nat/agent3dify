---
name: cadquery-codegen
description: Use this skill when you need to implement a 3D model from the structured plan using CadQuery.
---
# cadquery-codegen

## Goal
Produce executable CadQuery code and artifacts.

## Required inputs
- spec/part_plan.json
- spec/view_map.json (if available)
- review/fix_plan.json (if available)
- templates/model_template.py

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
1. Read the plan and latest fix plan
2. Start from the template
3. Write generated/model.py
4. Execute:
   python generated/model.py --out-dir artifacts
5. If it fails, inspect the error, patch the code, and rerun

## Coding requirements
- The script must print exactly one JSON object to stdout
- The script must be idempotent
- Use readable helper functions
- Keep view export directions stable across revisions

## Important
Do not return success without actually executing the script.
