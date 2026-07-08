"""Extract Re3.0 batch20 case results into a single Markdown report (with Chinese translations)."""
import json
import os
import glob
import sys

# Add translations module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translations import TRANSLATIONS

BASE = r'g:\PaperAgent\tmp_re30_eval\batch20'
GT_PATH = r'g:\PaperAgent\tmp_re30_eval\ground_truth\verified_ground_truth.json'
OUT = r'g:\PaperAgent\Plan\PaperAgent_Re3.0_Batch20_成功结果与标答.md'


def shorten(s, n=200):
    if not s:
        return ''
    s = str(s).replace('\n', ' ').strip()
    return s[:n] + ('...' if len(s) > n else '')


def fmt_authors(authors):
    if not authors:
        return ''
    if isinstance(authors, str):
        return authors
    names = []
    for a in authors[:3]:
        if isinstance(a, dict):
            n = a.get('name') or a.get('full_name') or a.get('display_name') or ''
        else:
            n = str(a)
        if n:
            names.append(n)
    out = ', '.join(names)
    if isinstance(authors, list) and len(authors) > 3:
        out += ' et al.'
    return out


def fmt_paper(p, full=True, case_id=None, idx=None, ptype='verified'):
    if not isinstance(p, dict):
        return f'- {p}'
    title = p.get('title') or p.get('name') or '(untitled)'
    title = title.strip().replace('\n', ' ')
    year = p.get('year') or p.get('published_year') or ''
    venue = p.get('venue') or p.get('journal') or p.get('source') or ''
    authors = fmt_authors(p.get('authors') or p.get('author_list'))
    doi = p.get('doi') or ''
    url = p.get('url') or p.get('link') or p.get('arxiv_url') or doi
    abstract = p.get('abstract') or p.get('summary') or ''
    score = p.get('score') or p.get('relevance_score') or ''

    line = f'- **{title}**'
    meta = []
    if authors:
        meta.append(authors)
    if year:
        meta.append(str(year))
    if venue:
        meta.append(str(venue))
    if meta:
        line += ' — ' + ' | '.join(meta)

    # Chinese translation
    if case_id is not None and idx is not None:
        key = (case_id, f'{ptype}_title', idx)
        tr = TRANSLATIONS.get(key)
        if tr:
            line += f'\n  - **中文译名**: {tr}'

    if url:
        line += f'\n  - URL: {url}'
    elif doi:
        line += f'\n  - DOI: {doi}'
    if full and abstract:
        line += f'\n  - Abstract: {shorten(abstract, 200)}'
        # Abstract translation
        if case_id is not None and idx is not None:
            key = (case_id, f'{ptype}_abstract', idx)
            tr_abs = TRANSLATIONS.get(key)
            if tr_abs:
                line += f'\n  - **摘要译文**: {shorten(tr_abs, 300)}'
    if score != '':
        line += f'\n  - 相关性分数: {score}'
    return line


def fmt_repo(r):
    if not isinstance(r, dict):
        return f'- {r}'
    name = r.get('name') or r.get('full_name') or r.get('repo') or ''
    url = r.get('url') or r.get('html_url') or r.get('link') or ''
    # Fallback: derive name from URL
    if not name and url:
        name = url.rstrip('/').split('/')[-1]
    if not name:
        name = '(unnamed)'
    stars = r.get('stars') or r.get('stargazers_count') or ''
    desc = r.get('description') or r.get('desc') or ''
    line = f'- **{name}**'
    if stars != '':
        line += f' (★ {stars})'
    if url:
        line += f'\n  - URL: {url}'
    if desc:
        line += f'\n  - 描述: {shorten(desc, 150)}'
    return line


def fmt_dataset(d):
    if not isinstance(d, dict):
        return f'- {d}'
    name = d.get('name') or d.get('title') or str(d)
    url = d.get('url') or d.get('link') or ''
    desc = d.get('description') or ''
    line = f'- **{name}**'
    if url:
        line += f' — {url}'
    if desc:
        line += f'\n  - {shorten(desc, 120)}'
    return line


def fmt_innovation(inv):
    if isinstance(inv, dict):
        name = inv.get('name') or inv.get('title') or ''
        desc = inv.get('description') or inv.get('desc') or inv.get('detail') or ''
        line = f'- **{name}**' if name else '- '
        if desc:
            line += f': {shorten(desc, 250)}'
        return line
    return f'- {shorten(inv, 250)}'


