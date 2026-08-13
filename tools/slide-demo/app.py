"""Online demo for slide-skill: paste markdown -> download .pptx.

Single-file Flask app. Run with:
    PYTHONPATH=tools/slide/src python tools/slide-demo/app.py
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

# Ensure slide_skill is importable regardless of how the workflow launches us.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]
_SLIDE_SRC = _REPO_ROOT / "tools" / "slide" / "src"
if str(_SLIDE_SRC) not in sys.path:
    sys.path.insert(0, str(_SLIDE_SRC))

from flask import Flask, Response, jsonify, render_template_string, request, send_file

from slide_skill.intake import convert_file
from slide_skill.project import init_project
from slide_skill.svg_pipeline import create_spec, generate_svg, finalize_svg, write_svg_report
from slide_skill.exporter import export_project
from slide_skill.themes import list_themes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("slide-demo")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB request body cap

OUTPUT_ROOT = Path(tempfile.gettempdir()) / "slide-skill-demo"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# Jobs older than this are purged. Keep short — the user downloads immediately.
JOB_TTL_SECONDS = 30 * 60  # 30 minutes
_PURGE_LOCK = threading.Lock()
_LAST_PURGE = 0.0


def _purge_expired_jobs() -> None:
    """Best-effort TTL sweep of OUTPUT_ROOT. Cheap, idempotent, throttled to once/min."""
    global _LAST_PURGE
    now = time.time()
    if now - _LAST_PURGE < 60:
        return
    if not _PURGE_LOCK.acquire(blocking=False):
        return
    try:
        _LAST_PURGE = now
        cutoff = now - JOB_TTL_SECONDS
        for child in OUTPUT_ROOT.iterdir():
            try:
                if child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                continue
    finally:
        _PURGE_LOCK.release()

SAMPLE_MD = """# 大语言模型驱动的产品设计

> 一份用 slide-skill 一行命令生成的中文演示文稿样例

## 我们要解决的问题

- 传统幻灯片工具需要手动排版每一页
- 设计师与工程师之间的协作成本高
- 改一处文字,整页排版都要重做
- AI 生成的内容难以直接落到精美的母版

## 核心数据

- 用户调研覆盖 **2400** 位设计师
- 平均每份提案节省 **6.5** 小时
- 模板复用率提升至 **89%**
- 客户满意度评分 **4.8 / 5**

## 方案对比

### 传统流程
- PPT 手动调整,每页平均 12 分钟
- 改字号要重新对齐所有元素

### slide-skill 流程
- Markdown 输入,2 秒生成完整 .pptx
- 主题切换瞬间完成,排版自动重算

## 使用场景

| 场景 | 输入 | 输出 |
|---|---|---|
| 产品周会 | 需求、指标、风险 | 汇报材料 |
| 课程培训 | 讲义、案例、练习 | 教学课件 |
| 路演答辩 | 商业计划书 | 结构化路演稿 |
| 项目复盘 | Markdown 纪要 | 管理简报 |

## 设计原则

> 好看的默认结果来自稳定的设计约束:先锁定主题色、字体和版式节奏,再让每页围绕一个清晰信息层级展开。

## 工作流概览

1. 输入文档:Markdown / PDF / DOCX / PPTX / 网页资料
2. 内容规划:自动切片、选择布局、生成讲者备注
3. 视觉生成:基于主题生成 SVG 页面
4. 质量检查:文本提取、结构校验、截图复核

## 质量闸门

- 100% PPTX 包结构可打开
- 0 个占位符残留
- 0 个文本溢出错误
- 0 个高严重度视觉 warning

## 渲染管道

- Markdown → 智能切片(LLM 可选)
- 切片 → SVG(主题驱动,完全确定性)
- SVG → 原生 DrawingML(渐变、形状、文字均可在 PowerPoint 内编辑)
- 全程 ~2 秒,零 API key 也能跑通

## 主题系统

| 主题 | 适合场景 | 视觉倾向 |
|---|---|---|
| dark-tech | 技术汇报 | 深色、系统感、强对比 |
| light-corporate | 管理层汇报 | 浅色、清爽、稳健 |
| warm-editorial | 课程和观点 | 温暖、叙事、杂志感 |
| data-forward | 经营分析 | 指标优先、结构明确 |

