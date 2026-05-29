---
name: drive ingest flow intro
overview: Add a short, first-time-friendly "how it works" flow guide to the top of the Drive ingest tab so new users understand the place-in-Drive → select → ingest → query path.
todos: []
isProject: false
---

# Drive Ingest Flow Intro

Add a concise step-by-step explainer near the top of the ingest UI so a brand-new user understands the whole flow before doing anything.

## Where
All changes are in [frontend/src/components/drive/DriveTab.tsx](frontend/src/components/drive/DriveTab.tsx). This is the ingest frontend (the "Google Drive" tab).

## Change
Replace the single-line intro at lines 285-287:

```285:287:frontend/src/components/drive/DriveTab.tsx
      <p style={{ fontSize: 13, color: '#57606a', lineHeight: 1.6, marginBottom: 14 }}>
        List and ingest completed reports from Google Drive into the document repository.
      </p>
```

with a small numbered "How ingesting works" panel that walks through the flow:

1. Open the Drive folder and drop your completed report(s) in (link to the team folder).
2. Click **List files** to see what's there.
3. Select the report(s) and click **Ingest**.
4. Once indexed, the report is searched automatically whenever you ask the assistant a question in the Chat tab.

Notes:
- Keep the existing team-folder paragraph (lines 289-315) since it already links to the default ingest folder; the new panel references the same flow without duplicating that link logic.
- Reuse the existing inline-style approach (e.g. a light `#f6f8fa` / `#d0d7de` panel like the folder box at lines 317-337) and the existing button label words ("List files", "Ingest") so the steps match the on-screen buttons.
- Pure copy/markup addition: no new state, props, or API calls.

## Out of scope
- No dismiss/localStorage logic (always-visible, compact). Can add later if desired.