def extract_case(state_path):
    with open(state_path, 'r', encoding='utf-8') as f:
        s = json.load(f)

    case_id = s.get('case_id', os.path.basename(os.path.dirname(state_path)))
    topic = s.get('topic', '')

    out = []
    out.append(f'## {case_id} — {topic}')
    out.append('')

    # Feasibility
    fr = s.get('feasibility_report') or {}
    verdict = fr.get('verdict', '')
    score = fr.get('score', '')
    reason = fr.get('reason', '')
    out.append(f'- **可行性裁决**: `{verdict}` (分数: {score})')
    if reason:
        out.append(f'- **可行性理由**: {shorten(reason, 300)}')

    # Review
    rr = s.get('review_report') or {}
    ov = rr.get('overall_verdict', '')
    if ov:
        out.append(f'- **复核裁决**: `{ov}`')

    # Verified papers
    vp = s.get('verified_papers') or []
    out.append('')
    out.append(f'### Verified Papers ({len(vp)} 篇)')
    if vp:
        for i, p in enumerate(vp):
            out.append(fmt_paper(p, full=True, case_id=case_id, idx=i, ptype='verified'))
    else:
        out.append('（无）')

    # Weak papers
    wp = s.get('weak_papers') or []
    out.append('')
    out.append(f'### Weak Papers ({len(wp)} 篇)')
    if wp:
        for i, p in enumerate(wp[:10]):
            out.append(fmt_paper(p, full=False, case_id=case_id, idx=i, ptype='weak'))
        if len(wp) > 10:
            out.append(f'- ... 等共 {len(wp)} 篇')
    else:
        out.append('（无）')

    # Repos
    rp = s.get('repo_candidates') or s.get('repos_found') or []
    out.append('')
    out.append(f'### Repos ({len(rp)} 个)')
    if rp:
        for r in rp:
            out.append(fmt_repo(r))
    else:
        out.append('（无）')

    # Datasets
    ds = s.get('dataset_candidates') or s.get('dataset_papers') or []
    out.append('')
    out.append(f'### Datasets ({len(ds)} 个)')
    if ds:
        for d in ds:
            out.append(fmt_dataset(d))
    else:
        out.append('（无）')

    # Baselines
    bl = s.get('baseline_candidates') or []
    out.append('')
    out.append(f'### Baselines ({len(bl)} 个)')
    if bl:
        for b in bl:
            if isinstance(b, dict):
                t = b.get('title') or b.get('name') or str(b)
                out.append(f'- {t}')
            else:
                out.append(f'- {b}')
    else:
        out.append('（无）')

    # Innovation points
    ip = s.get('innovation_points') or []
    out.append('')
    out.append(f'### Innovation Points ({len(ip)} 个)')
    if ip:
        for inv in ip:
            out.append(fmt_innovation(inv))
    else:
        out.append('（无）')

    # Stitching plan
    sp = s.get('stitching_plan') or {}
    if sp:
        out.append('')
        out.append('### Stitching Plan (缝合方案)')
        bm = sp.get('baseline_model', '')
        mb = sp.get('module_b', '')
        mc = sp.get('module_c', '')
        if bm:
            out.append(f'- **Baseline**: {shorten(bm, 150)}')
        if mb:
            out.append(f'- **Module B**: {shorten(mb, 150)}')
        if mc:
            out.append(f'- **Module C**: {shorten(mc, 150)}')

    # Narrative
    rn = s.get('research_narrative') or s.get('research_narrative') or {}
    if isinstance(rn, dict) and rn:
        out.append('')
        out.append('### Research Narrative (研究叙事)')
        np_ = rn.get('nick_model_name', '')
        sm = rn.get('narrative_summary', '')
        if np_:
            out.append(f'- **Nick Model**: {shorten(np_, 100)}')
        if sm:
            out.append(f'- **叙事摘要**: {shorten(sm, 400)}')

    return '\n'.join(out)


