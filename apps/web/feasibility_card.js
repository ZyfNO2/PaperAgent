// Session 28: Feasibility Card — 可行性风险裁决前端模块 (SOP §3-4)
//
// 公开 API:
//   FeasibilityCard.renderAssessment(assessment)
//   FeasibilityCard.renderDimension(dim)
//   FeasibilityCard.renderPivotRoute(route, idx)
//   FeasibilityCard.renderHardVeto(veto)
//   FeasibilityCard.verdictBadge(verdict)
//   FeasibilityCard.isReady()

(function (global) {
  "use strict";

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  var VERDICT_STYLES = {
    GO: { icon: "✅", cls: "verdict--go", label: "GO" },
    CONDITIONAL: { icon: "⚠️", cls: "verdict--conditional", label: "CONDITIONAL" },
    PIVOT: { icon: "🔄", cls: "verdict--pivot", label: "PIVOT" },
    PARK: { icon: "⏸️", cls: "verdict--park", label: "PARK" },
    STOP: { icon: "🛑", cls: "verdict--stop", label: "STOP" },
  };

  var LEVEL_ICONS = { low: "🟢", medium: "🟡", high: "🟠", fatal: "🔴" };
  var ROUTE_ICONS = { conservative: "🐢", balanced: "⚖️", aggressive: "🚀" };

  function verdictBadge(verdict) {
    var v = VERDICT_STYLES[verdict] || VERDICT_STYLES.PARK;
    return '<span class="verdict-badge ' + esc(v.cls) + '" data-verdict="' + esc(verdict) + '">' +
      v.icon + ' ' + esc(v.label) + '</span>';
  }

  function renderDimension(dim) {
    var html = '<div class="feasibility-dim" data-dimension="' + esc(dim.dimension) + '">';
    html += '<div class="dim-header">';
    html += '<span class="dim-icon">' + (LEVEL_ICONS[dim.level] || "⚪") + '</span>';
    html += '<span class="dim-name">' + esc(dim.dimension) + '</span>';
    html += '<span class="dim-score">' + dim.score + '/100</span>';
    html += '</div>';
    html += '<div class="dim-reason">' + esc(dim.reason) + '</div>';
    if (dim.suggestion) {
      html += '<div class="dim-suggestion">💡 ' + esc(dim.suggestion) + '</div>';
    }
    if (dim.missing_evidence && dim.missing_evidence.length) {
      html += '<div class="dim-missing">';
      html += '<span class="dim-missing-label">⚠️ 缺少：</span>';
      dim.missing_evidence.forEach(function (m) {
        html += '<span class="dim-missing-item">' + esc(m) + '</span>';
      });
      html += '</div>';
    }
    if (dim.evidence_refs && dim.evidence_refs.length) {
      html += '<div class="dim-evidence">📎 证据：' + dim.evidence_refs.map(esc).join(", ") + '</div>';
    }
    html += '</div>';
    return html;
  }

  function renderHardVeto(veto) {
    if (!veto.triggered) return "";
    return '<div class="hard-veto hard-veto--triggered" data-rule="' + esc(veto.rule) + '">' +
      '<span class="veto-icon">🚫</span>' +
      '<span class="veto-desc">' + esc(veto.description) + '</span>' +
      '</div>';
  }

  function renderPivotRoute(route, idx) {
    var html = '<div class="pivot-route" data-route-type="' + esc(route.route_type) + '">';
    html += '<div class="route-header">';
    html += '<span class="route-icon">' + (ROUTE_ICONS[route.route_type] || "🔀") + '</span>';
    html += '<span class="route-title">' + esc(route.new_topic) + '</span>';
    html += '</div>';
    html += '<div class="route-details">';
    if (route.changed_keywords.length) {
      html += '<div class="route-keywords">🔑 ' + route.changed_keywords.map(esc).join(" / ") + '</div>';
    }
    if (route.required_evidence.length) {
      html += '<div class="route-evidence">📋 需要：' + route.required_evidence.map(esc).join("；") + '</div>';
    }
    if (route.expected_workload) {
      html += '<div class="route-workload">⏱️ 工作量：' + esc(route.expected_workload) + '</div>';
    }
    if (route.risk_delta) {
      html += '<div class="route-risk">📊 风险变化：' + esc(route.risk_delta) + '</div>';
    }
    if (route.recommended_for) {
      html += '<div class="route-for">👤 适合：' + esc(route.recommended_for) + '</div>';
    }
    html += '</div>';
    html += '<button class="cta-mini cta-mini--pivot" data-action="select_pivot" data-route-index="' + idx + '">选择此路线（需确认）</button>';
    html += '</div>';
    return html;
  }

  function renderAssessment(assessment) {
    var html = '<div class="feasibility-card">';

    // 标题
    html += '<h3 class="feasibility-title">📊 可行性评估</h3>';

    // 裁决 + 分数
    html += '<div class="feasibility-verdict">';
    html += verdictBadge(assessment.verdict);
    html += '<span class="feasibility-score">综合评分：' + assessment.overall_score + '/100</span>';
    html += '</div>';

    // 摘要
    if (assessment.summary) {
      html += '<div class="feasibility-summary">' + esc(assessment.summary) + '</div>';
    }

    // 硬性否决
    var triggeredVetoes = (assessment.hard_vetoes || []).filter(function (v) { return v.triggered; });
    if (triggeredVetoes.length) {
      html += '<div class="feasibility-vetoes">';
      html += '<h4>🚫 硬性否决项</h4>';
      triggeredVetoes.forEach(function (v) { html += renderHardVeto(v); });
      html += '</div>';
    }

    // 7 维
    html += '<div class="feasibility-dimensions">';
    html += '<h4>📋 风险维度（7维）</h4>';
    (assessment.dimensions || []).forEach(function (d) { html += renderDimension(d); });
    html += '</div>';

    // PIVOT 路线
    if (assessment.pivot_routes && assessment.pivot_routes.length) {
      html += '<div class="feasibility-pivots">';
      html += '<h4>🔀 PIVOT 路线建议</h4>';
      assessment.pivot_routes.forEach(function (r, i) { html += renderPivotRoute(r, i); });
      html += '</div>';
    }

    // 缺口
    if (assessment.missing_evidence && assessment.missing_evidence.length) {
      html += '<div class="feasibility-missing">';
      html += '<h4>⚠️ 证据缺口</h4>';
      assessment.missing_evidence.forEach(function (m) {
        html += '<div class="missing-item">• ' + esc(m) + '</div>';
      });
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  function isReady() {
    return true;
  }

  global.FeasibilityCard = {
    renderAssessment: renderAssessment,
    renderDimension: renderDimension,
    renderPivotRoute: renderPivotRoute,
    renderHardVeto: renderHardVeto,
    verdictBadge: verdictBadge,
    isReady: isReady,
  };
})(window);
