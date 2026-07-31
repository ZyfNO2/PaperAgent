"use strict";

(() => {
  window.PA = window.PA || {};
  PA.views = PA.views || {};
  const demoViews = {
    projects: PA.views.projects,
    literature: PA.views.literature,
    evidence: PA.views.evidence,
    artifacts: PA.views.artifacts,
    runs: PA.views.runs,
  };

  const h = (...args) => PA.h(...args);
  const project = () => {
    const id = PA.store.get("currentProject");
    return (PA.model.projects || []).find((item) => item.id === id) || PA.model.projects[0];
  };
  const state = (kind, text) => h("span", { class: `badge badge-${kind}`, text });

  function renderFailure(container, error, retry) {
    container.append(PA.errorState(`${error.code || "request_failed"}: ${error.message}`, retry));
  }

  PA.views.projects = {
    render(container) {
      if (PA.mode === "demo") return demoViews.projects.render(container);
      const projects = PA.model.projects || [];
      const name = h("input", { class: "input", placeholder: "项目名称", maxlength: "200" });
      const create = h("button", {
        class: "btn btn-primary", type: "button", text: "创建项目",
        onclick: async () => {
          const clean = name.value.trim();
          if (!clean) return;
          create.disabled = true;
          try {
            const result = await PA.api.createProject(clean);
            const item = result.project;
            PA.model.projects.push({
              id: item.project_id, name: item.name, status: "active", stage: "evidence",
              paperCount: 0, evidenceCount: 0, gateStatus: "REVISE",
            });
            PA.store.set("currentProject", item.project_id);
            PA.navigate();
          } catch (error) {
            PA.toast(error.message, "danger");
          } finally {
            create.disabled = false;
          }
        },
      });
      container.append(h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {},
          h("p", { class: "eyebrow", text: "PAPERCLAW WORKSPACES" }),
          h("h3", { text: "研究项目" })), h("div", { class: "row" }, name, create)),
        h("div", { class: "panel-body" },
          projects.length ? h("div", { class: "card-grid" }, projects.map((item) =>
            h("button", {
              class: "card", type: "button",
              onclick: () => { PA.store.set("currentProject", item.id); PA.navigate(); },
            }, h("h3", { text: item.name }),
            h("p", { class: "muted small", text: item.id }),
            h("div", { class: "row" }, state("info", `${item.paperCount || 0} papers`),
              state("warning", item.gateStatus || "REVISE")))))
            : PA.emptyState({ title: "暂无项目", text: "创建项目后即可导入论文。" }))));
    },
  };

  PA.views.literature = {
    render(container) {
      if (PA.mode === "demo") return demoViews.literature.render(container);
      const current = project();
      if (!current) {
        container.append(PA.emptyState({ title: "尚未选择项目", text: "请先创建项目。" }));
        return;
      }
      const source = h("input", {
        class: "input", placeholder: "PaperClaw 允许根目录内的 PDF 路径",
        "aria-label": "论文文件路径",
      });
      const importButton = h("button", {
        class: "btn btn-primary", type: "button", text: "导入论文",
        onclick: async () => {
          importButton.disabled = true;
          try {
            const result = await PA.api.importPaper(current.id, source.value.trim());
            await PA.api.parsePaper(current.id, result.paper.paper_id);
            await PA.api.buildIndex(current.id);
            result.paper.parse_status = "indexed";
            PA.model.papers.push(result.paper);
            PA.navigate();
          } catch (error) {
            PA.toast(error.message, "danger");
          } finally {
            importButton.disabled = false;
          }
        },
      });
      const papers = PA.model.papers || [];
      container.append(h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {},
          h("p", { class: "eyebrow", text: "CANONICAL PAPERS" }), h("h3", { text: current.name })),
          h("div", { class: "row" }, source, importButton)),
        h("div", { class: "panel-body" }, papers.length
          ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, ["Paper", "Version", "Metadata", "Status"].map((x) => h("th", { text: x })))),
            h("tbody", {}, papers.map((paper) => h("tr", {},
              h("td", {}, h("strong", { text: paper.title || paper.filename || paper.paper_id }), h("div", { class: "muted small", text: paper.paper_id })),
              h("td", { text: String((paper.current_version || {}).version_number || paper.version_number || "—") }),
              h("td", {}, state(paper.metadata_confirmed ? "success" : "warning", paper.metadata_confirmed ? "confirmed" : "candidate")),
              h("td", {}, state("info", paper.parse_status || paper.status || "imported")))))))
          : PA.emptyState({ title: "暂无论文", text: "导入后由 PaperClaw 版本化、解析和索引。" }))));
    },
  };

  PA.views.evidence = {
    render(container) {
      if (PA.mode === "demo") return demoViews.evidence.render(container);
      const current = project();
      if (!current) {
        container.append(PA.emptyState({ title: "尚未选择项目", text: "请先创建项目。" }));
        return;
      }
      const question = h("textarea", { class: "input", rows: "3", placeholder: "输入可核验的研究问题" });
      const output = h("div", { class: "stack" });
      const run = h("button", {
        class: "btn btn-primary", type: "button", text: "检索 Evidence",
        onclick: async () => {
          run.disabled = true;
          PA.clear(output).append(PA.loadingState("正在执行 Query Planner 与多通道检索…"));
          try {
            const result = await PA.api.queryEvidence(
              current.id, question.value.trim(), (PA.model.papers || []).map((p) => p.paper_id),
            );
            PA.model.lastEvidence = result;
            renderResult(output, result, current.id);
          } catch (error) {
            PA.clear(output);
            renderFailure(output, error, () => run.click());
          } finally {
            run.disabled = false;
          }
        },
      });
      container.append(h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "ACCEPTED-ONLY" }), h("h3", { text: "Evidence Ledger" }))),
        h("div", { class: "panel-body stack" }, question, h("div", { class: "row" }, run), output)));
      if (PA.model.lastEvidence) renderResult(output, PA.model.lastEvidence, current.id);
    },
  };

  function renderResult(output, result, projectId) {
    PA.clear(output);
    const entries = (result.ledger && result.ledger.entries) || [];
    const candidates = new Map((result.retrieval_candidates || []).map((item) => [item.evidence_id, item]));
    output.append(h("div", { class: "row" },
      state(result.sufficiency === "sufficient" ? "success" : "warning", result.sufficiency || "unknown"),
      state("info", result.stop_reason || "unknown"),
      h("span", { class: "muted small", text: `Trace: ${(result.trace_ids || []).join(", ")}` })));
    if (!entries.length) {
      output.append(PA.emptyState({ title: "Evidence 不足，系统已 abstain", text: "当前 Gate 为 REVISE；不会构造无证据 Claim。" }));
      return;
    }
    output.append(h("div", { class: "card-grid" }, entries.map((entry) => {
      const candidate = candidates.get(entry.evidence_id) || {};
      return h("button", {
        class: "card", type: "button",
        onclick: async () => {
          try {
            const resolved = await PA.api.resolveLocator(projectId, entry.locator);
            const body = h("div", { class: "stack" },
              h("pre", { class: "code-block", text: JSON.stringify(entry.locator, null, 2) }),
              h("p", { text: resolved.text || "This object has no extracted text." }));
            const asset = (resolved.assets || [])[0];
            if (asset && asset.sha256) {
              const blob = await PA.api.readAsset(projectId, entry.locator, asset.sha256);
              body.append(h("img", {
                src: URL.createObjectURL(blob),
                alt: `Resolved page/region asset for ${entry.evidence_id}`,
                style: "max-width:100%;height:auto;border-radius:8px",
              }));
            } else {
              body.append(h("p", { class: "muted small", text: "No page/region asset is attached to this canonical object." }));
            }
            PA.drawer({
              title: `Claim Locator · ${entry.evidence_id}`,
              subtitle: `${entry.locator.paper_id} / p.${entry.locator.page_number}`,
              body,
            });
          } catch (error) { PA.toast(error.message, "danger"); }
        },
      }, state(entry.status === "accepted" ? "success" : "warning", entry.status),
      h("h3", { text: candidate.text || entry.evidence_id }),
      h("p", { class: "muted small", text: `${entry.locator.object_type} · page ${entry.locator.page_number} · ${entry.locator.object_id}` }),
      h("p", { class: "muted small", text: `score ${candidate.score == null ? "—" : candidate.score}` }));
    })));
    const papers = PA.model.papers || [];
    if (papers.length >= 2 && result.ledger.accepted_ids.length) {
      const generate = h("button", {
        class: "btn btn-primary", type: "button", text: "生成八类 Evidence-bound Artifacts",
        onclick: async () => {
          generate.disabled = true;
          try {
            await PA.api.generateArtifacts(
              projectId,
              result.query_plan.original_question,
              papers[0].paper_id,
              papers.slice(1).map((paper) => paper.paper_id),
            );
            const refreshed = await PA.api.listArtifacts(projectId);
            PA.model.artifacts = refreshed.artifacts || [];
            PA.toast("Artifact 草稿已写入 PaperClaw append-only store", "success");
          } catch (error) {
            PA.toast(error.message, "danger");
          } finally {
            generate.disabled = false;
          }
        },
      });
      output.append(h("div", { class: "row" }, generate));
    }
  }

  PA.views.artifacts = {
    render(container) {
      if (PA.mode === "demo") return demoViews.artifacts.render(container);
      const current = project();
      const artifacts = PA.model.artifacts || [];
      if (!current || !artifacts.length) {
        container.append(PA.emptyState({ title: "暂无 Artifact", text: "运行 evidence-bound 方法任务后将在此显示八类草稿。" }));
        return;
      }
      container.append(h("div", { class: "card-grid" }, artifacts.map((artifact) =>
        h("button", {
          class: "card", type: "button",
          onclick: () => openArtifact(current.id, artifact.artifact_id),
        },
        state("info", artifact.artifact_type),
        h("h3", { text: artifact.title }),
        h("p", { class: "muted small", text: `revision ${artifact.latest_revision_number}` })),
      )));
    },
  };

  async function openArtifact(projectId, artifactId) {
    try {
      const detail = await PA.api.getArtifact(projectId, artifactId);
      const revisions = detail.revisions || [];
      const latest = revisions[revisions.length - 1] || {};
      const content = latest.content || {};
      PA.drawer({
        title: detail.artifact.title,
        subtitle: `${detail.artifact.artifact_type} · ${revisions.length} revisions`,
        body: h("div", { class: "stack" },
          state(content.state === "approved" ? "success" : "warning", content.state || "unknown"),
          h("p", { text: content.summary || "" }),
          h("pre", { class: "code-block", text: JSON.stringify(revisions, null, 2) })),
        actions: ["approved", "rejected", "revise"].map((decision) => ({
          label: decision === "approved" ? "Approve" : decision === "rejected" ? "Reject" : "Request Revision",
          kind: decision === "approved" ? "primary" : "secondary",
          onClick: () => {
            const note = window.prompt("请输入审阅说明（必填）");
            if (!note || !note.trim()) return true;
            PA.api.reviewArtifact(projectId, artifactId, decision, note.trim())
              .then(() => { PA.toast("已追加新的 Artifact revision", "success"); PA.navigate(); })
              .catch((error) => PA.toast(error.message, "danger"));
            return false;
          },
        })),
      });
    } catch (error) { PA.toast(error.message, "danger"); }
  }

  PA.views.runs = {
    render(container) {
      if (PA.mode === "demo") return demoViews.runs.render(container);
      const runs = PA.model.runs || [];
      container.append(runs.length
        ? h("pre", { class: "code-block", text: JSON.stringify(runs, null, 2) })
        : PA.emptyState({ title: "暂无运行记录", text: "任务状态通过 PaperAgent durable Task API 与 SSE 恢复。" }));
    },
  };
})();
