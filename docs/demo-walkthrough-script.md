# TrueAI — Demo Walkthrough Script

**For:** RealPage technical round (via Carter Smith, Motion Recruitment)
**Target length:** 5 minutes (~750 spoken words)
**Structure:** problem → architecture → the decision and what it cost → how I know it works → what changes at their scale

Stage directions are in **[brackets]**. Everything else is spoken.

Stay signed out for the whole recording. The guest demo opens Search with no account, so nothing in the header is an email. Search carries the refusal. Report Writer carries one sample claim that clears the same gate and comes back as a draft. Do not generate that draft on camera — warm it before you record. See the notes.

---

## 0:00 — Open

**[Screen: the demo URL, already on Search, signed out. Header reads "Live demo on sample inspection reports." Don't click Sign in or Sign up. Don't linger — 3 seconds.]**

Hi — I'm Rebecca Clarke. This is TrueAI, a retrieval system I built and deployed solo at True Reports.

**[Stay on Search. If a sign-in form is in the header, leave it alone and keep it out of the spoken beat.]**

The company writes forensic engineering reports — storm damage, roof failures, that kind of thing. Those reports get used in insurance claims and sometimes in litigation. So the constraint that shaped everything here is: a confident wrong answer is worse than no answer at all. Nobody is helped by a system that guesses well.

---

## 0:35 — Search, grounded

**[Type a question about shingle damage. Submit. Let the answer render.]**

This is search over the report library. The engineers use it to find what they've already written about a damage type, so they're not rewriting the same analysis from scratch.

**[Point at the sources on the result.]**

Every answer carries its sources. That's not decoration — generation never sees the full corpus, only the retrieved passages plus the question. So if an answer exists, there's a specific retrieved passage behind it, and you can go read that passage.

**[Click "Save to collection" on a result. Gesture at the right-hand panel.]**

Anything worth keeping goes to a collection. That's a bookmark. Each search stays independent — I didn't want conversational state quietly carrying context between unrelated questions. The report itself is a separate claim. I'll open that in a minute.

**[Toggle on "Show retrieval retries (rewritten query)." Run a deliberately vague query.]**

This toggle exposes something I usually keep hidden: when the first retrieval pass comes back weak, the system rewrites the query and retries — and this shows you the rewrite. Retrieval is hybrid: semantic search over pgvector alongside keyword matching, fused with reciprocal rank fusion so each method votes without a hand-tuned weight.

---

## 1:50 — The decision that matters

