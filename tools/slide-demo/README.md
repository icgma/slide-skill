# slide-skill · live demo (Flask)

  A single-file Flask web app that exposes `slide-skill` over HTTP so anyone can try it
  in a browser without installing Python: paste markdown, pick a theme, download a fully
  editable `.pptx` in ~300 ms.

  ## Run locally

  ```bash
  # from repo root
  pip install -e . flask
  PYTHONPATH=tools/slide/src python tools/slide-demo/app.py
  # open http://localhost:5000
  ```

  ## Deploy on Replit

  1. Fork this repo on Replit.
  2. Replit auto-detects `tools/slide-demo/app.py` as a Python service.
  3. Add a workflow: `PYTHONPATH=tools/slide/src python tools/slide-demo/app.py` on port 5000.
  4. Click **Publish** — your demo gets a public `*.replit.app` URL.

  ## Endpoints

  | Method | Path | Notes |
  |--|--|--|
  | `GET`  | `/`           | HTML form (Markdown textarea + theme selector + live SVG preview) |
  | `POST` | `/generate`   | form fields: `markdown`, `theme`, `name` → JSON `{pptx_url, slide_count, first_svg, last_svg, ...}` |
  | `GET`  | `/download/<job_id>/<file.pptx>` | streams the generated deck |
  | `GET`  | `/healthz`    | `{"ok":true}` |

  Markdown is capped at 100 KB. Generated jobs live in `/tmp/slide-skill-demo/` and are
  not persisted across restarts.
  