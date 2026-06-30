# README Review Notes

---

**Post-intro block** — Lines after the comparison table (glossary bullets → banking sentinel bullets → offline/online eval paragraphs)

- This block has grown into a mess: glossary, project feature list, and concept explanations are mixed together with overlapping content. Refactor into a coherent structure.

---

**L621** — CI/CD: How to exploit evaluations in Langfuse (pending investigation)

- `.doc/evals-flow.png` shows the full loop: Trace → Monitor → Build datasets → Experiment → Evaluate → Deploy.
- Investigate: what are the concrete day-to-day actions once scores land in Langfuse? How do you compare across runs, set up alerts, act on regressions? How does this compare to Datadog (monitors, dashboards)?
- Decide: include the image, recreate as mermaid, or describe in prose.