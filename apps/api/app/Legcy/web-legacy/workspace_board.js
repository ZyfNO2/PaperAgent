// Session 25: Workspace Board (双栏工作台 MVP).
//
// 左栏 SelectedResource（用户选中），右栏 CandidateResource（系统候选）。
// 用户可加入左栏、移除、标核心、标复核。
// Selected != Evidence：加入左栏不等于进入证据链。

(function (global) {
  "use strict";

  // ---------- 内部状态 ---------- //

  var _selectedResources = []; // [{ selectedId, candidateId, kind, title, url, source, isCore, needsReview, ... }]
  var _coverageCache = null;

  // ---------- helpers ---------- //

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function kindIcon(kind) {
    var icons = { paper: "📄", dataset: "📊", repo: "💻", thesis_template: "📐", benchmark: "🏆" };
    return icons[kind] || "📎";
  }

  // ---------- 覆盖度计算 ---------- //

  function computeCoverage() {
    var counts = { paper: 0, dataset: 0, repo: 0, thesis_template: 0, benchmark: 0 };
    var hasUnverified = false;
    var needsReview = false;
    _selectedResources.forEach(function (s) {
      counts[s.kind] = (counts[s.kind] || 0) + 1;
      if (s.verificationStatus === "unchecked" || s.verificationStatus === "failed") {
        hasUnverified = true;
      }
      if (s.needsReview) needsReview = true;
    });
    _coverageCache = {
      selectedPaperCount: counts.paper,
      selectedDatasetCount: counts.dataset,
      selectedRepoCount: counts.repo,
      selectedTemplateCount: counts.thesis_template,
      selectedBenchmarkCount: counts.benchmark,
      hasDataset: counts.dataset > 0,
      hasBaseline: counts.repo > 0 || counts.benchmark > 0,
      hasUrlUnverified: hasUnverified,
      hasNeedsReview: needsReview,
      totalSelected: _selectedResources.length,
    };
    return _coverageCache;
  }

  // ---------- CRUD 操作 ---------- //

  function addToSelected(candidateCard) {
    // 幂等：同 candidateId 不重复添加
    var existing = _selectedResources.find(function (s) { return s.candidateId === candidateCard.id; });
    if (existing) return existing.selectedId;

    var id = "sel_" + String(_selectedResources.length + 1).padStart(3, "0");
    var item = {
      selectedId: id,
      candidateId: candidateCard.id,
      kind: candidateCard.props && candidateCard.props.kind || "paper",
      title: candidateCard.props && candidateCard.props.title || "Unknown",
      url: candidateCard.props && candidateCard.props.url || "",
      source: candidateCard.props && candidateCard.props.source || "unknown",
      isCore: false,
      needsReview: false,
      verificationStatus: "unchecked",
      evidenceStatus: "not_promoted",
      addedAt: new Date().toISOString(),
    };
    _selectedResources.push(item);
    _coverageCache = null;
    return id;
  }

  function removeFromSelected(candidateId) {
    var before = _selectedResources.length;
    _selectedResources = _selectedResources.filter(function (s) { return s.candidateId !== candidateId; });
    _coverageCache = null;
    return _selectedResources.length < before;
  }

  function markCore(candidateId, core) {
    var sel = _selectedResources.find(function (s) { return s.candidateId === candidateId; });
    if (!sel) return false;
    sel.isCore = core !== false;
    return true;
  }

  function markForReview(candidateId, needs) {
    var sel = _selectedResources.find(function (s) { return s.candidateId === candidateId; });
    if (!sel) return false;
    sel.needsReview = needs !== false;
    _coverageCache = null;
    return true;
  }

  // ---------- 渲染：左栏 Selected ---------- //

  function renderSelectedColumn() {
    if (!_selectedResources.length) {
      return '<div class="ws-col ws-col--selected">' +
        '<h3 class="ws-col__title">📌 已选资料（左栏）</h3>' +
        '<div class="ws-empty">尚未选中任何资料</div>' +
        '</div>';
    }
    var items = _selectedResources.map(function (s) {
      var coreTag = s.isCore ? '<span class="pa-tag pa-tag--core">⭐ 核心</span>' : '';
      var reviewTag = s.needsReview ? '<span class="pa-tag pa-tag--review">🔍 待复核</span>' : '';
      var statusTag = s.verificationStatus === "url_verified" ? '<span class="pa-tag pa-tag--ok">✅ 已验证</span>' :
        s.verificationStatus === "failed" ? '<span class="pa-tag pa-tag--fail">❌ 验证失败</span>' :
        '<span class="pa-tag pa-tag--unchecked">⏳ 未验证</span>';
      return '<div class="ws-item ws-item--selected" data-candidate-id="' + esc(s.candidateId) + '">' +
        '<div class="ws-item__header">' +
          '<span class="ws-item__icon">' + kindIcon(s.kind) + '</span>' +
          '<span class="ws-item__title">' + esc(s.title) + '</span>' +
        '</div>' +
        '<div class="ws-item__tags">' + coreTag + reviewTag + statusTag + '</div>' +
        '<div class="ws-item__actions">' +
          '<button class="cta-mini" data-ws-action="remove_from_selected" data-candidate-id="' + esc(s.candidateId) + '" type="button">➖ 移除</button>' +
          '<button class="cta-mini" data-ws-action="mark_core" data-candidate-id="' + esc(s.candidateId) + '" type="button">' + (s.isCore ? '⭐ 取消核心' : '☆ 设为核心') + '</button>' +
          '<button class="cta-mini" data-ws-action="mark_needs_review" data-candidate-id="' + esc(s.candidateId) + '" type="button">' + (s.needsReview ? '🔍 取消复核' : '🔍 需复核') + '</button>' +
        '</div>' +
        '</div>';
    }).join("");
    return '<div class="ws-col ws-col--selected">' +
      '<h3 class="ws-col__title">📌 已选资料（左栏）<span class="ws-count">' + _selectedResources.length + '</span></h3>' +
      items +
      '</div>';
  }

  // ---------- 渲染：右栏 Candidates ---------- //

  function renderCandidateColumn(runState) {
    var candidates = [];
    if (runState && runState.steps && runState.steps.candidates) {
      var candStep = runState.steps.candidates;
      (candStep.blocks || []).forEach(function (cardId) {
        var card = runState.cards[cardId];
        if (card && (card.type === "RetrievalCandidateCard" || card.component === "RetrievalCandidateCard")) {
          candidates.push(card);
        }
      });
    }

    if (!candidates.length) {
      return '<div class="ws-col ws-col--candidates">' +
        '<h3 class="ws-col__title">📚 候选资料（右栏）</h3>' +
        '<div class="ws-empty">暂无候选资源</div>' +
        '</div>';
    }

    var items = candidates.map(function (card) {
      var p = card.props || {};
      var kws = (p.matched_keywords || []).map(function (kw) {
        return '<span class="pa-tag pa-tag--keyword">' + esc(kw) + '</span>';
      }).join("");
      var isSelected = _selectedResources.some(function (s) { return s.candidateId === card.id; });
      return '<div class="ws-item ws-item--candidate' + (isSelected ? ' ws-item--already-selected' : '') + '" data-card-id="' + esc(card.id) + '">' +
        '<div class="ws-item__header">' +
          '<span class="ws-item__icon">' + kindIcon(p.kind) + '</span>' +
          '<span class="ws-item__title">' + esc(p.title) + '</span>' +
        '</div>' +
        (kws ? '<div class="ws-item__tags">' + kws + '</div>' : '') +
        '<div class="ws-item__actions">' +
          (isSelected
            ? '<span class="pa-tag pa-tag--ok">✅ 已加入左栏</span>'
            : '<button class="cta-mini" data-ws-action="add_to_selected" data-card-id="' + esc(card.id) + '" type="button">➕ 加入左栏</button>'
          ) +
        '</div>' +
        '</div>';
    }).join("");

    return '<div class="ws-col ws-col--candidates">' +
      '<h3 class="ws-col__title">📚 候选资料（右栏）<span class="ws-count">' + candidates.length + '</span></h3>' +
      items +
      '</div>';
  }

  // ---------- 渲染：覆盖度摘要 ---------- //

  function renderCoverageSummary() {
    var cov = computeCoverage();
    var items = [
      { label: "已选论文", value: cov.selectedPaperCount, icon: "📄" },
      { label: "已选数据集", value: cov.selectedDatasetCount, icon: "📊" },
      { label: "已选工程", value: cov.selectedRepoCount, icon: "💻" },
      { label: "已选模板", value: cov.selectedTemplateCount, icon: "📐" },
      { label: "已选 Benchmark", value: cov.selectedBenchmarkCount, icon: "🏆" },
    ];
    var summary = items.map(function (it) {
      return '<span class="ws-cov-item">' + it.icon + ' ' + it.label + ': <strong>' + it.value + '</strong></span>';
    }).join("");

    var flags = "";
    if (!cov.hasDataset) flags += '<span class="ws-flag ws-flag--warn">⚠️ 无数据集</span>';
    if (!cov.hasBaseline) flags += '<span class="ws-flag ws-flag--warn">⚠️ 无 baseline/repo</span>';
    if (cov.hasUrlUnverified) flags += '<span class="ws-flag ws-flag--info">🔗 存在未验证 URL</span>';
    if (cov.hasNeedsReview) flags += '<span class="ws-flag ws-flag--info">🔍 存在需复核资料</span>';

    return '<div class="ws-coverage">' +
      '<h4 class="ws-coverage__title">📊 覆盖度摘要</h4>' +
      '<div class="ws-coverage__items">' + summary + '</div>' +
      (flags ? '<div class="ws-coverage__flags">' + flags + '</div>' : '') +
      '</div>';
  }

  // ---------- 渲染：完整工作台 ---------- //

  function renderWorkspace(runState) {
    return '<div class="workspace-board" id="workspace-board">' +
      '<div class="workspace-board__header">' +
        '<h2>🗂️ 资料工作台</h2>' +
        '<span class="workspace-board__note">左栏：已选资料 · 右栏：系统候选</span>' +
      '</div>' +
      '<div class="workspace-board__cols">' +
        renderSelectedColumn() +
        renderCandidateColumn(runState) +
      '</div>' +
      renderCoverageSummary() +
      '</div>';
  }

  // ---------- 事件绑定 ---------- //

  function handleAction(action, candidateId, runState) {
    var result = { ok: false, action: action };
    switch (action) {
      case "add_to_selected": {
        var card = runState && runState.cards && runState.cards[candidateId];
        if (card) {
          var sid = addToSelected(card);
          result = { ok: true, action: "add_to_selected", selectedId: sid };
          // 记入 eventBuffer
          if (runState && runState.eventBuffer) {
            runState.eventBuffer.push({
              event_type: "workspace_action",
              step_key: "workspace",
              payload: { action: "add_to_selected", candidate_id: candidateId, selected_id: sid },
              ts: new Date().toISOString(),
            });
          }
        }
        break;
      }
      case "remove_from_selected": {
        var removed = removeFromSelected(candidateId);
        result = { ok: removed, action: "remove_from_selected" };
        if (runState && runState.eventBuffer) {
          runState.eventBuffer.push({
            event_type: "workspace_action",
            step_key: "workspace",
            payload: { action: "remove_from_selected", candidate_id: candidateId },
            ts: new Date().toISOString(),
          });
        }
        break;
      }
      case "mark_core": {
        var sel = _selectedResources.find(function (s) { return s.candidateId === candidateId; });
        var core = sel ? !sel.isCore : true;
        markCore(candidateId, core);
        result = { ok: true, action: "mark_core", isCore: core };
        if (runState && runState.eventBuffer) {
          runState.eventBuffer.push({
            event_type: "workspace_action",
            step_key: "workspace",
            payload: { action: "mark_core", candidate_id: candidateId, is_core: core },
            ts: new Date().toISOString(),
          });
        }
        break;
      }
      case "mark_needs_review": {
        var selR = _selectedResources.find(function (s) { return s.candidateId === candidateId; });
        var needs = selR ? !selR.needsReview : true;
        markForReview(candidateId, needs);
        result = { ok: true, action: "mark_needs_review", needsReview: needs };
        break;
      }
      default:
        break;
    }
    return result;
  }

  // ---------- 公开 API ---------- //

  function getSelectedResources() {
    return _selectedResources.slice();
  }

  function reset() {
    _selectedResources = [];
    _coverageCache = null;
  }

  function isReady() {
    return true;
  }

  global.WorkspaceBoard = {
    addToSelected: addToSelected,
    removeFromSelected: removeFromSelected,
    markCore: markCore,
    markForReview: markForReview,
    computeCoverage: computeCoverage,
    getSelectedResources: getSelectedResources,
    renderWorkspace: renderWorkspace,
    renderSelectedColumn: renderSelectedColumn,
    renderCandidateColumn: renderCandidateColumn,
    renderCoverageSummary: renderCoverageSummary,
    handleAction: handleAction,
    reset: reset,
    isReady: isReady,
  };
})(window);
