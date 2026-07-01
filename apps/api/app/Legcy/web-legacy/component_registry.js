// Session 22: Renderer Component Registry (SOP §4-6).
//
// 统一注册表：component -> schema -> render -> actions -> fallback
// 第一批 6 张核心卡 + 7 张通用 JSON 降级卡。
//
// 22-a 范围：纯前端注册表，不影响 S21 mock stream 事件协议。

(function (global) {
  "use strict";

  // ---------- helpers ----------

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escObj(obj) {
    return esc(JSON.stringify(obj, null, 2));
  }

  // ---------- 核心卡 schema validators ----------

  function validateTopicUnderstandingCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!props.topic || typeof props.topic !== "string") return { ok: false, error: "missing or invalid topic" };
    return { ok: true };
  }

  function validateKeywordReviewCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!Array.isArray(props.keywords)) return { ok: false, error: "missing or invalid keywords array" };
    for (var i = 0; i < props.keywords.length; i++) {
      var k = props.keywords[i];
      if (!k || typeof k.text !== "string") return { ok: false, error: "keyword[" + i + "] missing text" };
    }
    return { ok: true };
  }

  function validateSearchQueryPlanCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!Array.isArray(props.queries)) return { ok: false, error: "missing or invalid queries array" };
    for (var i = 0; i < props.queries.length; i++) {
      var q = props.queries[i];
      if (!q || typeof q.query !== "string") return { ok: false, error: "query[" + i + "] missing query text" };
    }
    return { ok: true };
  }

  function validateRetrievalCandidateCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!props.kind || typeof props.kind !== "string") return { ok: false, error: "missing or invalid kind" };
    if (!props.title || typeof props.title !== "string") return { ok: false, error: "missing or invalid title" };
    if (!Array.isArray(props.matched_keywords)) return { ok: false, error: "missing or invalid matched_keywords" };
    return { ok: true };
  }

  function validateEvidenceRefCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!props.evidence_id || typeof props.evidence_id !== "string") return { ok: false, error: "missing or invalid evidence_id" };
    if (!props.source_type || typeof props.source_type !== "string") return { ok: false, error: "missing or invalid source_type" };
    if (!props.claim || typeof props.claim !== "string") return { ok: false, error: "missing or invalid claim" };
    return { ok: true };
  }

  function validateReportQualityCard(props) {
    if (!props) return { ok: false, error: "missing props" };
    if (!Array.isArray(props.checks)) return { ok: false, error: "missing or invalid checks array" };
    for (var i = 0; i < props.checks.length; i++) {
      var c = props.checks[i];
      if (!c || typeof c.name !== "string") return { ok: false, error: "check[" + i + "] missing name" };
      if (c.status !== "pass" && c.status !== "warn" && c.status !== "fail") {
        return { ok: false, error: "check[" + i + "] invalid status: " + c.status };
      }
    }
    return { ok: true };
  }

  // ---------- 核心卡 render functions ----------

  function renderTopicUnderstandingCard(card) {
    var p = card.props || {};
    var tags = "";
    if (Array.isArray(p.assumptions) && p.assumptions.length) {
      tags += '<div class="pa-card-section"><span class="pa-card-label">假设</span>' +
        p.assumptions.map(function (a) { return '<span class="pa-tag pa-tag--info">' + esc(a) + '</span>'; }).join("") +
        '</div>';
    }
    if (Array.isArray(p.risks) && p.risks.length) {
      tags += '<div class="pa-card-section"><span class="pa-card-label">风险</span>' +
        p.risks.map(function (r) { return '<span class="pa-tag pa-tag--warn">' + esc(r) + '</span>'; }).join("") +
        '</div>';
    }
    return '<div class="pa-card pa-card--TopicUnderstandingCard" data-component="TopicUnderstandingCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">📝 TopicUnderstandingCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-field"><span class="pa-card-label">题目</span>' +
        '<span class="pa-card-value pa-card-value--topic">' + esc(p.topic) + '</span></div>' +
      (p.intent ? '<div class="pa-card-field"><span class="pa-card-label">意图</span>' +
        '<span class="pa-card-value">' + esc(p.intent) + '</span></div>' : '') +
      tags +
      '</div>';
  }

  function renderKeywordReviewCard(card) {
    var p = card.props || {};
    var kws = p.keywords || [];
    var editable = p.editable;
    return '<div class="pa-card pa-card--KeywordReviewCard' + (editable ? ' is-editable' : '') + '" data-component="KeywordReviewCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">🔑 KeywordReviewCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-keywords" data-card-id="' + esc(card.id || "") + '">' +
        kws.map(function (k, i) {
          return '<span class="pa-kw" data-kind="' + esc(k.kind || "other") + '" data-idx="' + i + '">' +
            '<span class="pa-kw__text">' + esc(k.text) + '</span>' +
            (editable ? '<button class="pa-kw__del" data-action="del" data-idx="' + i + '" type="button">✕</button>' : '') +
            '</span>';
        }).join("") +
      '</div>' +
      (editable ?
        '<div class="pa-card-actions">' +
          '<button class="cta-mini" data-gate-action="approve" data-step-key="keyword_review" type="button">✅ 确认并继续</button>' +
          '<button class="cta-mini" data-gate-action="revise" data-step-key="keyword_review" type="button">✏️ 修改并继续</button>' +
        '</div>' : '') +
      '</div>';
  }

  function renderSearchQueryPlanCard(card) {
    var p = card.props || {};
    var queries = p.queries || [];
    var rows = queries.map(function (q, i) {
      return '<div class="pa-card-query" data-idx="' + i + '">' +
        '<span class="pa-card-query-source">' + esc(q.source || "unknown") + '</span>' +
        '<span class="pa-card-query-text">' + esc(q.query) + '</span>' +
        '</div>';
    }).join("");
    return '<div class="pa-card pa-card--SearchQueryPlanCard" data-component="SearchQueryPlanCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">📋 SearchQueryPlanCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-queries">' + rows + '</div>' +
      '</div>';
  }

  function renderRetrievalCandidateCard(card) {
    var p = card.props || {};
    var kindIcons = { paper: "📄", dataset: "📊", repo: "💻" };
    var icon = kindIcons[p.kind] || "📎";
    var kws = (p.matched_keywords || []).map(function (kw) {
      return '<span class="pa-tag pa-tag--keyword">' + esc(kw) + '</span>';
    }).join("");
    return '<div class="pa-card pa-card--RetrievalCandidateCard" data-component="RetrievalCandidateCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">' + icon + ' RetrievalCandidateCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-field"><span class="pa-card-label">类型</span>' +
        '<span class="pa-card-value">' + esc(p.kind) + '</span></div>' +
      '<div class="pa-card-field"><span class="pa-card-label">标题</span>' +
        '<span class="pa-card-value pa-card-value--title">' + esc(p.title) + '</span></div>' +
      (p.url ? '<div class="pa-card-field"><span class="pa-card-label">URL</span>' +
        '<span class="pa-card-value"><a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer">' +
        esc(p.url) + '</a></span></div>' : '') +
      (p.confidence ? '<div class="pa-card-field"><span class="pa-card-label">置信度</span>' +
        '<span class="pa-card-value pa-tag--' + esc(p.confidence) + '">' + esc(p.confidence) + '</span></div>' : '') +
      (kws ? '<div class="pa-card-section"><span class="pa-card-label">匹配关键词</span>' + kws + '</div>' : '') +
      '<div class="pa-card-actions">' +
        '<button class="cta-mini" data-card-action="save_candidate" data-card-id="' + esc(card.id || "") + '" type="button">💾 保存候选</button>' +
        '<button class="cta-mini" data-card-action="reject_candidate" data-card-id="' + esc(card.id || "") + '" type="button">❌ 淘汰</button>' +
        '<button class="cta-mini" data-card-action="open_drawer" data-card-id="' + esc(card.id || "") + '" type="button">📂 详情</button>' +
      '</div>' +
      '</div>';
  }

  function renderEvidenceRefCard(card) {
    var p = card.props || {};
    var statusIcon = p.verified ? "✅" : "⏳";
    return '<div class="pa-card pa-card--EvidenceRefCard" data-component="EvidenceRefCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">📎 EvidenceRefCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-field"><span class="pa-card-label">证据 ID</span>' +
        '<span class="pa-card-value">' + esc(p.evidence_id) + '</span></div>' +
      '<div class="pa-card-field"><span class="pa-card-label">来源类型</span>' +
        '<span class="pa-card-value">' + esc(p.source_type) + '</span></div>' +
      '<div class="pa-card-field"><span class="pa-card-label">声明</span>' +
        '<span class="pa-card-value">' + esc(p.claim) + '</span></div>' +
      '<div class="pa-card-field"><span class="pa-card-label">支持等级</span>' +
        '<span class="pa-card-value">' + esc(p.support_level || "unknown") + '</span></div>' +
      '<div class="pa-card-field"><span class="pa-card-label">状态</span>' +
        '<span class="pa-card-value">' + statusIcon + ' ' + (p.verified ? "已验证" : "待验证") + '</span></div>' +
      '</div>';
  }

  function renderReportQualityCard(card) {
    var p = card.props || {};
    var checks = (p.checks || []).map(function (c) {
      var icon = { pass: "✅", warn: "⚠️", fail: "❌" }[c.status] || "❓";
      return '<div class="pa-card-check pa-card-check--' + esc(c.status) + '">' +
        '<span class="pa-card-check-icon">' + icon + '</span>' +
        '<span class="pa-card-check-name">' + esc(c.name) + '</span>' +
        '</div>';
    }).join("");
    return '<div class="pa-card pa-card--ReportQualityCard" data-component="ReportQualityCard">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">📊 ReportQualityCard</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-checks">' + checks + '</div>' +
      '</div>';
  }

  // ---------- 降级渲染器（其余白名单组件） ----------

  function renderFallbackJSON(card) {
    return '<div class="pa-card pa-card--fallback" data-component="' + esc(card.component || "unknown") + '">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">📦 ' + esc(card.component || "unknown") + '</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<pre class="pa-card-props">' + escObj(card.props || {}) + '</pre>' +
      '</div>';
  }

  function renderInvalidCard(card, error) {
    return '<div class="pa-card pa-card--invalid" data-component="invalid">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">⚠️ 安全降级卡</span>' +
        '<span class="pa-card-id">' + esc(card.id || "") + '</span>' +
      '</div>' +
      '<p class="pa-card-error">组件 <code>' + esc(card.component) + '</code> 未通过校验: ' + esc(error) + '</p>' +
      '</div>';
  }

  // ---------- Registry ----------

  var REGISTRY = {};

  function register(name, def) {
    REGISTRY[name] = def;
  }

  // 注册 6 类核心卡
  register("TopicUnderstandingCard", {
    schema: validateTopicUnderstandingCard,
    render: renderTopicUnderstandingCard,
    actions: [],                   // 只读，无交互动作
    selector: ".pa-card--TopicUnderstandingCard"
  });

  register("KeywordReviewCard", {
    schema: validateKeywordReviewCard,
    render: renderKeywordReviewCard,
    actions: ["approve_step", "revise_step", "regenerate_step"],
    selector: ".pa-card--KeywordReviewCard"
  });

  register("SearchQueryPlanCard", {
    schema: validateSearchQueryPlanCard,
    render: renderSearchQueryPlanCard,
    actions: ["approve_step", "revise_step"],
    selector: ".pa-card--SearchQueryPlanCard"
  });

  register("RetrievalCandidateCard", {
    schema: validateRetrievalCandidateCard,
    render: renderRetrievalCandidateCard,
    actions: ["save_candidate", "reject_candidate", "open_drawer"],
    selector: ".pa-card--RetrievalCandidateCard"
  });

  register("EvidenceRefCard", {
    schema: validateEvidenceRefCard,
    render: renderEvidenceRefCard,
    actions: ["mark_needs_review"],
    selector: ".pa-card--EvidenceRefCard"
  });

  register("ReportQualityCard", {
    schema: validateReportQualityCard,
    render: renderReportQualityCard,
    actions: [],
    selector: ".pa-card--ReportQualityCard"
  });

  // ---------- 对外接口 ----------

  function get(name) {
    return REGISTRY[name] || null;
  }

  function has(name) {
    return name in REGISTRY;
  }

  function isActionAllowed(componentName, actionId) {
    var def = REGISTRY[componentName];
    if (!def) return false;
    return def.actions.indexOf(actionId) !== -1;
  }

  function validateCard(card) {
    var compName = card && (card.component || card.type);
    if (!card || typeof compName !== "string") {
      return { ok: false, error: "missing or invalid component" };
    }
    var def = REGISTRY[compName];
    if (!def) {
      // 白名单但非核心卡：允许解析，使用通用 JSON 降级
      return { ok: true, fallback: true };
    }
    var result = def.schema(card.props);
    if (!result.ok) return result;
    return { ok: true, fallback: false };
  }

  function renderCard(card) {
    // 兼容 run_state 的 type 字段和直接构造的 component 字段
    var compName = card && (card.component || card.type);
    if (!card || typeof compName !== "string") {
      return renderInvalidCard(card || {}, "missing component");
    }
    var def = REGISTRY[compName];
    if (!def) {
      // 非核心卡：JSON 降级
      return renderFallbackJSON(card);
    }
    var v = def.schema(card.props);
    if (!v.ok) {
      return renderInvalidCard(card, v.error);
    }
    return def.render(card);
  }

  // ---------- 全局导出 ----------

  global.ComponentRegistry = {
    register: register,
    get: get,
    has: has,
    isActionAllowed: isActionAllowed,
    validateCard: validateCard,
    renderCard: renderCard,
    renderInvalidCard: renderInvalidCard,
    renderFallbackJSON: renderFallbackJSON,
    _registry: REGISTRY
  };

})(window);
