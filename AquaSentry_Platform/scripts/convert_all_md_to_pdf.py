#!/usr/bin/env python3
"""Convert all Markdown files in the repository to high-quality PDF documents.

Uses Python-Markdown with tables, fenced code, Mermaid.js for diagrams,
KaTeX for mathematics, and Google Chrome headless for rendering.
"""

import os
import re
import sys
import glob
import subprocess
import tempfile
import urllib.parse
import markdown

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  
  <!-- KaTeX for Math Rendering -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>

  <!-- Mermaid for Architecture Diagrams -->
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'default',
      flowchart: {{ useMaxWidth: false, htmlLabels: true }}
    }});
  </script>

  <style>
    @page {{
      size: A4;
      margin: 18mm 16mm 20mm 16mm;
      @bottom-right {{
        content: counter(page);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 9pt;
        color: #94a3b8;
      }}
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      line-height: 1.6;
      font-size: 13px;
      margin: 0;
      padding: 0;
      background: #ffffff;
    }}

    h1, h2, h3, h4, h5, h6 {{
      color: #0f172a;
      font-weight: 600;
      page-break-after: avoid;
      break-after: avoid;
    }}

    h1 {{
      font-size: 22px;
      border-bottom: 2px solid #0284c7;
      padding-bottom: 6px;
      margin-top: 0;
      margin-bottom: 14px;
      color: #0369a1;
    }}

    h2 {{
      font-size: 16px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
      margin-top: 24px;
      margin-bottom: 12px;
      color: #0f172a;
    }}

    h3 {{
      font-size: 14px;
      margin-top: 18px;
      margin-bottom: 8px;
      color: #1e293b;
    }}

    p {{
      margin: 10px 0;
    }}

    a {{
      color: #0284c7;
      text-decoration: none;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      page-break-inside: avoid;
      break-inside: avoid;
      font-size: 11.5px;
    }}

    th, td {{
      border: 1px solid #cbd5e1;
      padding: 7px 10px;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      background-color: #f1f5f9;
      font-weight: 600;
      color: #0f172a;
    }}

    tr:nth-child(even) {{
      background-color: #f8fafc;
    }}

    blockquote {{
      border-left: 4px solid #0284c7;
      background: #f0f9ff;
      margin: 14px 0;
      padding: 10px 14px;
      border-radius: 0 4px 4px 0;
      color: #0369a1;
      page-break-inside: avoid;
      break-inside: avoid;
    }}

    .alert-important {{
      border-left: 4px solid #8b5cf6;
      background: #f5f3ff;
      color: #6d28d9;
    }}

    .alert-warning {{
      border-left: 4px solid #f59e0b;
      background: #fffbeb;
      color: #b45309;
    }}

    .alert-caution {{
      border-left: 4px solid #ef4444;
      background: #fef2f2;
      color: #b91c1c;
    }}

    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
      font-size: 11.5px;
      background: #f1f5f9;
      padding: 2px 5px;
      border-radius: 4px;
      border: 1px solid #e2e8f0;
      color: #0f172a;
    }}

    pre {{
      background: #0f172a;
      border-radius: 6px;
      padding: 12px;
      margin: 14px 0;
      page-break-inside: avoid;
      break-inside: avoid;
      overflow-x: auto;
    }}

    pre code {{
      background: transparent;
      padding: 0;
      border: none;
      color: #f8fafc;
      font-size: 11px;
      line-height: 1.45;
    }}

    img {{
      max-width: 100%;
      max-height: 480px;
      height: auto;
      display: block;
      margin: 16px auto;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.12);
      page-break-inside: avoid;
      break-inside: avoid;
    }}

    .mermaid {{
      margin: 20px auto;
      text-align: center;
      page-break-inside: avoid;
      break-inside: avoid;
    }}

    hr {{
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 22px 0;
    }}

    ul, ol {{
      margin: 8px 0;
      padding-left: 24px;
    }}

    li {{
      margin-bottom: 4px;
    }}

    .doc-footer {{
      margin-top: 32px;
      padding-top: 10px;
      border-top: 1px solid #e2e8f0;
      font-size: 9.5px;
      color: #94a3b8;
      text-align: center;
    }}
  </style>
