---
name: Drive steps collapsible
overview: Turn the Drive tab's ingest guidance into a clear, collapsible "what to do and why" steps panel placed first (open initially, remembered when collapsed), keeping the existing default-folder paragraph directly after it.
todos:
  - id: storage-key
    content: Add STEPS_OPEN storage key in lib/driveFolder.ts and stepsOpen state + localStorage read on mount in DriveTab
    status: completed
  - id: collapsible-steps
    content: Convert the lines 289-333 steps box into a <details> panel (summary 'How to ingest your files') wired to stepsOpen/onToggle
    status: completed
  - id: reword-steps
    content: Reword the <ol> into choose files / ingest files / why-it-helps-queries steps, keeping the conditional 'open in Drive' link
    status: completed
  - id: verify
    content: Verify default-open, collapse persistence across reload, ordering, and no-default-folder fallback
    status: completed
isProject: false
---

## Drive tab: collapsible step-by-step guidance

Make the existing always-visible "How ingesting works" box in [`frontend/src/components/drive/DriveTab.tsx`](frontend/src/components/drive/DriveTab.tsx) (lines 289–333) into a collapsible `<details>` panel that clearly communicates the user flow and its payoff, placed first, with the "Our default folder…" paragraph right after it (unchanged copy).

### 1. Convert the steps box to a collapsible panel

Replace the `<div>…</div>` block at lines 289–333 with a `<details>` element:

- Summary text: `How to ingest your files` (uses existing `detailsSummaryStyle` / `detailsBodyStyle` from lines 47–59, so it matches the other collapsibles).
- Keep the framed look (light background, border) by wrapping in the same panel styling currently on the box.
- Default open/closed driven by remembered state (see step 3).

### 2. Tighten the steps to emphasize what + why

Reword the `<ol>` so each step states the action and the steps build toward the payoff (your framing: choose files, ingest them, then get useful info in queries):

1. Choose your files: open the Drive folder (keep the conditional `open in Drive` link using `driveFolderUrl(effectiveFolderId)`) and drop your completed report(s) in, then click **List files**.
2. Ingest your files: select the report(s) you want and click **Ingest**.
3. Why it matters: once indexed, those files are searched automatically whenever you ask a question in the Chat tab, so the assistant can pull real answers from them.

### 3. Remember the collapse state (open first time, stay collapsed once dismissed)

- Add a storage key (e.g. `verbiage.drive.stepsOpen`) — define it next to `DRIVE_FOLDER_STORAGE_KEY` in [`frontend/src/lib/driveFolder.ts`](frontend/src/lib/driveFolder.ts) for consistency.
- Add local state `const [stepsOpen, setStepsOpen] = useState(true)`; on mount, read the stored value (default `true` if unset).
- On the `<details>`, set `open={stepsOpen}` and `onToggle={e => { const o = (e.target as HTMLDetailsElement).open; setStepsOpen(o); localStorage.setItem(STEPS_KEY, o ? '1' : '0') }}` — mirrors the existing `authHelpOpen` pattern at lines 521–525.

### 4. Ordering and the default-folder paragraph

Keep the current order, just with the steps now collapsible:

1. `h2` "Google Drive" + one-line intro (lines 283–287) — unchanged.
2. Collapsible **How to ingest your files** steps panel (new).
3. **"Our default folder for ingesting completed reports into the repository is … the best procedure is to copy your file into that folder first."** paragraph (lines 335–348) — unchanged.
4. Location banner, actions, messages, file list, and the existing "Use a different folder" / "Connection or setup problems?" collapsibles — unchanged.

### Verification

- Default load: steps panel is expanded, shows the 3-step flow, default-folder paragraph below it.
- Collapse the steps, reload the page → it stays collapsed.
- `open in Drive` inline link still appears in step 1 only when a folder is resolved.
- No-default-folder fallback (amber note) still renders correctly below the steps.