## 交付物

- `.pptx`:可打开、可编辑、可继续美化的 PowerPoint 文件
- `svg_final/`:每页 SVG 源,用于复核和二次生成
- `qa/QA.md`:文本、结构、占位符和导出检查
- `qa/rendered/`:渲染截图,用于人工或视觉模型审查

## 发展规划

- Q1 2026:根据内容密度动态切换版式
- Q2 2026:自动生成图标、示意图和背景视觉
- Q3 2026:把可读性、美观度纳入默认 QA
- Q4 2026:支持局部重写、局部替换和批注修复

## 立即开始

- 安装:`pip install -e .`
- 命令:`slide-skill quickstart input.md --theme dark-tech`
- 项目主页:github.com/icgma/slide-skill
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>slide-skill · live demo</title>
<style>
  :root { --bg:#0F172A; --surface:#1E293B; --text:#F1F5F9; --body:#94A3B8; --accent:#3B82F6; --muted:#334155; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; background:linear-gradient(180deg,#0F172A 0%,#020617 100%); color:var(--text);
         font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif;
         padding:40px 20px; }
  .container { max-width: 1100px; margin: 0 auto; }
  header { text-align:center; margin-bottom: 36px; }
  header h1 { font-size: 44px; margin: 0 0 8px; font-weight: 800; letter-spacing: -0.02em; }
  header h1 span { color: var(--accent); }
  header p { color: var(--body); margin: 0; font-size: 17px; }
  header a { color: var(--accent); text-decoration: none; }
  header a:hover { text-decoration: underline; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media (max-width: 880px) { .grid { grid-template-columns: 1fr; } }
  .card { background: linear-gradient(180deg, var(--surface) 0%, #0F172A 100%);
          border: 1px solid var(--muted); border-radius: 14px; padding: 24px;
          box-shadow: 0 10px 40px rgba(0,0,0,.4); }
  .card h2 { margin: 0 0 14px; font-size: 18px; font-weight: 700; color: var(--text); }
  label { display:block; color: var(--body); font-size: 13px; text-transform: uppercase;
          letter-spacing: 0.05em; margin-bottom: 8px; font-weight: 600; }
  textarea, select, input[type=text] {
    width: 100%; background: #0B1220; color: var(--text); border: 1px solid var(--muted);
    border-radius: 8px; padding: 12px 14px; font-size: 14px;
    font-family: 'SF Mono', ui-monospace, 'JetBrains Mono', Menlo, monospace; }
  textarea { min-height: 420px; resize: vertical; line-height: 1.55; }
  textarea:focus, select:focus, input:focus { outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59,130,246,.18); }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px; }
  button { background: var(--accent); color: white; border: none; padding: 14px 28px;
           font-size: 15px; font-weight: 700; border-radius: 8px; cursor: pointer;
           width: 100%; transition: transform .08s ease, box-shadow .15s ease; }
  button:hover { box-shadow: 0 8px 24px rgba(59,130,246,.4); }
  button:active { transform: translateY(1px); }
  button:disabled { background: var(--muted); cursor: not-allowed; opacity: 0.6; }
  .preview { display:flex; flex-direction:column; gap:14px; align-items:center; }
  .preview .empty { color: var(--body); text-align:center; padding: 60px 20px; font-size:14px; }
  .preview svg, .preview img { width:100%; max-width: 480px; border-radius: 6px;
    border: 1px solid var(--muted); display: block; }
  .download-bar { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.5);
    border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; display: flex;
    justify-content: space-between; align-items: center; }
  .download-bar a { background: rgb(34,197,94); color: white; padding: 8px 16px;
    border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 13px; }
  .meta { color: var(--body); font-size: 13px; }
  .error { background: rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.5);
           color:#FCA5A5; padding:12px 14px; border-radius:8px; margin-bottom: 14px; }
  .badge { display:inline-block; padding: 3px 10px; background: var(--muted); color: var(--text);
           border-radius:99px; font-size:11px; margin-right:6px; font-weight: 600; }
  footer { text-align:center; margin-top: 40px; color: var(--body); font-size: 13px; }
  footer a { color: var(--body); }
  .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.4);
    border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: -2px; margin-right: 8px;}
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1><span>slide-skill</span> · live demo</h1>
    <p>Markdown in &nbsp;→&nbsp; fully-editable .pptx out &nbsp;·&nbsp; 2 seconds &nbsp;·&nbsp; no API key.
       Source on <a href="https://github.com/icgma/slide-skill" target="_blank" rel="noopener">GitHub</a>.</p>
  </header>

  <div class="grid">
    <div class="card">
      <h2>1. Paste your markdown</h2>
      <form id="gen" method="post" action="/generate">
        <div class="row">
          <div>
            <label for="theme">Theme</label>
            <select name="theme" id="theme">
              {% for t in themes %}
              <option value="{{ t }}" {% if t == 'dark-tech' %}selected{% endif %}>{{ t }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label for="name">Project name</label>
            <input type="text" name="name" id="name" value="demo" maxlength="40" />
          </div>
        </div>
        <label for="markdown">Markdown source</label>
        <textarea name="markdown" id="markdown" required>{{ sample }}</textarea>
        <div style="margin-top:14px;">
          <button type="submit" id="submitBtn">Generate .pptx →</button>
        </div>
      </form>
    </div>

    <div class="card">
      <h2>2. Preview &amp; download</h2>
      <div class="preview" id="preview">
        <div class="empty">
          <p>Click <strong>Generate .pptx</strong> on the left.<br/>
          The first slide preview and download link appear here.</p>
          <p style="margin-top:24px;">
            <span class="badge">SVG-first</span>
            <span class="badge">Native gradients</span>
            <span class="badge">CJK supported</span>
          </p>
        </div>
      </div>
    </div>
  </div>

  <footer>
    Powered by slide-skill v2.1 · open source on <a href="https://github.com/icgma/slide-skill">GitHub</a><br/>
    All processing happens on this server. Your markdown is not stored beyond the generation request.
  </footer>
</div>

<script>
  const form = document.getElementById('gen');
  const preview = document.getElementById('preview');
  const submitBtn = document.getElementById('submitBtn');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span>Generating…';
    preview.innerHTML = '<div class="empty"><span class="spinner"></span> Rendering slides…</div>';
    try {
      const fd = new FormData(form);
      const res = await fetch('/generate', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok || data.error) {
        preview.innerHTML = '<div class="error">' + (data.error || ('HTTP ' + res.status)) + '</div>';
      } else {
        let html = '<div class="download-bar">'
          + '<div><div style="font-weight:700;">' + data.slide_count + ' slides ready</div>'
          + '<div class="meta">' + data.theme + ' · generated in ' + data.elapsed_ms + ' ms · '
          + Math.round(data.size_bytes/1024) + ' KB</div></div>'
          + '<a href="' + data.pptx_url + '" download>Download .pptx</a></div>';
        if (data.first_svg) {
          html += '<div>' + data.first_svg + '</div>';
        }
        if (data.slide_count > 1 && data.last_svg) {
          html += '<div style="margin-top:14px;">' + data.last_svg + '</div>';
        }
        preview.innerHTML = html;
      }
    } catch (err) {
      preview.innerHTML = '<div class="error">' + err.message + '</div>';
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = 'Generate .pptx →';
    }
  });
