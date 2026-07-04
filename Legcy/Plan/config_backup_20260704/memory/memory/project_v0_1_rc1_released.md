---
name: v0-1-rc1-released
description: Session 19-20 completed — PaperAgent v0.1.0-rc1 is the Release Candidate; Session 21+ must be re-evaluated
metadata: 
  node_type: memory
  type: project
  originSessionId: 2f30fc2b-4231-4707-896d-4f7966b3e7c4
---

PaperAgent v0.1.0-rc1 reached on 2026-06-20, after Sessions 18-20 finished.

**What's in RC**:
- 20 Sessions of feature work (evidence workbench, multi-source retrieval, trace persistence, skill registry, material cards, demo baseline, error observability, opening report templates)
- 6 maintenance docs: VERSION, CHANGELOG, Roadmap, Known_Limitations, Release_Checklist, Architecture_Overview
- 258 backend tests + 85+ Playwright e2e all green
- S17 demo baseline regression still passes

**Why**: SOP §13 explicitly says Session 21+ must re-evaluate direction. Past RC, any new feature (DOCX export, RAG, OCR, deployment, user system) is OUT of scope until independently assessed.

**How to apply**: Do NOT autonomously design Session 21+ without explicit user approval. The user already told me "不要做没有SOP的了" — only execute sessions that have an SOP file under `Plan/PaperAgent_Session*.md`. After S20 the maintenance mode is correct — stop here unless user gives new SOP or direction.

Related: [[feedback_dont_design_without_sop]]