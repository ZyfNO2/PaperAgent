"""Smoke test: chain nodes one by one with timing."""
import sys, time, os, json, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
logging.basicConfig(level=logging.INFO, format="%(name)s:%(lineno)d %(levelname)s: %(message)s")

from apps.api.app.services.agents.graph.nodes.intake import intake_node
from apps.api.app.services.agents.graph.nodes.topic_parser import topic_parser_node
from apps.api.app.services.agents.graph.nodes.search_planner import search_planner_node
from apps.api.app.services.agents.graph.nodes.search_agent import search_agent_node


def test_chain():
    topic = "Using deep learning for steel surface defect detection"
    state: dict = {"topic": topic, "mode": "quick"}

    t0 = time.time()
    result = intake_node(state)
    state.update(result)
    t1 = time.time()
    print(f"[1] intake: {t1-t0:.1f}s")
    print(f"    search_queries={state.get('search_queries','N/A')}")

    result = topic_parser_node(state)
    state.update(result)
    t2 = time.time()
    atoms = state.get('topic_atoms', {})
    print(f"[2] topic_parser: {t2-t1:.1f}s")
    print(f"    atoms: method={atoms.get('method','N/A')}, object={atoms.get('object','N/A')}")
    print(f"    domain={atoms.get('domain','N/A')}, task={atoms.get('task','N/A')}")

    result = search_planner_node(state)
    state.update(result)
    t3 = time.time()
    plan = state.get('search_plan', {})
    pq = plan.get('queries', [])
    print(f"[3] search_planner: {t3-t2:.1f}s")
    print(f"    plan_queries={len(pq)}, rounds={plan.get('rounds','N/A')}")
    if pq:
        for q in pq[:3]:
            print(f"      - [{q.get('tool','?')}] {q.get('query','?')[:80]}")

    result = search_agent_node(state)
    state.update(result)
    t4 = time.time()
    print(f"[4] search_agent: {t4-t3:.1f}s")
    papers = state.get('paper_candidates', [])
    repos = state.get('repo_candidates', [])
    raw = state.get('raw_results', {})
    steps = state.get('search_steps', [])
    print(f"    paper_candidates={len(papers)}, repo_candidates={len(repos)}, raw_sources={list(raw.keys())}")
    for s in steps:
        print(f"    step[{s.get('step','?')}]: {s.get('type','?')} tool={s.get('tool','?')} n_results={s.get('n_results','?')} n_papers={s.get('n_papers','?')}")
    if papers:
        for p in papers[:3]:
            print(f"      - {p.get('title','?')[:80]}")

    print(f"\nTotal: {t4-t0:.1f}s")


if __name__ == "__main__":
    test_chain()