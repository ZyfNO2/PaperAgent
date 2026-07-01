// Session 27: Stream Client — NDJSON + SSE 消费 + 回放 (SOP §8-9)
//
// 公开 API:
//   StreamClient.createRun(projectId, opts)
//   StreamClient.consumeNDJSON(runId, opts)
//   StreamClient.consumeSSE(runId, opts)
//   StreamClient.replayRun(runId, opts)
//   StreamClient.resumeRun(runId, patch, opts)
//   StreamClient.isReady()

(function (global) {
  "use strict";

  var BASE_URL = "/api/v1";

  function _fetch(url, opts) {
    return fetch(url, opts).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + ": " + r.statusText);
      return r;
    });
  }

  function _postJSON(url, body) {
    return _fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json(); });
  }

  function _getJSON(url) {
    return _fetch(url).then(function (r) { return r.json(); });
  }

  // ---- Create Run ---- //

  function createRun(projectId, opts) {
    opts = opts || {};
    return _postJSON(BASE_URL + "/runs", {
      project_id: projectId,
      run_id: opts.runId || null,
      initial_step: opts.initialStep || null,
      mock_mode: opts.mockMode || false,
    });
  }

  // ---- Consume NDJSON ---- //

  function consumeNDJSON(runId, opts) {
    opts = opts || {};
    var onEvent = opts.onEvent || function () {};
    var onComplete = opts.onComplete || function () {};
    var onError = opts.onError || function () {};
    var url = BASE_URL + "/runs/" + runId + "/events?from_seq=" + (opts.fromSeq || 0);

    return _getJSON(url).then(function (data) {
      if (data && data.events) {
        data.events.forEach(function (evt) { onEvent(evt); });
      }
      onComplete(data);
      return data;
    }).catch(function (err) {
      onError(err);
      throw err;
    });
  }

  // ---- Consume SSE ---- //

  function consumeSSE(runId, opts) {
    opts = opts || {};
    var onEvent = opts.onEvent || function () {};
    var onComplete = opts.onComplete || function () {};
    var onError = opts.onError || function () {};
    var url = BASE_URL + "/runs/" + runId + "/stream";

    return new Promise(function (resolve, reject) {
      var source = new EventSource(url);
      var events = [];

      source.onmessage = function (e) {
        try {
          var evt = JSON.parse(e.data);
          events.push(evt);
          onEvent(evt);
        } catch (err) {
          // non-JSON message (e.g. done signal)
          if (e.data === "[DONE]") {
            source.close();
            onComplete(events);
            resolve(events);
          }
        }
      };

      source.onerror = function (err) {
        source.close();
        onError(err);
        // SSE 不可用时 fallback 到 NDJSON
        consumeNDJSON(runId, opts).then(resolve).catch(reject);
      };
    });
  }

  // ---- Replay Run ---- //

  function replayRun(runId, opts) {
    opts = opts || {};
    var fromSeq = opts.fromSeq || 0;
    var onEvent = opts.onEvent || function () {};

    return _getJSON(BASE_URL + "/runs/" + runId + "/events?from_seq=" + fromSeq).then(function (data) {
      if (data && data.events) {
        // 重放事件 — 按 seq 排序
        var sorted = data.events.slice().sort(function (a, b) { return a.seq - b.seq; });
        sorted.forEach(function (evt) { onEvent(evt); });
      }
      return data;
    });
  }

  // ---- Resume Run ---- //

  function resumeRun(runId, patch, opts) {
    opts = opts || {};
    var body = {
      from_seq: opts.fromSeq || 0,
      user_patch: patch || {},
      strategy: opts.strategy || "continue",
      skip_steps: opts.skipSteps || [],
    };

    return _postJSON(BASE_URL + "/runs/" + runId + "/resume", body).then(function (data) {
      if (opts.onResumed) opts.onResumed(data);
      return data;
    });
  }

  // ---- isReady ---- //

  function isReady() {
    return typeof fetch !== "undefined" && typeof EventSource !== "undefined";
  }

  // ---- Public API ---- //

  global.StreamClient = {
    createRun: createRun,
    consumeNDJSON: consumeNDJSON,
    consumeSSE: consumeSSE,
    replayRun: replayRun,
    resumeRun: resumeRun,
    isReady: isReady,
  };
})(window);
