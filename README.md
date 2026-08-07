# Website Analyzer

Website Analyzer is an asynchronous framework for recording websites that you are authorized to access. It creates an offline evidence dataset for frontend documentation and AI-assisted reconstruction: routes, rendered DOM, responsive screenshots, same-origin assets, browser network traffic, forms, components, UI states, navigation flows, and inferred design tokens.

The tool never bypasses authentication, CAPTCHA, Cloudflare, email/SMS verification, or 2FA. It pauses the persistent Chromium session for a human to complete such work and resumes only after confirmation.

## Installation

Python 3.13+ is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

## Crawl a website

```powershell
website-analyzer crawl https://example.com
website-analyzer crawl https://example.com --headless --depth unlimited --max-pages 1000
website-analyzer crawl https://example.com --headless --ui-states 30 --output output-example
website-analyzer crawl https://example.com --login
```

`--login` starts headed Chromium and pauses so you can sign in to an account you are authorized to use. It cannot be combined with `--headless`.

The crawler follows same-origin links and captures safe client-side states exposed through tabs, menus, dropdowns, accordions, dialogs, and pagination. It does not submit forms and rejects controls labelled as account creation, sign-out, delete/remove, purchase, payment, checkout, or similar side effects. `--ui-states` controls the per-page exploration limit.

## Generate or refresh reports

```powershell
website-analyzer analyze output-example
website-analyzer report output-example
```

## Output structure

```text
output-example/
  metadata.sqlite3              # pages, assets, requests, components and flow edges
  sitemap.xml
  pages/ html/ dom/ design/     # per route and UI-state evidence
  screenshots/                  # desktop, laptop, tablet and mobile - full + viewport
  images/ css/ js/ fonts/ videos/ assets/
  responses/ apis/ flows/ reports/
  markdown/
    design_system.md
    component_tree.md
    ai-rebuild-handoff/
      README.md
      implementation_manifest.json
      pages/                    # route-by-route reconstruction specifications
```

## AI reconstruction handoff

After a crawl, start another IDE AI agent with:

```text
<output>/markdown/ai-rebuild-handoff/README.md
```

That document links to a JSON route/state manifest and one Markdown specification for every captured page or UI state. Each specification contains screenshot evidence, HTML path, detected components, forms and validation, links, asset references, and visual-token samples. It also links to the inferred design system, navigation flows, and observed API documentation.

## Architecture

- `browser/`: persistent Playwright Chromium and manual-verification gate.
- `crawler/`: bounded same-origin route crawling and safe UI-state exploration.
- `pages/`, `dom/`, `design/`: rendered page evidence and analysis.
- `network/`, `apis/`: passive request recording and evidence-based API docs.
- `assets/`: async same-origin archival with SHA-256 deduplication.
- `storage/`: SQLite metadata repository using SQLAlchemy.
- `flows/`, `reports/`: navigation graph, aggregate reports, and AI handoff docs.

## Validation

```powershell
pytest
ruff check src tests
```

Only analyze sites and accounts you are authorized to access.
"# tool_document_clone_web" 