</head>
<body>
  {content}
  <div class="doc-footer">
    AquaSentry &copy; 2026 &middot; Environmental Water Quality &amp; Arsenic Surveillance Node
  </div>

  <script>
    document.addEventListener("DOMContentLoaded", function() {{
      if (window.renderMathInElement) {{
        renderMathInElement(document.body, {{
          delimiters: [
            {{left: "$$", right: "$$", display: true}},
            {{left: "$", right: "$", display: false}},
            {{left: "\\\\(", right: "\\\\)", display: false}},
            {{left: "\\\\[", right: "\\\\]", display: true}}
          ],
          throwOnError: false
        }});
      }}
    }});
  </script>
</body>
</html>
"""

def preprocess_markdown(md_text: str, md_dir: str) -> str:
    # 1. Resolve relative images to absolute file:// URLs
    def fix_image_path(match):
        alt = match.group(1)
        src = match.group(2).strip()
        # If already absolute or URL
        if src.startswith("http://") or src.startswith("https://") or src.startswith("file://"):
            return f"![{alt}]({src})"
        if src.startswith("/"):
            abs_path = os.path.abspath(src)
        else:
            abs_path = os.path.abspath(os.path.join(md_dir, src))
        
        if os.path.exists(abs_path):
            file_url = f"file://{abs_path}"
            return f"![{alt}]({file_url})"
        return f"![{alt}]({src})"

    md_text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', fix_image_path, md_text)

    # 2. Convert GitHub alert quotes (> [!NOTE], > [!IMPORTANT], etc.)
    md_text = re.sub(r'>\s*\[!NOTE\]\s*\n', '> **Note:** ', md_text)
    md_text = re.sub(r'>\s*\[!IMPORTANT\]\s*\n', '> **Important:** ', md_text)
    md_text = re.sub(r'>\s*\[!WARNING\]\s*\n', '> **Warning:** ', md_text)
    md_text = re.sub(r'>\s*\[!CAUTION\]\s*\n', '> **Caution:** ', md_text)
    md_text = re.sub(r'>\s*\[!TIP\]\s*\n', '> **Tip:** ', md_text)

    return md_text

def convert_md_file(md_path: str) -> str:
    md_abs = os.path.abspath(md_path)
    md_dir = os.path.dirname(md_abs)
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    pdf_path = os.path.splitext(md_abs)[0] + ".pdf"

    print(f"[*] Processing: {md_path} -> {pdf_path}")

    with open(md_abs, "r", encoding="utf-8") as f:
        raw_md = f.read()

    processed_md = preprocess_markdown(raw_md, md_dir)

    # Convert to HTML
    html_body = markdown.markdown(
        processed_md,
        extensions=[
            "tables",
            "fenced_code",
            "pymdownx.magiclink",
            "pymdownx.tasklist",
        ]
    )

    # Convert mermaid code blocks to <div class="mermaid">
    html_body = re.sub(
        r'<pre><code class="(?:language-)?mermaid">([\s\S]*?)</code></pre>',
        r'<div class="mermaid">\1</div>',
        html_body
    )

    # Title from first H1 or filename
    h1_match = re.search(r'<h1>(.*?)</h1>', html_body)
    title = h1_match.group(1) if h1_match else base_name

    full_html = HTML_TEMPLATE.format(title=title, content=html_body)

    # Write temporary HTML file next to md file so relative resources work
    temp_html_path = os.path.join(md_dir, f"._temp_{base_name}.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # Run Chrome Headless
    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--enable-local-file-accesses",
        "--virtual-time-budget=3500",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        temp_html_path,
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            size_kb = os.path.getsize(pdf_path) / 1024
            print(f"    [+] SUCCESS: {pdf_path} ({size_kb:.1f} KB)")
        else:
            print(f"    [-] FAILED to generate {pdf_path}: {proc.stderr}")
    finally:
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

    return pdf_path

def main():
    # Root is the parent of the scripts/ directory
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(scripts_dir)
    
    # Collect all markdown files in workspace excluding third-party venv
    md_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Ignore venv, .git, .system_generated
        dirnames[:] = [d for d in dirnames if d not in [".venv", "venv", ".git", "__pycache__", ".system_generated"]]
        if "site-packages" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".md"):
                md_files.append(os.path.join(dirpath, f))

    md_files.sort()
    print(f"Found {len(md_files)} markdown files to convert to PDF:")
    for m in md_files:
        print(f"  - {os.path.relpath(m, root_dir)}")
    print("=" * 60)

    for m in md_files:
        convert_md_file(m)

    print("=" * 60)
    print("All markdown files converted successfully!")

if __name__ == "__main__":
    main()
