# agent3dify

A tool for converting 2D drawings into 3D models using a combination of AI agents.

```mermaid
flowchart TD
    U[User] --> S[Supervisor]

    S -->|optional analysis| A[Drawing Analyzer]
    A -->|summary / completion| S

    S -->|build/revision task| B[CadQuery Builder]
    B -->|summary / completion| S

    S -->|optional verification| V[Render Verifier]
    V -->|summary / completion| S
```

```bash
uv sync
```

Run the agent with the default models:

```bash
uv run agent3dify --drawing data/b9-1.png
```

Run the agent with custom models:

```bash
uv run agent3dify \
  --drawing data/b9-1.png \
  --model openai:gpt-5 \
  --analyzer-model google_genai:gemini-3.1-pro-preview \
  --builder-model google_genai:gemini-3.1-pro-preview \
  --verifier-model google_genai:gemini-3.1-flash-preview
```

`cadquery-builder` is the primary subagent. `drawing-analyzer` and `render-verifier` are optional helpers that run only when their outputs would materially help the build or revision.

The builder now aims to get a working `artifacts/model.step` first. STL, projection images, and `build_report.json` are optional and are expected only when they help verification or debugging.
