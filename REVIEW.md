# README Review Notes

All `--review:` comments extracted from `README.md`. Line numbers reference the original file before extraction.

---

~~**L12–13** — Introduction: Strands Agents background~~ ✓

---

~~**L17** — Introduction: AI vs deterministic quality assurance~~ ✓

---

~~**L33–34** — Comparison table: Feature descriptions and annotation queues~~ ✓

---

~~**L46** — Feature list: Concept structure~~ ✓

---

~~**L127** — Step 1: Real application guidance~~ ✓

---

~~**L143–144** — Step 2: OpenTelemetry background~~ ✓

---

~~**L182** — Offline vs Online: Section placement~~ ✓

---

~~**L230–231** — Step 3: Strands Evals context~~ ✓

---

~~**L246** — Step 3: Embedded vs API mode explanation~~ ✓

---

~~**L262** — Step 4: Experiment concept definition~~ ✓

---

~~**L618** — CI/CD: External evaluations / Langfuse equivalent~~ ✓ (Step 6 renamed + restructured around this concept)

---

~~**L620** — CI/CD: Real-world CI/CD scenario~~ ✓

---

**L621** — CI/CD: How to exploit evaluations in Langfuse (pending investigation)

- `.doc/evals-flow.png` shows the full loop: Trace → Monitor → Build datasets → Experiment → Evaluate → Deploy.
- Investigate: what are the concrete day-to-day actions once scores land in Langfuse? How do you compare across runs, set up alerts, act on regressions? How does this compare to Datadog (monitors, dashboards)?
- Decide: include the image, recreate as mermaid, or describe in prose.