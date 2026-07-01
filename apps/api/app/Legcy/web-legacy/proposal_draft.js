/**
 * Session 29: 开题报告草稿 UI — 12 节可折叠 + 证据绑定 + 置信度指示器 + 工作量 + 创新点
 *
 * Public API: window.ProposalDraft = { renderDraft, renderSection, renderInnovation, renderWorkload, isReady }
 */
(function (global) {
  'use strict';

  /* ---------- constants ---------- */

  var SECTION_ICONS = {
    topic_direction: '🎯',
    background: '📖',
    literature_review: '📚',
    research_objectives: '🏁',
    research_content: '📝',
    technical_approach: '🔧',
    dataset_experiment: '📊',
    innovation: '💡',
    workload: '📋',
    feasibility_risk: '⚖️',
    reference_resources: '📎',
    missing_evidence: '❓',
  };

  var CONFIDENCE_LABELS = {
    high: { icon: '🟢', label: '高置信', cls: 'confidence--high' },
    medium: { icon: '🟡', label: '中置信', cls: 'confidence--medium' },
    low: { icon: '🔴', label: '低置信', cls: 'confidence--low' },
  };

  var _ready = true;

  /* ---------- render helpers ---------- */

  function esc(s) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s || ''));
    return d.innerHTML;
  }

  function renderConfidence(level) {
    var c = CONFIDENCE_LABELS[level] || CONFIDENCE_LABELS.low;
    return '<span class="confidence-badge ' + c.cls + '">' + c.icon + ' ' + c.label + '</span>';
  }

  function renderEvidenceBinding(section) {
    var html = '<div class="section-evidence">';

    if (section.evidence_refs && section.evidence_refs.length) {
      html += '<div class="ev-group"><span class="ev-label">📎 EvidenceRef:</span> ';
      html += section.evidence_refs.map(function (r) { return '<code>' + esc(r) + '</code>'; }).join(', ');
      html += '</div>';
    }

    if (section.selected_refs && section.selected_refs.length) {
      html += '<div class="ev-group"><span class="ev-label">✅ Selected:</span> ';
      html += section.selected_refs.map(function (r) { return '<code>' + esc(r) + '</code>'; }).join(', ');
      html += '</div>';
    }

    if (section.candidate_refs && section.candidate_refs.length) {
      html += '<div class="ev-group"><span class="ev-label">📦 Candidate:</span> ';
      html += section.candidate_refs.map(function (r) { return '<code>' + esc(r) + '</code>'; }).join(', ');
      html += '</div>';
    }

    if (section.missing_evidence && section.missing_evidence.length) {
      html += '<div class="ev-group ev-missing"><span class="ev-label">⚠️ 缺少:</span> ';
      html += section.missing_evidence.map(function (m) { return '<span class="missing-tag">' + esc(m) + '</span>'; }).join(' ');
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  /* ---------- section renderer ---------- */

  function renderSection(section, idx) {
    var icon = SECTION_ICONS[section.section_id] || '📄';
    var hasWarning = (!section.evidence_refs || !section.evidence_refs.length) &&
                    (!section.selected_refs || !section.selected_refs.length) &&
                    section.confidence === 'low';

    var html = '<div class="proposal-section" data-section-id="' + esc(section.section_id) + '">';
    html += '<div class="section-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html += '<span class="section-icon">' + icon + '</span>';
    html += '<span class="section-num">' + (idx + 1) + '.</span>';
    html += '<span class="section-title">' + esc(section.title) + '</span>';
    html += renderConfidence(section.confidence);
    if (hasWarning) {
      html += '<span class="section-warning">⚠️ 缺证据</span>';
    }
    html += '<span class="section-toggle">▼</span>';
    html += '</div>';
    html += '<div class="section-body">';
    html += '<div class="section-content">' + esc(section.content) + '</div>';
    html += renderEvidenceBinding(section);
    html += '</div>';
    html += '</div>';
    return html;
  }

  /* ---------- innovation point ---------- */

  function renderInnovation(ip, idx) {
    var html = '<div class="innovation-card">';
    html += '<div class="innovation-header">';
    html += '<span class="innovation-num">💡 ' + (idx + 1) + '.</span>';
    html += '<span class="innovation-title">' + esc(ip.title) + '</span>';
    html += '</div>';
    html += '<div class="innovation-desc">' + esc(ip.description) + '</div>';
    html += '<div class="innovation-meta">';
    html += '<span class="innovation-evidence">📎 证据基础: ' + esc(ip.evidence_base) + '</span>';
    html += '<span class="innovation-risk">⚠️ 风险: ' + esc(ip.risk) + '</span>';
    html += '</div>';
    html += '</div>';
    return html;
  }

  /* ---------- workload item ---------- */

  function renderWorkloadItem(wi, idx) {
    var html = '<div class="workload-item">';
    html += '<span class="workload-num">' + (idx + 1) + '.</span>';
    html += '<span class="workload-name">' + esc(wi.item) + '</span>';
    if (wi.estimated_weeks) {
      html += '<span class="workload-weeks">~' + wi.estimated_weeks + ' 周</span>';
    }
    html += '</div>';
    return html;
  }

  /* ---------- main draft renderer ---------- */

  function renderDraft(draft) {
    if (!draft || !draft.sections) return '<div class="proposal-empty">暂无报告数据</div>';

    var html = '<div class="proposal-draft">';
    html += '<h3 class="proposal-title">📄 开题报告草稿 — ' + esc(draft.topic_title) + '</h3>';

    if (draft.feasibility_summary) {
      html += '<div class="proposal-feasibility">⚖️ 可行性: ' + esc(draft.feasibility_summary) + '</div>';
    }

    // 12 sections
    html += '<div class="proposal-sections">';
    draft.sections.forEach(function (s, i) {
      html += renderSection(s, i);
    });
    html += '</div>';

    // Innovation points
    if (draft.innovation_points && draft.innovation_points.length) {
      html += '<div class="proposal-innovation">';
      html += '<h4>💡 创新点</h4>';
      draft.innovation_points.forEach(function (ip, i) {
        html += renderInnovation(ip, i);
      });
      html += '</div>';
    }

    // Workload
    if (draft.workload_items && draft.workload_items.length) {
      html += '<div class="proposal-workload">';
      html += '<h4>📋 工作量拆解</h4>';
      draft.workload_items.forEach(function (wi, i) {
        html += renderWorkloadItem(wi, i);
      });
      html += '</div>';
    }

    // Overall missing
    if (draft.overall_missing && draft.overall_missing.length) {
      html += '<div class="proposal-overall-missing">';
      html += '<h4>⚠️ 待补证据汇总</h4>';
      html += '<ul>';
      draft.overall_missing.forEach(function (m) {
        html += '<li class="missing-tag">' + esc(m) + '</li>';
      });
      html += '</ul>';
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  /* ---------- API ---------- */

  global.ProposalDraft = {
    renderDraft: renderDraft,
    renderSection: renderSection,
    renderInnovation: renderInnovation,
    renderWorkload: renderWorkloadItem,
    isReady: function () { return _ready; },
  };
})(window);
