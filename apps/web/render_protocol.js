// Session 21: 安全 render block 解析器 (SOP §8).
//
// 支持的受控块:
// - ```paperagent-card\n{ "component": "X", "props": {} }\n```
// - <pa-card type="X" id="...">{"props": {}}</pa-card>
//
// 白名单组件 (SOP §8.2):
// - TopicUnderstandingCard / KeywordReviewCard / SearchQueryPlanCard /
//   RetrievalCandidateCard / EvidenceCard / EvidenceRefCard /
//   VerificationCard / FeasibilityCard / PivotRouteCard /
//   HumanReviewCard / FinalReportCard / ReportQualityCard / TraceEventCard
//
// 安全规则 (SOP §8.4):
// 1. 正则只识别块边界
// 2. 块内容必须是 JSON
// 3. JSON 必须过 schema (component 在白名单, props 是 dict)
// 4. action 必须映射到已注册事件
// 5. 文本必须 escape
// 6. 禁止 script / style / iframe / onClick / eval / new Function
// 7. 非法块降级为普通文本或安全错误卡

(function (global) {
  "use strict";

  const WHITELIST = new Set([
    "TopicUnderstandingCard",
    "KeywordReviewCard",
    "SearchQueryPlanCard",
    "RetrievalCandidateCard",
    "EvidenceCard",
    "EvidenceRefCard",
    "VerificationCard",
    "FeasibilityCard",
    "PivotRouteCard",
    "HumanReviewCard",
    "FinalReportCard",
    "ReportQualityCard",
    "TraceEventCard",
  ]);

  const KNOWN_ACTIONS = new Set([
    "approve_step",
    "revise_step",
    "regenerate_step",
    "skip_step",
    "open_drawer",
  ]);

  // 危险模式: 任何脚本 / 事件处理器 / 远程加载
  const FORBIDDEN = [
    /<script\b/i,
    /<\/script>/i,
    /<style\b/i,
    /<\/style>/i,
    /<iframe\b/i,
    /<object\b/i,
    /<embed\b/i,
    /\bon\w+\s*=/i,        // onclick / onerror / onload 等
    /\beval\s*\(/i,
    /\bnew\s+Function\s*\(/i,
    /javascript:/i,
    /data:text\/html/i,
  ];

  // ---------- 块识别 ----------

  // 块 1: ```paperagent-card ... ``` (fenced code block)
  const FENCED_RE = /```paperagent-card\s*\n([\s\S]+?)\n```/g;

  // 块 2: <pa-card type="X" id="...">{"props": ...}</pa-card>
  // props 体是 JSON, 不允许有 '>' 干扰, 所以非贪婪 + [^{}]+ 提取
  const PA_CARD_RE = /<pa-card\s+type="([A-Za-z][A-Za-z0-9_]*)"(?:\s+id="([^"]*)")?\s*>([\s\S]+?)<\/pa-card>/g;

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function containsForbidden(text) {
    if (!text) return null;
    for (const re of FORBIDDEN) {
      if (re.test(text)) {
        return re.source;
      }
    }
    return null;
  }

  function isValidProps(p) {
    return p !== null && typeof p === "object" && !Array.isArray(p);
  }

  function containsEventHandlerKey(obj, path) {
    // 递归检查 object 中是否存在以 on 开头的 key (事件处理器)
    if (!obj || typeof obj !== "object") return null;
    for (const k of Object.keys(obj)) {
      if (/^on/i.test(k)) {
        return path + "." + k;
      }
      const v = obj[k];
      if (v && typeof v === "object") {
        const inner = containsEventHandlerKey(v, path + "." + k);
        if (inner) return inner;
      }
    }
    return null;
  }

  function validateCard(parsed) {
    if (!parsed || typeof parsed !== "object") return "不是 JSON 对象";
    if (typeof parsed.component !== "string") return "缺 component 字段";
    if (!WHITELIST.has(parsed.component)) return `component 不在白名单: ${parsed.component}`;
    if (parsed.props !== undefined && !isValidProps(parsed.props)) return "props 必须是 object";
    if (parsed.props) {
      const evt = containsEventHandlerKey(parsed.props, "props");
      if (evt) return `含事件处理器 key (${evt}), 不允许`;
    }
    if (parsed.actions !== undefined) {
      if (!Array.isArray(parsed.actions)) return "actions 必须是数组";
      for (const a of parsed.actions) {
        if (!a || typeof a !== "object" || typeof a.id !== "string" || typeof a.event !== "string") {
          return "action 缺 id / event";
        }
        if (!KNOWN_ACTIONS.has(a.event)) return `action event 不在白名单: ${a.event}`;
      }
    }
    return null;
  }

  // ---------- 块解析 ----------

  function parseFenced(text) {
    const out = [];
    let m;
    FENCED_RE.lastIndex = 0;
    while ((m = FENCED_RE.exec(text)) !== null) {
      const raw = m[1];
      const danger = containsForbidden(raw);
      if (danger) {
        out.push({ ok: false, raw: m[0], reason: `包含禁止模式: ${danger}` });
        continue;
      }
      let parsed = null;
      try {
        parsed = JSON.parse(raw);
      } catch (e) {
        out.push({ ok: false, raw: m[0], reason: `JSON 解析失败: ${e.message}` });
        continue;
      }
      const err = validateCard(parsed);
      if (err) {
        out.push({ ok: false, raw: m[0], reason: err });
        continue;
      }
      out.push({ ok: true, raw: m[0], block: parsed });
    }
    return out;
  }

  function parsePaCard(text) {
    const out = [];
    let m;
    PA_CARD_RE.lastIndex = 0;
    while ((m = PA_CARD_RE.exec(text)) !== null) {
      const component = m[1];
      const cardId = m[2] || ("pa_card_" + out.length);
      const body = m[3].trim();
      const danger = containsForbidden(body);
      if (danger) {
        out.push({ ok: false, raw: m[0], reason: `包含禁止模式: ${danger}` });
        continue;
      }
      let parsed = null;
      try {
        parsed = JSON.parse(body);
      } catch (e) {
        out.push({ ok: false, raw: m[0], reason: `JSON 解析失败: ${e.message}` });
        continue;
      }
      // 把 pa-card 标签信息合并进 props
      const props = (parsed && parsed.props) || {};
      const block = {
        component: component,
        id: cardId,
        props: props,
        actions: parsed && parsed.actions ? parsed.actions : [],
      };
      const err = validateCard(block);
      if (err) {
        out.push({ ok: false, raw: m[0], reason: err });
        continue;
      }
      out.push({ ok: true, raw: m[0], block: block });
    }
    return out;
  }

  // ---------- 顶层: parse(text) -> { blocks[], plainText }

  function parse(text) {
    if (!text || typeof text !== "string") {
      return { blocks: [], plainText: "" };
    }
    const blocks = [];
    const consumedRanges = [];

    // 收集 fenced
    for (const r of parseFenced(text)) {
      blocks.push(r);
      if (r.ok) {
        const start = text.indexOf(r.raw);
        consumedRanges.push([start, start + r.raw.length]);
      }
    }
    // 收集 pa-card
    for (const r of parsePaCard(text)) {
      blocks.push(r);
      if (r.ok) {
        const start = text.indexOf(r.raw);
        consumedRanges.push([start, start + r.raw.length]);
      }
    }

    // 计算剩余 plain text
    let plainText = "";
    let cursor = 0;
    const sorted = consumedRanges.sort((a, b) => a[0] - b[0]);
    for (const [s, e] of sorted) {
      if (s < 0) continue;
      if (s > cursor) plainText += text.slice(cursor, s);
      cursor = Math.max(cursor, e);
    }
    if (cursor < text.length) plainText += text.slice(cursor);

    return { blocks: blocks, plainText: plainText };
  }

  // ---------- 渲染 block 为安全 HTML ----------

  function renderBlock(block) {
    if (!block || !block.component) return "";
    const propsJson = escapeHtml(JSON.stringify(block.props || {}));
    const meta = `<div class="pa-card-meta">
      <span class="pa-card-component">${escapeHtml(block.component)}</span>
      <span class="pa-card-id">${escapeHtml(block.id || "")}</span>
    </div>`;
    // 不直接渲染 props (避免任意 HTML), 只做摘要
    let bodyHtml = "";
    if (block.component === "KeywordReviewCard") {
      const kws = (block.props && block.props.keywords) || [];
      bodyHtml = '<div class="pa-card-keywords">' + kws.map(function (k) {
        return '<span class="pa-kw" data-kind="' + escapeHtml(k.kind || "other") + '">' +
          escapeHtml(k.text) + '</span>';
      }).join("") + '</div>';
    } else {
      // 通用 JSON 摘要
      bodyHtml = '<pre class="pa-card-props">' + propsJson + '</pre>';
    }
    return '<div class="pa-card pa-card--' + escapeHtml(block.component) + '">' +
      meta + bodyHtml + '</div>';
  }

  // ---------- 渲染整段文本 + 块 ----------

  function renderText(text) {
    const parsed = parse(text);
    const parts = [];
    let cursor = 0;
    // 按出现顺序拼接 plain + block
    const tokens = [];
    for (const b of parsed.blocks) {
      const start = text.indexOf(b.raw);
      tokens.push({ start: start, end: start + b.raw.length, block: b });
    }
    tokens.sort((a, b) => a.start - b.start);
    for (const t of tokens) {
      if (t.start < 0) continue;
      if (t.start > cursor) {
        parts.push('<p class="pa-plain">' + escapeHtml(text.slice(cursor, t.start)) + '</p>');
      }
      if (t.block.ok) {
        parts.push(renderBlock(t.block.block));
      } else {
        // 降级: 显示为安全错误块
        parts.push('<div class="pa-card pa-card--invalid">' +
          '<div class="pa-card-meta"><span class="pa-card-component">⚠ 非法块已降级</span></div>' +
          '<pre class="pa-card-props">' + escapeHtml(t.block.reason) + '</pre>' +
          '</div>');
      }
      cursor = t.end;
    }
    if (cursor < text.length) {
      parts.push('<p class="pa-plain">' + escapeHtml(text.slice(cursor)) + '</p>');
    }
    return parts.join("");
  }

  global.RenderProtocol = {
    WHITELIST: Array.from(WHITELIST),
    KNOWN_ACTIONS: Array.from(KNOWN_ACTIONS),
    parse: parse,
    renderText: renderText,
    renderBlock: renderBlock,
    escapeHtml: escapeHtml,
    validateCard: validateCard,
  };
})(window);
