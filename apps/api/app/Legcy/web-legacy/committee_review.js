/**
 * Session 30: 委员会复核 UI — 5 视角意见卡 + severity 排序 + revision actions
 *
 * Public API: window.CommitteeReview = { renderReview, renderIssue, renderHistory, isReady }
 */
(function (global) {
  'use strict';

  /* ---------- constants ---------- */

  var PERSPECTIVE_LABELS = {
    advisor: { icon: '👨‍🏫', label: '导师视角' },
    method: { icon: '🔬', label: '方法视角' },
    experiment: { icon: '🧪', label: '实验视角' },
    writing: { icon: '✍️', label: '写作视角' },
    risk: { icon: '⚠️', label: '风险视角' },
  };

  var SEVERITY_STYLES = {
    fatal: { icon: '🔴', label: '致命', cls: 'severity--fatal' },
    high: { icon: '🟠', label: '高', cls: 'severity--high' },
    medium: { icon: '🟡', label: '中', cls: 'severity--medium' },
    low: { icon: '🟢', label: '低', cls: 'severity--low' },
  };

  var VERDICT_STYLES = {
    pass: { icon: '✅', label: '通过', cls: 'verdict--pass' },
    conditional_pass: { icon: '⚠️', label: '有条件通过', cls: 'verdict--conditional' },
    revise: { icon: '🔄', label: '需修改', cls: 'verdict--revise' },
    reject: { icon: '❌', label: '不通过', cls: 'verdict--reject' },
  };

  var _ready = true;

  /* ---------- helpers ---------- */

  function esc(s) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s || ''));
    return d.innerHTML;
  }

  function renderSeverity(severity) {
    var s = SEVERITY_STYLES[severity] || SEVERITY_STYLES.low;
    return '<span class="severity-badge ' + s.cls + '">' + s.icon + ' ' + s.label + '</span>';
  }

  function renderVerdict(verdict) {
    var v = VERDICT_STYLES[verdict] || VERDICT_STYLES.revise;
    return '<span class="verdict-badge ' + v.cls + '">' + v.icon + ' ' + v.label + '</span>';
  }

  function renderPerspective(perspective) {
    var p = PERSPECTIVE_LABELS[perspective] || { icon: '❓', label: perspective };
    return '<span class="perspective-tag">' + p.icon + ' ' + p.label + '</span>';
  }

  /* ---------- issue renderer ---------- */

  function renderIssue(issue) {
    var html = '<div class="review-issue ' + (issue.resolved ? 'issue--resolved' : '') + '" data-issue-id="' + esc(issue.issue_id) + '">';
    html += '<div class="issue-header">';
    html += renderPerspective(issue.perspective);
    html += renderSeverity(issue.severity);
    if (issue.resolved) {
      html += '<span class="issue-resolved-tag">✅ 已处理</span>';
    }
    html += '</div>';
    html += '<div class="issue-message">' + esc(issue.message) + '</div>';
    html += '<div class="issue-fix">💡 ' + esc(issue.suggested_fix) + '</div>';
    if (issue.section_id) {
      html += '<div class="issue-section">📄 相关章节: <code>' + esc(issue.section_id) + '</code></div>';
    }
    html += '<div class="issue-actions">';
    html += '<button class="btn-accept-fix" data-issue-id="' + esc(issue.issue_id) + '" data-action="accept_fix" ' + (issue.resolved ? 'disabled' : '') + '>接受修复</button>';
    html += '<button class="btn-ignore" data-issue-id="' + esc(issue.issue_id) + '" data-action="ignore_issue" ' + (issue.resolved ? 'disabled' : '') + '>忽略</button>';
    html += '</div>';
    html += '</div>';
    return html;
  }

  /* ---------- revision action renderer ---------- */

  function renderAction(action, type) {
    var cls = type === 'required' ? 'action--required' : 'action--optional';
    var label = type === 'required' ? '🔴 必须' : '🔵 可选';
    var html = '<div class="revision-action ' + cls + '">';
    html += '<span class="action-label">' + label + '</span>';
    html += '<span class="action-desc">' + esc(action.description) + '</span>';
    html += '</div>';
    return html;
  }

  /* ---------- main review renderer ---------- */

  function renderReview(review) {
    if (!review) return '<div class="review-empty">暂无复核数据</div>';

    var html = '<div class="committee-review">';

    // Verdict
    html += '<div class="review-verdict-row">';
    html += '<h3>📋 委员会复核</h3>';
    html += renderVerdict(review.verdict);
    html += '</div>';

    // Next revision prompt
    if (review.next_revision_prompt) {
      html += '<div class="review-prompt">📌 ' + esc(review.next_revision_prompt) + '</div>';
    }

    // Issues by severity
    if (review.issues && review.issues.length) {
      var sorted = review.issues.slice().sort(function (a, b) {
        var order = { fatal: 0, high: 1, medium: 2, low: 3 };
        return (order[a.severity] || 9) - (order[b.severity] || 9);
      });

      // Group by perspective
      var groups = {};
      sorted.forEach(function (issue) {
        var p = issue.perspective;
        if (!groups[p]) groups[p] = [];
        groups[p].push(issue);
      });

      Object.keys(groups).forEach(function (perspective) {
        var p = PERSPECTIVE_LABELS[perspective] || { icon: '❓', label: perspective };
        html += '<div class="review-perspective-group">';
        html += '<h4>' + p.icon + ' ' + p.label + ' (' + groups[perspective].length + ')</h4>';
        groups[perspective].forEach(function (issue) {
          html += renderIssue(issue);
        });
        html += '</div>';
      });
    }

    // Required actions
    if (review.required_actions && review.required_actions.length) {
      html += '<div class="review-actions required-actions">';
      html += '<h4>🔴 必须处理 (' + review.required_actions.length + ')</h4>';
      review.required_actions.forEach(function (a) { html += renderAction(a, 'required'); });
      html += '</div>';
    }

    // Optional actions
    if (review.optional_actions && review.optional_actions.length) {
      html += '<div class="review-actions optional-actions">';
      html += '<h4>🔵 可选处理 (' + review.optional_actions.length + ')</h4>';
      review.optional_actions.forEach(function (a) { html += renderAction(a, 'optional'); });
      html += '</div>';
    }

    // Evidence gaps
    if (review.evidence_gaps && review.evidence_gaps.length) {
      html += '<div class="review-gaps">';
      html += '<h4>📎 证据缺口</h4>';
      html += '<ul>';
      review.evidence_gaps.forEach(function (g) {
        html += '<li>' + esc(g) + '</li>';
      });
      html += '</ul>';
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  /* ---------- history renderer ---------- */

  function renderHistory(history) {
    if (!history || !history.rounds || !history.rounds.length) {
      return '<div class="review-history-empty">暂无复核历史</div>';
    }

    var html = '<div class="review-history">';
    html += '<h3>📜 复核历史 — ' + esc(history.topic_title) + '</h3>';
    html += '<p>共 ' + history.rounds.length + ' 轮</p>';

    history.rounds.forEach(function (round) {
      html += '<div class="history-round">';
      html += '<h4>第 ' + round.round_id + ' 轮 ';
      html += renderVerdict(round.verdict);
      html += '</h4>';
      html += '<p>问题: ' + round.issues.length + ' | 必须处理: ' + round.required_actions.length + '</p>';
      html += '</div>';
    });

    html += '</div>';
    return html;
  }

  /* ---------- API ---------- */

  global.CommitteeReview = {
    renderReview: renderReview,
    renderIssue: renderIssue,
    renderHistory: renderHistory,
    isReady: function () { return _ready; },
  };
})(window);
