# agent3dify

A tool for converting 2D drawings into 3D models using a combination of AI agents.

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
  --planner-model google_genai:gemini-3.1-pro-preview \
  --modeler-model google_genai:gemini-3.1-pro-preview \
  --verifier-model google_genai:gemini-3.1-flash-preview
```