</script>
</body>
</html>
"""


@app.get("/")
def index() -> Response:
    return render_template_string(INDEX_HTML, themes=list_themes(), sample=SAMPLE_MD)


@app.get("/healthz")
def healthz() -> Response:
    return jsonify({"ok": True})


@app.post("/generate")
def generate() -> Response:
    markdown = (request.form.get("markdown") or "").strip()
    theme_name = (request.form.get("theme") or "dark-tech").strip()
    project_name = (request.form.get("name") or "demo").strip() or "demo"
    project_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in project_name)[:40] or "demo"

    if not markdown:
        return jsonify({"error": "Empty markdown."}), 400
    if len(markdown) > 100_000:
        return jsonify({"error": "Markdown too large (>100KB)."}), 400

    job_id = uuid.uuid4().hex[:10]
    job_base = OUTPUT_ROOT / job_id
    job_base.mkdir(parents=True, exist_ok=True)
    md_input = job_base / "input.md"
    md_input.write_text(markdown, encoding="utf-8")

    _purge_expired_jobs()

    started = time.time()
    try:
        project = init_project(project_name, "ppt169", str(job_base), overwrite=True)
        source_md = project / "sources" / "input.md"
        convert_file(str(md_input), source_md)
        create_spec(project, source_md, theme_name=theme_name)
        generate_svg(project, source_md)
        write_svg_report(project)
        finalize_svg(project)
        pptx_path = Path(export_project(project))
    except Exception:  # noqa: BLE001 — log full trace, return generic message
        log.exception("generate failed (job_id=%s, theme=%s)", job_id, theme_name)
        shutil.rmtree(job_base, ignore_errors=True)
        return jsonify({"error": "Generation failed. Check that your markdown is valid and try a different theme."}), 500

    elapsed_ms = int((time.time() - started) * 1000)
    if not pptx_path.exists():
        return jsonify({"error": "Generation finished but no .pptx file was produced."}), 500

    svg_dir = project / "svg_final"
    svgs = sorted(svg_dir.glob("slide_*.svg"))
    first_svg = svgs[0].read_text(encoding="utf-8") if svgs else ""
    last_svg = svgs[-1].read_text(encoding="utf-8") if len(svgs) > 1 else ""

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "slide_count": len(svgs),
        "theme": theme_name,
        "elapsed_ms": elapsed_ms,
        "size_bytes": pptx_path.stat().st_size,
        "pptx_url": f"/download/{job_id}/{pptx_path.name}",
        "first_svg": first_svg,
        "last_svg": last_svg,
    })


@app.get("/preview/<job_id>/html")
def preview_html(job_id: str) -> Response:
    if not job_id.isalnum():
        return jsonify({"error": "Bad job id"}), 400
    job_root = (OUTPUT_ROOT / job_id).resolve()
    if not job_root.is_dir():
        return jsonify({"error": "Job not found or expired"}), 404
    from slide_skill.html_preview import render_preview_html
    import json as _json
    for project_dir in job_root.iterdir():
        if (project_dir / "svg_final").is_dir():
            lang = "en"
            lock = project_dir / "spec_lock.json"
            if lock.exists():
                try:
                    lang = _json.loads(lock.read_text(encoding="utf-8")).get("lang", "en")
                except Exception:  # noqa: BLE001
                    pass
            html_str = render_preview_html(project_dir, title=project_dir.name, lang=lang)
            return Response(html_str, mimetype="text/html; charset=utf-8")
    return jsonify({"error": "No finalized slides for this job"}), 404


@app.errorhandler(413)
def _too_large(_err):
    return jsonify({"error": "Request too large. Markdown input is capped at 100 KB."}), 413


@app.errorhandler(404)
def _not_found(_err):
    return jsonify({"error": "Not found."}), 404


# Filename whitelist: alnum, dot, underscore, dash only. Rejects glob
# metacharacters (*, ?, [], {}), path separators, and NUL — closing the
# path-traversal-via-glob hole flagged in .planning/codebase/CONCERNS.md.
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@app.get("/download/<job_id>/<path:filename>")
def download(job_id: str, filename: str) -> Response:
    if not job_id.isalnum():
        return jsonify({"error": "Bad job id"}), 400
    safe = Path(filename).name
    if not _SAFE_FILENAME_RE.match(safe) or safe in (".", ".."):
        return jsonify({"error": "Bad filename"}), 400

    job_root = (OUTPUT_ROOT / job_id).resolve()
    if not job_root.is_dir():
        return jsonify({"error": "File not found or expired"}), 404

    # Walk job_root/<project>/exports/<safe> without using glob — safe is now
    # guaranteed metacharacter-free, but resolve() each candidate and confirm
    # it is contained within job_root before serving (defense in depth).
    chosen: Path | None = None
    for project_dir in job_root.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = (project_dir / "exports" / safe).resolve()
        try:
            candidate.relative_to(job_root)
        except ValueError:
            continue
        if candidate.is_file():
            chosen = candidate
            break

    if chosen is None:
        return jsonify({"error": "File not found or expired"}), 404

    return send_file(
        chosen,
        as_attachment=True,
        download_name=safe,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
