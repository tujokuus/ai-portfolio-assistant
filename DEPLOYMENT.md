# First deployment: frontend and backend together on Render

Status: prepared, not deployed or runtime-verified. Keep the GitHub Pages
portfolio separate initially and link it to this service. This configuration
does not yet serve a cross-origin frontend on GitHub Pages.

## Source bundle

`deployment_bundle/` is a local, gitignored snapshot containing the original CV,
five README files, and a relative-path `sources.json`. It contains personal CV
contact information and will be downloadable by visitors through source links.
Review it before making it public. A private repository does not make the
deployed source endpoints private.

The cloud needs these actual files; it cannot read your local Downloads folder.
After reviewing the bundle, explicitly add it to the repository used for Render
deployment. If that repository is public, this also publishes the files in Git
history. A separate private deployment repository is an alternative.

### Updating the source bundle

After editing the CV or a project's README, run these commands from the repository
root. If a file's location changed, first update its `path` in `sources.local.json`.

```powershell
.\.venv\Scripts\python.exe -m backend.update_sources --dry-run
.\.venv\Scripts\python.exe -m backend.update_sources
git diff --stat -- deployment_bundle
```

The command validates every listed document, then copies its original bytes and
writes `deployment_bundle/sources.json` with portable relative paths. It reports
added, updated, and unchanged files. It makes no API calls or Git operations.
PDF validation needs the existing `web` dependencies. Optional `--sources` and
`--output-dir` select another manifest and destination.

Unlisted files are reported and retained for manual review; the new manifest
excludes them from the assistant's sources. Remove obsolete public files from Git
yourself if appropriate (this does not erase Git history). An interrupted write
can leave a partly updated bundle: rerun successfully before committing it.

Review the changes, commit the bundle, and push to the branch used by Render.
Already tracked bundle files can be staged normally; a new file in the ignored
directory needs `git add -f deployment_bundle/<filename>`. With automatic deploys
enabled, the push triggers deployment; otherwise deploy the commit manually.
The running service reads a source snapshot at startup, so local edits alone do
not update the deployed assistant.

Do not include USAGE.md, evaluation answers, reports, API keys, or unrelated
repository contents in the source manifest.

## Local release checks (run manually)

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[web,dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.compare --provider openai --sources deployment_bundle/sources.json --dataset tests/evaluation_originals_en.json --suite all --validate-only
$env:SOURCES_MANIFEST = "deployment_bundle/sources.json"
.\.venv\Scripts\python.exe -m backend.web
```

The tests and validate-only command make no model calls. TestClient route tests
mock the assistant and skip real startup; the manual launch checks startup and
the source package. Test the browser at desktop and mobile widths, Enter and
Ctrl+Enter, source expansion, original PDF/README opening, errors and Clear chat.
Then run one or two real questions to check the shortened corpus (paid requests).
Use `Remove-Item Env:SOURCES_MANIFEST` to return to your local source list.

## Render setup

1. Review and commit the code and the intended public source bundle to the
   repository Render will clone. The ignored bundle is not included by a normal
   `git add .`; add it explicitly only after reviewing its contents.
2. In Render, create a Blueprint from that repository and `render.yaml`.
3. Supply OPENAI_API_KEY as a secret in Render, never in a file or Git history.
4. Deploy with CHAT_ENABLED=false initially. Check `/health`, the page, and
   original-source links. A healthy server does not verify API credit or access.
5. Render's RENDER_EXTERNAL_URL supplies the allowed HTTPS origin. Set
   PUBLIC_ORIGIN explicitly if using a custom domain (origin only, no path).
6. Configure the API project's billing controls and verify a small usage budget.
7. Change CHAT_ENABLED to true and restart/deploy. Send a real question and
   confirm its citation and provider usage. Then add the link to your portfolio.

The YAML uses one worker, free compute, `pip install -e ".[web]"`, and Uvicorn on
Render's PORT. No local embeddings, Chroma, Ollama, database, or Node build is
required. The dependency ranges are not a lockfile: record the installed
versions after a successful deployment before claiming a reproducible release.

Official references: [FastAPI on Render](https://render.com/docs/deploy-fastapi),
[Blueprint specification](https://render.com/docs/blueprint-spec), and
[free-tier limitations](https://render.com/docs/free).

## Controls and their limits

- CHAT_ENABLED=false blocks generation. It does not hide documents or the page.
- CHAT_HOURLY_LIMIT=20 and CHAT_DAILY_LIMIT=100 count attempted generations across
  **all visitors** and remain the service-wide ceiling, with rolling windows.
  CHAT_IP_HOURLY_LIMIT=20 and CHAT_IP_DAILY_LIMIT=40 are separate per-IP limits.
  Failed provider calls also consume a slot because they may be billed.
  Busy/invalid/disabled requests do not.
- Render's CF-Connecting-IP header is preferred; the first address in
  X-Forwarded-For is the fallback, followed by the direct client address. IP
  limits are best-effort and can be evaded by changing networks or addresses.
- One model call runs at a time. Requests while busy receive 429.
- Quotas live in memory, reset on restart, and are not shared across workers or
  instances. Keep one worker. They are not a durable spend cap or a verified
  identity limit. Multiple visitors can share one IP address.
- CORS is not enabled and unexpected browser Origins are rejected. Origin checks
  do not authenticate callers and cannot prevent direct automated requests.
- API error details are not exposed to visitors. The app does not store chat
  messages; requests still send questions and evidence to OpenAI. Hosting/provider
  logs are separate. Uvicorn access logging is disabled in the start command.
- Render's free instance sleeps after inactivity; a cold first visit can be slow.

Before a wider public launch, consider bot protection and a persistent shared
quota store if actual abuse or multiple instances justify them. Keep a small
provider budget and monitor usage. For rollback, disable chat and redeploy the
previous known-good commit, including its source snapshot.

## Remaining release gates

- Run the new tests and manual browser checks; they have not been run by the agent.
- Approve source contents for public access and deliver the bundle to Render.
- Confirm the CV's graduation information and other time-sensitive facts.
- Verify the Render configuration, startup, original files and one live answer.
- Review the latest answer results after shortening the corpus.

Visitor analytics, conversation memory, streaming, and source-code retrieval are
optional follow-ups, not prerequisites for the first small demo.
