# README Review Notes

---

**Intro** — Opening description

- Consider adding the Langfuse diagram here (the mermaid flowchart is further down — move or duplicate it?)
- The intro currently lists features by enumeration ("tracing, evaluations, prompt management, human feedback") — rewrite as a higher-level value statement instead.

---

**Comparison table footer** — `> Tracing means…` glossary row

- Replace "User Feedback" with "External Evaluations" in the glossary and table header — as decided when implementing Step 6.

---

**Step 2: Langfuse Tracing** — `The challenge:` paragraph

- The paragraph ends with "you get `undefined` in the annotation queue" — annotation queues haven't been introduced at this point in the doc. Rephrase the consequence without referencing annotation queues.

---

**Step 3: Strands Native Evaluations** — `Use embedded when…` paragraph

- Does the final "Use embedded / Use API" paragraph add value, or should those recommendations be folded into the two bullet points above it (Embedded / API)?

---

**Step 4: Langfuse Experiments** — `An experiment (called…)` sentence

- The opening sentence lists how other providers name this concept — move that context to the comparison table (add a column or footnote) and keep this section focused on Langfuse.

---

**Step 6: External Evaluations** — Opening paragraph

- "This is the equivalent of Datadog's external evaluations — though other providers may use different names (to investigate)" — resolve the "(to investigate)" and move the cross-provider naming context to the comparison table with links to each provider's docs. Keep this section focused on Langfuse.

---

**L621** — CI/CD: How to exploit evaluations in Langfuse (pending investigation)

- `.doc/evals-flow.png` shows the full loop: Trace → Monitor → Build datasets → Experiment → Evaluate → Deploy.
- Investigate: what are the concrete day-to-day actions once scores land in Langfuse? How do you compare across runs, set up alerts, act on regressions? How does this compare to Datadog (monitors, dashboards)?
- Decide: include the image, recreate as mermaid, or describe in prose.