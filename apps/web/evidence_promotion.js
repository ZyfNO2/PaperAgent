// Session 26: Evidence Promotion module.
//
// 候选→证据晋升闸门前端逻辑。
// 只有 selected + URLVerified + user_confirmed 才能晋升。
// Selected != Evidence 是不变式。

(function (global) {
  "use strict";

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

  // ---------- Promotion Gate Check ---------- //

  function checkPromotionGate(candidate, selectedResources, urlVerifications) {
    var blockers = [];
    var warnings = [];

    // 检查是否已选中
    var sel = null;
    if (selectedResources && selectedResources.length) {
      sel = selectedResources.find(function (s) { return s.candidateId === candidate.id; });
    }
    if (!sel) {
      blockers.push("Candidate " + candidate.id + " is not selected.");
    }

    // 检查 URL 验证状态
    var urlStatus = "unchecked";
    if (sel && sel.verificationStatus) {
      urlStatus = sel.verificationStatus;
    }
    if (urlVerifications && urlVerifications[candidate.id]) {
      urlStatus = urlVerifications[candidate.id].status || urlStatus;
    }

    if (urlStatus === "unchecked") {
      blockers.push("URL for " + candidate.id + " is not verified.");
    } else if (urlStatus === "failed") {
      var reason = (urlVerifications && urlVerifications[candidate.id] && urlVerifications[candidate.id].failure_reason) || "unknown";
      blockers.push("URL verification failed for " + candidate.id + ": " + reason);
    } else if (urlStatus === "expired") {
      blockers.push("URL verification expired for " + candidate.id + ".");
    } else if (urlStatus === "partial") {
      warnings.push("URL for " + candidate.id + " is only partially verified.");
    }

    return {
      status: blockers.length ? "blocked" : "eligible",
      blockers: blockers,
      warnings: warnings,
    };
  }

  // ---------- Promote to Evidence ---------- //

  function promoteToEvidence(candidate, selectedResources, urlVerifications, reason, claimHint) {
    var gate = checkPromotionGate(candidate, selectedResources, urlVerifications);
    if (gate.status === "blocked") {
      return { status: "blocked", evidence_ref: null, blockers: gate.blockers, warnings: gate.warnings };
    }

    var kindMap = { paper: "paper", dataset: "dataset", repo: "repo" };
    var evType = kindMap[(candidate.props && candidate.props.kind) || "paper"] || "note";
    var evId = "ev_" + candidate.id;
    var title = (candidate.props && candidate.props.title) || "Evidence from " + candidate.id;
    var url = (candidate.props && candidate.props.url) || "";
    var urlVerified = urlVerifications && urlVerifications[candidate.id] && urlVerifications[candidate.id].status === "verified";

    return {
      status: "promoted",
      evidence_ref: {
        evidence_id: evId,
        evidence_type: evType,
        title: title,
        role: "supports",
        reason: reason || "Promoted from candidate",
        review_status: "pending",
        url: url,
        url_verified: urlVerified,
        candidate_id: candidate.id,
      },
      blockers: [],
      warnings: gate.warnings,
    };
  }

  // ---------- URL Verification Status UI ---------- //

  function urlStatusBadge(status) {
    var map = {
      unchecked: '<span class="pa-tag pa-tag--unchecked">⏳ 未验证</span>',
      verified: '<span class="pa-tag pa-tag--ok">✅ 已验证</span>',
      partial: '<span class="pa-tag pa-tag--partial">⚠️ 部分验证</span>',
      failed: '<span class="pa-tag pa-tag--fail">❌ 验证失败</span>',
      expired: '<span class="pa-tag pa-tag--fail">⏰ 已过期</span>',
    };
    return map[status] || map.unchecked;
  }

  // ---------- Render Promotion UI ---------- //

  function renderPromotionButton(candidate, selectedResources, urlVerifications) {
    var gate = checkPromotionGate(candidate, selectedResources, urlVerifications);
    var isBlocked = gate.status === "blocked";
    var isSelected = selectedResources && selectedResources.some(function (s) { return s.candidateId === candidate.id; });
    var urlStatus = "unchecked";
    if (isSelected) {
      var sel = selectedResources.find(function (s) { return s.candidateId === candidate.id; });
      urlStatus = (sel && sel.verificationStatus) || "unchecked";
    }
    if (urlVerifications && urlVerifications[candidate.id]) {
      urlStatus = urlVerifications[candidate.id].status || urlStatus;
    }

    var html = '<div class="promo-actions">';
    html += urlStatusBadge(urlStatus);
    if (isBlocked) {
      html += '<button class="cta-mini" disabled title="' + esc(gate.blockers.join("; ")) + '">🔒 晋升为证据</button>';
      html += '<div class="promo-blockers">' + gate.blockers.map(function (b) {
        return '<span class="promo-blocker-msg">⛔ ' + esc(b) + '</span>';
      }).join("") + '</div>';
    } else {
      html += '<button class="cta-mini cta-mini--promote" data-action="promote_to_evidence" data-candidate-id="' + esc(candidate.id) + '">⬆️ 晋升为证据</button>';
      if (gate.warnings.length) {
        html += gate.warnings.map(function (w) {
          return '<span class="promo-warning-msg">⚠️ ' + esc(w) + '</span>';
        }).join("");
      }
    }
    html += '</div>';
    return html;
  }

  // ---------- Public API ---------- //

  function isReady() {
    return true;
  }

  global.EvidencePromotion = {
    checkPromotionGate: checkPromotionGate,
    promoteToEvidence: promoteToEvidence,
    urlStatusBadge: urlStatusBadge,
    renderPromotionButton: renderPromotionButton,
    isReady: isReady,
  };
})(window);