**[Ask something the corpus genuinely can't answer — off-domain. Let it refuse.]**

This is the part I'd most want to talk about.

It just refused. There's a relevance gate between retrieval and generation — a similarity check on what came back. If retrieval clears the bar, the system generates. If it doesn't, it declines and says so, instead of writing something plausible out of thin air.

The important detail is *where* that decision lives. The gate is a hard stop in the pipeline. **The language model never makes that call.** I didn't want the component most capable of producing a confident hallucination to also be the component deciding whether it has enough evidence to proceed.

---

## 2:35 — Report Writer, and what the DAG cost

**[Switch to Report Writer. One sample claim is already open. Stay on Starting data. New claim, Import, and Delete are hidden — don't look for them.]**

Search answers one question. This drafts the report.

**[Point at the address, the storm date, and the field notes.]**

This is sample data. Fictional address, and notes written to match a report already in the library: missing and creased windward shingles, an opening, staining on the garage ceiling. Weather is already on the form. This screen is not calling a live weather or maps service.

**[Photos. Two seconds. Don't upload.]**

The photos are already captioned. Generate reads those captions. The image step is loading that cache.

**[Report. A draft from your warm-up should already be here. Scroll Roof Observations, then the retrieved-sources list.]**

Same hybrid retrieval as search, then the same relevance gate. This claim is an engineering report, which is how the library is titled, so retrieval cleared the bar and it wrote the sections: overview, findings, roof, interior, exterior, recommendations. If it had not cleared, this screen would say refused and there would be no sections. Generation only saw the notes, the captions, and these passages.

The run is a LangGraph DAG with a Postgres checkpointer and a typed state object. The sequence is fixed: analyze images, normalize inputs, hybrid retrieval, relevance gate, generate sections, validate, persist. It is acyclic and it runs once.

That was a deliberate trade, and I'll name what I gave up. An open-ended agent — ReAct-style, choosing its own tools each step — would handle novel report shapes far better than this does. Mine can't improvise. When a document doesn't fit the expected structure, my graph handles it worse than a reasoning loop would.

I took that trade because every run produces the same sequence of steps, each one logged, and the grounding gate sits at a fixed point the pipeline can't route around. In a domain where the output has to be defensible afterward, I wanted predictable and auditable more than I wanted adaptive.

I'd make that trade differently somewhere else. Lower stakes, or a workflow where the shape genuinely varies run to run, and the reasoning loop wins.

---

## 3:25 — How I know it works

**[Screen: editor or terminal with the eval harness. If you'd rather not show code, stay on the app and just talk — this section carries on narration alone.]**

The thing I'd least want to hand-wave is how I know any of this is correct.

There's an offline evaluation harness that runs the real pipeline against a frozen corpus and a fixed set of gold questions with known-good answers, in a throwaway database that gets torn down after. It runs after any retrieval or prompt change.

For grounding, it splits each generated answer into sentence-level claims and checks whether each claim is actually entailed by the passages that were retrieved for it — using a local natural-language-inference model as the judge rather than another LLM, so it's deterministic, free, and fast enough to run constantly.

Two things about it I'd defend:

It separates a **retrieval miss** from a **generation failure**. If the right passage never came back, that's a retriever problem, and it gets reported as one — otherwise you spend a day tuning a prompt to fix a search bug.

And **refusals are detected separately and never counted as hallucinations.** A system that correctly declines is behaving well. If your eval punishes that, you've built something that will quietly train itself to guess.

That harness caught retrieval failures that reading the output would never have surfaced — answers that were fluent, plausible, and not supported by what came back.

---

## 4:25 — What changes at your scale

**[Back to the app, or just talk to camera.]**

Two honest limits.

This serves one firm's corpus. Multi-tenant isolation — guaranteeing retrieval can never cross a boundary — is a different and harder problem than anything I've had to solve here, and I'd want that enforced at the data layer, not in application logic.

And the eval set is a fixed gold set I built with a subject-matter expert. That doesn't scale on its own. What I'd want next is corrections flowing back in — when a reviewer fixes an output, that becomes a new eval case, so coverage grows from real use instead of from me writing more questions.

The thing I'd bring is the instinct underneath all of this: decide what "correct" means and how you'll measure it *before* shipping, and make refusal a first-class outcome rather than a failure. That's most of what separates a demo from something people can rely on.

Happy to go deeper on any of it. Thanks for watching.

**[End.]**

---

# Notes — read before recording

## Accuracy guardrails

**Don't demo `1.3_retrieval_eval.py`.** It's an unfinished practice exercise in the project folder — the functions are still `pass` with TODOs. The real harness is in the True Reports repo under `tests/eval/`. If you screen-share code for the eval section, share that. Easiest safe option: don't share code at all there — the section is written to carry on narration alone.

**Eval numbers stay out of the recording.** The script deliberately says *"caught retrieval failures that reading the output would never have surfaced"* instead of citing faithfulness 0.875 → 1.0 or gate 2 → 0. A recording is forwardable and you can't answer a follow-up inside it — same reasoning as the C4 email, and the same failure mode that retired the 80% claim.

> **If you walk back through the eval code before recording,** you can add one line after "answers that were fluent, plausible, and not supported by what came back": *"On the frozen gold set, tightening a paraphrase-biased prompt took faithfulness from 0.875 to 1.0 and took gate failures from two to zero."* Only if you can explain cold what faithfulness scores and why each number moved. Otherwise leave it out — the mechanism sentence is doing the work already.

**Never say "multi-agent."** The script says orchestration, DAG, and graph. True Reports is an 8-node LangGraph DAG. If they ask directly, the honest answer is the one already in the script: it's a deterministic graph, and that was a choice.

**Stay signed out.** A session prints your email next to Sign out. The guest header does not. The subtitle already says this is a live demo on sample inspection reports, which is the anonymized-data line without you having to sign in to reach the app.

**Say the data is sample** when any address or claim detail is visible. The Report Writer beat already does this for 100 Harbor Example Road, Sampletown. One clause is enough on Search too, if a real-looking address renders. The library is the synthetic corpus, so a citation title should already be fictional — glance at the first result in the warm-up and confirm before you record.

**Don't say "deployed to AWS"** anywhere near this demo. It runs on Render.

**Collections are bookmarks.** They do not become the draft. The draft is the sample claim: field notes, cached photo captions, and similar engineering reports retrieved at generate time.

**Don't merge the two validators.** The graph's `validate_draft` step is a lightweight model check inside the run. The deterministic natural-language-inference judge is the offline harness in the 3:25 section. If a step name is on screen, `validate_draft` is the in-run check.

**Stay on Engineering.** The sample is an engineering report because that is how the library titles are written. Switching the type to Roof Report would miss the gate. Don't change it on camera.

## Recording logistics

- **Record signed out, in a private window.** Open the demo URL. Search should load with no sign-in. Sign out first if a previous session is still in that browser — the header will show the account email until you do. Use a private window so the email field in the header stays empty; browser autofill will otherwise type an address into it. Don't click that field, Sign in, or Sign up. Don't open Preferences.
- **Warm the app first.** Render free tier cold-starts — load the site and run one query a few minutes before you record, or the opening will be thirty seconds of spinner. Do that warm-up in the same signed-out window you'll record in.
- **Warm the report draft in that same pass.** Generate once, leave the finished draft on the Report tab, and do not press Generate during the take. Live generation sits on "Generating draft… (step: …)" long enough to blow a five-minute recording.
- **Two separate caps.** Search is 10 queries per hour per visitor. Report Writer generate is 5 per hour per IP. Rehearse narration without submitting. The warm-up query and the warm-up generate each spend one of those budgets.
- **One shared sample.** Another visitor can generate the same claim and replace the draft you warmed. Record when the demo is quiet, and glance at Roof Observations before you start the take.
- **Don't touch guest-blocked controls.** New claim, Import, and Delete are hidden. Upload, weather refresh, maps, aerials, and the property appraiser return errors for a guest. Stay on Starting data, Photos, and Report.
- **Pick your three search queries in advance and test them once:** one good shingle-damage question, one vague one for the retry toggle, one genuinely off-domain to trigger the refusal. The refusal is the strongest moment in the whole thing — make sure your chosen query actually triggers it before you hit record.
- **Optional, only if a rehearsal finishes in under a minute:** generate live and let the progress line show the step names while you say the sequence. If the rehearsal is slower than that, use the finished draft.
- **Record in one take if you can.** Small stumbles read as human; heavy editing reads as a sales asset.
- **5:00 is a ceiling, not a target.** 4:30 is better than 5:30.

## What's doing the work

- **The refusal is the centerpiece**, and it's sequenced at the 2-minute mark where attention is still high. For a company whose output has to be defensible, "it declines rather than guesses" is the single most relevant thing you can show.
- **Report Writer is the same gate, clearing.** Search shows a decline. The sample claim shows what happens when retrieval passes: sections, and the passages they came from. The pair is the point. A second refusal inside Report Writer spends a generate and throws away the draft you warmed.
- **You name what the architecture cost you.** "My graph handles it worse than a reasoning loop would" is the line that separates you from candidates reciting framework names. It also pre-empts the obvious challenge — nobody can spring "but a real agent would be better at that" on you if you said it first.
- **The eval section is your differentiator and it's the longest.** The retrieval-miss-vs-generation-failure distinction and refusals-aren't-hallucinations are both things most candidates have never had to think about. This req names model evals as a core responsibility.
- **The closing limits are deliberate.** Multi-tenant isolation and eval-set scale are the two real gaps between what you built and what they run — naming them yourself converts them from weaknesses they discover into judgment you demonstrated.
- **Nothing here needs the DOJ settlement.** Every word about auditability, provenance and defensible output lands for anyone at RealPage who owns that problem, without you having raised their open legal matter.