def load_ground_truth():
    with open(GT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def fmt_gt(gt):
    out = []
    out.append('## 标答 (Verified Ground Truth)')
    out.append('')
    out.append('> 来源: `tmp_re30_eval/ground_truth/verified_ground_truth.json`')
    out.append('')
    # Ground truth baselines Chinese translations
    gt_baseline_translations = {
        'Deep Learning (LeCun 2015, Nature 521:436)': '深度学习 (LeCun 2015, Nature 521:436)',
        'Deep Residual Learning for Image Recognition (He 2015, arxiv:1512.03385)': '用于图像识别的深度残差学习 (He 2015, arxiv:1512.03385)',
        'You Only Look Once: Unified Real-Time Object Detection (Redmon 2015, arxiv:1506.02640)': 'You Only Look Once：统一的实时目标检测 (Redmon 2015, arxiv:1506.02640)',
        'You Only Look Once (Redmon 2015, arxiv:1506.02640)': 'You Only Look Once (Redmon 2015, arxiv:1506.02640)',
        'ORB-SLAM: A Versatile and Accurate Monocular SLAM System (Mur-Artal 2015, arxiv:1502.00956)': 'ORB-SLAM：通用且精确的单目SLAM系统 (Mur-Artal 2015, arxiv:1502.00956)',
        'ORB-SLAM2: An Open-Source SLAM System for Monocular, Stereo and RGB-D Cameras (Mur-Artal 2017, arxiv:1610.06475)': 'ORB-SLAM2：面向单目、双目和RGB-D相机的开源SLAM系统 (Mur-Artal 2017, arxiv:1610.06475)',
        'LSD-SLAM: Large-Scale Direct Monocular SLAM (Engel 2014, ECCV)': 'LSD-SLAM：大规模直接单目SLAM (Engel 2014, ECCV)',
        'U-Net: Convolutional Networks for Biomedical Image Segmentation (Ronneberger 2015, arxiv:1505.04597)': 'U-Net：用于生物医学图像分割的卷积网络 (Ronneberger 2015, arxiv:1505.04597)',
        'Using Deep Learning for Image-Based Plant Disease Detection (Mohanty 2016, Front. Plant Sci. 7:1419)': '使用深度学习进行基于图像的植物病害检测 (Mohanty 2016, Front. Plant Sci. 7:1419)',
    }
    for g in gt:
        domain = g.get('domain', '')
        cases = g.get('cases', [])
        keywords = g.get('keywords', [])
        baselines = g.get('baselines', [])
        datasets = g.get('datasets', [])
        repos = g.get('repos', [])
        feas = g.get('feasibility', '')
        notes = g.get('notes', '')
        out.append(f'### {domain}')
        out.append(f'- **Cases**: {", ".join(cases)}')
        out.append(f'- **Keywords**: {", ".join(keywords)}')
        out.append(f'- **Feasibility**: `{feas}`')
        if baselines:
            out.append('- **Baselines**:')
            for b in baselines:
                tr = gt_baseline_translations.get(b)
                if tr:
                    out.append(f'  - {b}')
                    out.append(f'    - 译文: {tr}')
                else:
                    out.append(f'  - {b}')
        if datasets:
            out.append(f'- **Datasets**: {", ".join(datasets)}')
        if repos:
            out.append(f'- **Repos**: {", ".join(repos)}')
        if notes:
            out.append(f'- **Notes**: {notes}')
        out.append('')
    return '\n'.join(out)


def main():
    cases = sorted(glob.glob(os.path.join(BASE, 'ENG-THESIS-*', 'state.json')))

    header = []
    header.append('# PaperAgent Re3.0 — Batch20 成功结果与标答汇总')
    header.append('')
    header.append('> 本文档汇总 Re3.0 Batch20 测试中各 case 的最终结果（论文/Repo/Dataset/Baselines/创新点/缝合方案/研究叙事）以及对应的标答（Ground Truth）。')
    header.append('')
    header.append(f'- **数据来源**: `tmp_re30_eval/batch20/ENG-THESIS-*/state.json`')
    header.append(f'- **标答来源**: `tmp_re30_eval/ground_truth/verified_ground_truth.json`')
    header.append(f'- **case 总数**: {len(cases)}')
    header.append('')
    header.append('## 总览')
    header.append('')
    header.append('| Case ID | 题目 | 论文数 | Repo 数 | Dataset 数 | 可行性 | 复核裁决 |')
    header.append('|---|---|---|---|---|---|---|')

    summary_rows = []
    for sp in cases:
        with open(sp, 'r', encoding='utf-8') as f:
            s = json.load(f)
        cid = s.get('case_id', os.path.basename(os.path.dirname(sp)))
        topic = s.get('topic', '')
        np_ = len(s.get('verified_papers') or [])
        nr = len(s.get('repo_candidates') or s.get('repos_found') or [])
        nd = len(s.get('dataset_candidates') or s.get('dataset_papers') or [])
        fr = s.get('feasibility_report') or {}
        verdict = fr.get('verdict', '')
        rr = s.get('review_report') or {}
        ov = rr.get('overall_verdict', '')
        summary_rows.append(f'| {cid} | {topic} | {np_} | {nr} | {nd} | {verdict} | {ov} |')

    header.extend(summary_rows)
    header.append('')
    header.append('---')
    header.append('')

    body = [extract_case(sp) for sp in cases]

    gt = load_ground_truth()
    gt_md = fmt_gt(gt)

    full = '\n'.join(header) + '\n' + '\n\n'.join(body) + '\n\n---\n\n' + gt_md + '\n'

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(full)

    print(f'Written: {OUT}')
    print(f'Size: {os.path.getsize(OUT)} bytes')
    print(f'Lines: {full.count(chr(10)) + 1}')


if __name__ == '__main__':
    main()
