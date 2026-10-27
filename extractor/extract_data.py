# -*- coding: utf-8 -*-
r"""
考研复习 App 数据提取器
读取 D:\university_learning\考研 下的笔记，生成 www/data 与 site\appdata 所需的 JSON。

输出（data/ 目录）：
  words.json      英语 800 词（按词频降序）
  politics.json   政治背诵手册 28 天日程 + 原理条目 + 自测清单
  quiz.json       四科客观题错题库（选择题）
  cards.json      全仓「高频考点速记」表 → 翻面卡片
  selfcheck.json  四份「复习自查」：勾选清单 + 问答 + 易错点
  notes.json      笔记全文 bundle {path: content}
  manifest.json   目录树（优先复用 site\manifest.json 的文件清单，保证与站点一致）
  search.json     全文搜索语料（合并 site\search\*.json）
  appdata/index.json  在线刷新索引（版本 + 各文件 sha256）

自检报告：data/_report.txt
用法：python extract_data.py
"""
import hashlib
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(r"D:\university_learning\考研")
SITE = Path(r"D:\university_learning\site")
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DATA.mkdir(parents=True, exist_ok=True)

SUBJECTS = ["408", "数学", "英语", "政治"]
EXCLUDE_KEYS = ["参考", "校对报告", "课件", "合订版", "AGENTS", "试卷"]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_json(name: str, obj, indent=None) -> Path:
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8", newline="\n")
    return p


# ---------------------------------------------------------------- words
def parse_words():
    """英语单词表：| 序号 | 单词 | 音标 | 词性 | 文中释义 | 词频 | 选项次数 |"""
    src = read(ROOT / "英语" / "单词" / "单词.md")
    words = []
    for line in src.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 7 or "<nobr>" in cells[0] or not cells[0].isdigit():
            continue
        meaning = "|".join(cells[4:5]) if len(cells) == 7 else "|".join(cells[4:-2])
        try:
            words.append({
                "id": int(cells[0]),
                "word": cells[1],
                "phonetic": cells[2],
                "pos": cells[3],
                "meaning": meaning,
                "freq": int(cells[-2]),
                "opt": int(cells[-1]),
            })
        except ValueError:
            continue
    words.sort(key=lambda w: -w["freq"])
    for i, w in enumerate(words):
        w["sid"] = f"w{i+1}"  # 稳定 id（按词频序）
    return words


# ---------------------------------------------------------------- politics
def parse_politics():
    folder = ROOT / "政治" / "背诵手册"

    # 1) 总览表 → 28 天日程
    overview = read(folder / "00 背诵总览.md")
    days = []
    row_re = re.compile(
        r"^\|\s*第(\d+)天\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(第[一二]遍)\s*\|\s*(P[\d\-]+)\s*\|\s*(.+?)\s*\|\s*☐\s*\|")
    for line in overview.splitlines():
        m = row_re.match(line.strip())
        if m:
            days.append({
                "day": int(m.group(1)), "date": m.group(2),
                "round": 1 if m.group(3) == "第一遍" else 2,
                "pages": m.group(4), "summary": m.group(5).strip(),
            })
    days.sort(key=lambda d: d["day"])

    # 2) 逐日文件
    for d in days:
        pattern = f"{d['date']} 第{d['day']}天*.md"
        files = sorted(folder.glob(pattern))
        if not files:
            d.update({"file": "", "checkItems": [], "principles": [], "reviewGroups": []})
            continue
        text = read(files[0])
        d["file"] = files[0].name
        d.update(parse_politics_day(text, d["round"]))
    return {"start": days[0]["date"] if days else "", "days": days}


def parse_politics_day(text: str, rnd: int):
    out = {"checkItems": [], "principles": [], "reviewGroups": []}
    lines = text.splitlines()

    # 打卡项：> **打卡**：☐ 通读　☐ 复述　☐ 默写关键词
    for line in lines:
        m = re.match(r"^>\s*\*\*打卡\*\*[：:](.+)$", line.strip())
        if m:
            out["checkItems"] = [x.strip() for x in m.group(1).split("☐") if x.strip()]

    if rnd == 2:
        # 二遍：对应第一遍笔记表 + 今日自查清单（**第 N 天**（P页） 分组）
        in_check = False
        cur_group = None
        for line in lines:
            s = line.strip()
            if s.startswith("### 今日自查清单"):
                in_check = True
                continue
            if in_check:
                if s.startswith("### ") or s.startswith("> **导航**"):
                    break
                g = re.match(r"^\*\*第\s*(\d+)\s*天\*\*", s)
                if g:
                    cur_group = {"day": int(g.group(1)), "items": []}
                    out["reviewGroups"].append(cur_group)
                    continue
                c = re.match(r"^-\s*\[ \]\s*(.+)$", s)
                if c and cur_group is not None:
                    cur_group["items"].append(c.group(1).strip())
        return out

    # 一遍：### 第X部分《…》 / #### 一、… / **N.条目名** / **原理内容**： 等字段
    FIELD = re.compile(r"^\*\*(\S{2,8})\*\*[：:]\s*(.*)$")
    KNOWN = {"原理名字": "alias", "原理内容": "content", "方法论": "method",
             "具体运用": "usage", "意义": "usage", "总结": "usage", "地位": "alias"}
    ITEM = re.compile(r"^\*\*(\d+)[.、]\s*(.+?)\*\*$")
    PART = re.compile(r"^###\s+第.+?部分《(.+?)》")
    SECT = re.compile(r"^####\s+(.+)$")

    part = sect = ""
    item = None
    field = None

    def flush():
        if item is not None and item.get("name"):
            item["extra"] = [{"label": e[0], "text": e[1]} for e in item.get("_extra_raw", [])]
            if "_extra_raw" in item:
                del item["_extra_raw"]
            item.setdefault("tips", [])
            out["principles"].append(item)

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("### 今日自测") or s.startswith("> **导航**"):
            flush()
            item = None
            continue
        mp, ms, mi = PART.match(s), SECT.match(s), ITEM.match(s)
        if mp:
            flush(); item = None; part = mp.group(1); sect = ""; field = None
            continue
        if ms:
            flush(); item = None; sect = ms.group(1); field = None
            continue
        if mi:
            flush()
            item = {"num": int(mi.group(1)), "name": mi.group(2).strip(),
                    "part": part, "section": sect, "alias": "", "content": "", "method": "", "usage": ""}
            field = None
            continue
        if item is not None:
            mf = FIELD.match(s)
            if mf:
                label = mf.group(1)
                val = mf.group(2).strip()
                if label in KNOWN:
                    field = label
                    _assign(item, label, val)
                else:
                    field = None
                    item.setdefault("_extra_raw", []).append((label, val))
                continue
            if s.startswith("- [ ]") or s.startswith("|") or s.startswith("```"):
                continue  # 自测/表格/代码块不入原理正文
            mt = re.match(r"^>\s*【(.+?)】\s*(.*)$", s)
            if mt:
                # 【记忆关键词】【温馨提示】等原文提示块
                tip = mt.group(1) + ("：" + mt.group(2) if mt.group(2) else "")
                item.setdefault("tips", []).append(tip)
                continue
            if s.startswith(">"):
                continue  # 其余引用块（导航等）
            if s.startswith("---"):
                flush(); item = None
                continue
            if field:
                _assign(item, field, s, append=True)
            elif item.get("_extra_raw"):
                lab, txt = item["_extra_raw"][-1]
                item["_extra_raw"][-1] = (lab, txt + "\n" + s)
            else:
                # 无字段标签的纯段落（毛中特/史纲/思修等部分的正文）
                item["content"] = (item["content"] + "\n" + s) if item["content"] else s
    flush()

    # 今日自测条目（用于自测清单兜底；checkItems 已含通读/复述/默写）
    return out


def _assign(item, field, val, append=False):
    key = {"原理名字": "alias", "原理内容": "content", "方法论": "method",
           "具体运用": "usage", "意义": "usage", "总结": "usage", "地位": "alias"}[field]
    if append and item.get(key):
        item[key] += "\n" + val
    elif append:
        item[key] = val
    else:
        item[key] = item[key] + ("\n" + val if item.get(key) else val) if item.get(key) else val


# ---------------------------------------------------------------- quiz
QUIZ_FILES = [
    ("操作系统", ROOT / "408" / "操作系统" / "客观题知识漏洞.md"),
    ("计算机组成原理", ROOT / "408" / "计算机组成原理" / "客观题知识漏洞.md"),
    ("计算机网络", ROOT / "408" / "计算机网络" / "客观题知识漏洞.md"),
    ("数据结构", ROOT / "408" / "数据结构" / "客观题知识漏洞.md"),
]
OPT_RE = re.compile(r"^([A-D])[.．、]\s*")
ANS_RE = re.compile(r"^答案[：:]\s*\*\*(.+?)\*\*")
ENTRY_RE = re.compile(r"^\*\*([①②③④⑤⑥⑦⑧⑨⑩⑪⑫]+)\s*(.+?)\*\*\s*(（.+）)?$")
FREE_Q_RE = re.compile(r"^>\s*\*\*原题（综合应用题\s*(\d+)）\*\*[：:]\s*(.+)$")
SHORT_A_RE = re.compile(r"\*\*答（一句话版）\*\*[：:]\s*(.+)$")


def parse_freeform(lines):
    """综合应用题：题干在引用块，答案取其所属条目的「答（一句话版）」，细则取条目 bullets。"""
    free = []
    entries = []
    cur = None
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        mq = FREE_Q_RE.match(s)
        if mq:
            free.append({"num": int(mq.group(1)), "stem": mq.group(2).strip(),
                         "answer": "", "detail": []})
            continue
        me = ENTRY_RE.match(s)
        if me:
            title = (me.group(1) + " " + me.group(2)).strip()
            m = re.search(r"综合应用题\s*(\d+)", title)
            cur = {"num": int(m.group(1)), "title": title, "answer": "", "bullets": []} if m else None
            entries.append(cur)
            continue
        if cur is not None:
            ma = SHORT_A_RE.search(s)
            if ma:
                cur["answer"] = ma.group(1).strip()
            elif s.startswith("- "):
                cur["bullets"].append(s[2:].strip())
    for q in free:
        e = next((x for x in entries if x and x["num"] == q["num"]), None)
        if e:
            q["answer"] = e["answer"] or "、".join(e["bullets"][:2])
            q["detail"] = e["bullets"]
    return free


def parse_quiz():
    result = []
    for subject, path in QUIZ_FILES:
        text = read(path)
        # 切小节
        sections = re.split(r"^###\s+", text, flags=re.M)
        for sec in sections[1:]:
            sec_lines = sec.splitlines()
            sec_title = sec_lines[0].strip()
            if not sec_title or sec_title.startswith("待整理"):
                continue
            body = sec_lines[1:]
            # 漏洞条目标题（非引用行里的 **① …**）
            entries = []
            for ln in body:
                if ln.startswith(">"):
                    continue
                me = ENTRY_RE.match(ln.strip())
                if me:
                    entries.append((me.group(1) + " " + me.group(2)).strip())
            questions = parse_quiz_block(body)
            freeform = parse_freeform(body)
            result.append({"subject": subject, "section": sec_title,
                           "entries": entries, "questions": questions,
                           "freeform": freeform})
    return result


def parse_quiz_block(lines):
    """从行列表中解析 `> **原题 N**：…` 引用块里的选择题。"""
    questions = []
    cur = None          # 当前题
    mode = None         # None=题干 | 'opt' | done
    last_opt = None

    def finish():
        nonlocal cur, mode, last_opt
        if cur and cur["stem"] and len(cur["options"]) >= 2 and cur["answer"]:
            cur["options"] = {k: v for k, v in cur["options"].items() if v}
            questions.append(cur)
        cur, mode, last_opt = None, None, None

    for raw in lines:
        if not raw.startswith(">"):
            if cur is not None:
                finish()
            continue
        s = re.sub(r"^>\s?", "", raw).strip()
        if not s:
            continue
        mq = re.match(r"^\*\*原题\s*(\d+)\*\*[：:]\s*(.*)$", s)
        if mq:
            finish()
            cur = {"num": int(mq.group(1)),
                   "stem": mq.group(2).strip(), "options": {}, "answer": ""}
            mode = "stem"
            continue
        if cur is None:
            continue
        ma = ANS_RE.match(s)
        if ma:
            raw = ma.group(1).strip()
            letters = re.findall(r"[A-D]", raw)
            if letters:
                cur["answer"] = raw
                cur["key"] = letters[0] if len(letters) == 1 else "".join(letters)
                cur["mode"] = "single" if len(letters) == 1 else "multi"
                finish()
            continue
        mo = OPT_RE.match(s)
        if mo:
            mode = "opt"
            letter = mo.group(1)
            rest = s[mo.end():]
            # 行内连排选项：A. xxx　B. yyy　C. zzz（首段属于行首字母）
            parts = re.split(r"(?=[A-D][.．、])", rest)
            for p in parts:
                ps = p.strip()
                if not ps:
                    continue
                pm = OPT_RE.match(ps)
                if pm:
                    letter = pm.group(1)
                    cur["options"][letter] = ps[pm.end():].strip()
                    last_opt = letter
                else:
                    target = last_opt or letter
                    cur["options"][target] = (cur["options"].get(target, "") + ps).strip()
            continue
        # 普通行：题干延续 / 选项延续 / I/II/III 陈述
        if mode == "opt" and last_opt:
            cur["options"][last_opt] += s
        elif mode == "stem":
            cur["stem"] += "\n" + s
    finish()
    return questions


# ---------------------------------------------------------------- cards（速记表）
CARD_ANCHOR = "**高频考点速记**"


def strip_tags(s: str) -> str:
    return re.sub(r"</?(nobr|b)>", "", s).strip()


def parse_cards():
    result = []
    for md in walk_notes():
        text = read(md)
        if CARD_ANCHOR not in text:
            continue
        rel = md.relative_to(ROOT).as_posix()
        subject = rel.split("/")[0]
        chapter = md.stem
        cards = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            if CARD_ANCHOR in lines[i]:
                # 向后找最近一张表
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("|"):
                    j += 1
                # 表头 + 分隔行
                j += 2
                while j < len(lines):
                    s = lines[j].strip()
                    if not s.startswith("|"):
                        break
                    cells = [c.strip() for c in s.strip("|").split("|")]
                    if len(cells) >= 2 and set(cells[0]) - set(":- ") != set():
                        front = strip_tags(cells[0])
                        back = strip_tags("|".join(cells[1:]))
                        if front and back:
                            cards.append({"front": front, "back": back})
                    j += 1
                i = j
            else:
                i += 1
        if cards:
            result.append({"subject": subject, "chapter": chapter, "file": rel, "cards": cards})
    return result


# ---------------------------------------------------------------- selfcheck
SELFCHECK_FILES = [
    ("数学", "高数", ROOT / "数学" / "高数" / "复习自查.md"),
    ("数学", "线性代数", ROOT / "数学" / "线性代数" / "复习自查.md"),
    ("数学", "概率与统计", ROOT / "数学" / "概率与统计" / "复习自查.md"),
    ("408", "操作系统", ROOT / "408" / "操作系统" / "复习自查.md"),
]


def parse_selfcheck():
    result = []
    for group, name, path in SELFCHECK_FILES:
        if not path.exists():
            continue
        text = read(path)
        chapters = re.split(r"^##\s+", text, flags=re.M)[1:]
        chs = []
        for ch in chapters:
            ch_lines = ch.splitlines()
            title = ch_lines[0].strip()
            body = "\n".join(ch_lines[1:])
            items = [m.strip() for m in re.findall(r"^-\s*\[ \]\s*(.+)$", body, flags=re.M)]
            pitfalls = []
            in_pit = False
            for ln in body.splitlines():
                if re.match(r"^###.*易错点", ln):
                    in_pit = True
                    continue
                if ln.startswith("###"):
                    in_pit = False
                    continue
                if in_pit and ln.startswith("- "):
                    pitfalls.append(ln[2:].strip())
            qas = []
            for qm in re.finditer(r"^\*\*Q(\d+)\.\s*(.+?)\*\*\s*$", body, flags=re.M | re.S):
                # 题干行与 <details> 之间可能隔数据行（如银行家算法的资源表），一并入题干
                dm = re.match(r"\s*(.*?)\s*<details><summary>.+?</summary>(.*?)</details>",
                              body[qm.end():], flags=re.S)
                if dm:
                    stem_extra = dm.group(1).strip()
                    q = qm.group(2).strip()
                    if stem_extra:
                        q += "\n\n" + stem_extra
                    qas.append({"num": int(qm.group(1)), "q": q,
                                "a": re.sub(r"\n{3,}", "\n\n", dm.group(2).strip())})
            chs.append({"chapter": title, "items": items, "pitfalls": pitfalls, "qas": qas})
        result.append({"group": group, "subject": name, "chapters": chs})
    return result


# ---------------------------------------------------------------- notes / manifest / search
def load_site_manifest():
    p = SITE / "manifest.json"
    if p.exists():
        try:
            return json.loads(read(p))
        except Exception:
            return None
    return None


def manifest_files(node, base=None, out=None):
    if out is None:
        out = []
    if node.get("path"):
        out.append(node["path"])
    for c in node.get("children", []):
        manifest_files(c, out=out)
    return out


def walk_notes():
    r"""按 sync.py 同口径收集笔记 md（优先用 site\manifest.json 的清单）。"""
    man = load_site_manifest()
    files = []
    if man:
        for subj in man.get("subjects", []):
            for p in manifest_files(subj):
                f = ROOT / p
                if f.exists():
                    files.append(f)
        return sorted(set(files))
    for subj in SUBJECTS:
        for f in (ROOT / subj).rglob("*.md"):
            rel = f.relative_to(ROOT).as_posix()
            if any(k in rel for k in EXCLUDE_KEYS):
                continue
            files.append(f)
    return sorted(files)


def parse_notes():
    files = walk_notes()
    notes = {}
    total = 0
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        notes[rel] = read(f)
        total += len(notes[rel])
    man = load_site_manifest()
    search = {"pages": []}
    for subj in SUBJECTS:
        p = SITE / "search" / f"{subj}.json"
        if p.exists():
            try:
                d = json.loads(read(p))
                for pg in d.get("pages", []):
                    pg["subject"] = subj
                    search["pages"].append(pg)
            except Exception:
                pass
    return notes, man, search, total


# ---------------------------------------------------------------- appdata index
def build_appdata_index(names):
    idx = {"version": date.today().isoformat(), "t": int(time.time() * 1000), "files": {}}
    for n in names:
        p = DATA / n
        if p.exists():
            idx["files"][n] = {
                "sha": hashlib.sha256(p.read_bytes()).hexdigest()[:12],
                "size": p.stat().st_size,
            }
    return idx


def sync_code():
    """把 www 的应用代码（js/*.js 除 boot.js + css/app.css）同步到 site\appdata\code\，
    生成 appdata\app_index.json（带 t 时间戳，供 App「检查更新」比对与覆盖）。"""
    www = HERE.parent / "www"
    targets = []
    for p in sorted((www / "js").glob("*.js")):
        if p.name == "boot.js":      # boot.js 是引导层本体，覆盖不生效，排除
            continue
        targets.append((p, "js/" + p.name))
    targets.append((www / "css" / "app.css", "css/app.css"))
    out = {"version": date.today().isoformat(), "t": int(time.time() * 1000), "files": {}}
    dest_root = SITE / "appdata" / "code"
    for p, rel in targets:
        if not p.exists():
            continue
        b = p.read_bytes()
        out["files"][rel] = hashlib.sha256(b).hexdigest()[:12]
        (dest_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest_root / rel).write_bytes(b)
    (SITE / "appdata" / "app_index.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return out


def mirror_to_site(names):
    dest = SITE / "appdata"
    dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        src = DATA / n
        if src.exists():
            (dest / n).write_bytes(src.read_bytes())


# ---------------------------------------------------------------- main
def main():
    report = []

    words = parse_words()
    write_json("words.json", {"words": words}, indent=1)
    report.append(f"[words] 词条 {len(words)}；词频范围 {words[0]['freq']}~{words[-1]['freq']}"
                  if words else "[words] 空！")
    bad = [w for w in words if not (w["word"] and w["meaning"] and w["freq"] > 0)]
    report.append(f"[words] 字段缺失 {len(bad)} 条" + (f"：{bad[:3]}" if bad else ""))

    pol = parse_politics()
    n_prin = sum(len(d.get("principles", [])) for d in pol["days"])
    n_chk = sum(len(d.get("checkItems", [])) for d in pol["days"])
    write_json("politics.json", pol, indent=1)
    report.append(f"[politics] 天数 {len(pol['days'])}（期望 28）；原理条目 {n_prin}；打卡项 {n_chk}")
    # 日期连续性
    ok_dates = True
    if pol["days"]:
        d0 = date.fromisoformat(pol["days"][0]["date"])
        for i, d in enumerate(pol["days"]):
            if date.fromisoformat(d["date"]) != d0 + timedelta(days=i):
                ok_dates = False
                report.append(f"[politics] 日期不连续：第{d['day']}天 {d['date']}")
    report.append(f"[politics] 日期连续性 {'OK' if ok_dates else 'FAIL'}")
    miss_file = [d["day"] for d in pol["days"] if not d.get("file")]
    if miss_file:
        report.append(f"[politics] 缺文件的天：{miss_file}")

    quiz = parse_quiz()
    nq = sum(len(s["questions"]) for s in quiz)
    nf = sum(len(s["freeform"]) for s in quiz)
    nsec = len(quiz)
    expect = {"操作系统": 119, "计算机组成原理": 108, "计算机网络": 67, "数据结构": 48}
    write_json("quiz.json", {"sections": quiz}, indent=1)
    report.append(f"[quiz] 小节 {nsec}；选择题 {nq}；综合应用题 {nf}（期望 329+13=342）")
    for sub, exp in expect.items():
        got = sum(len(s["questions"]) + len(s["freeform"]) for s in quiz if s["subject"] == sub)
        flag = "OK" if got == exp else f"≠{exp}!"
        report.append(f"[quiz] {sub}: {got} {flag}")
    noans = [f'{s["subject"]}/{s["section"]}/{q["num"]}' for s in quiz for q in s["freeform"] if not q["answer"]]
    if noans:
        report.append(f"[quiz] 综合题无答案 {len(noans)}：{noans[:4]}")

    cards = parse_cards()
    nc = sum(len(c["cards"]) for c in cards)
    write_json("cards.json", {"decks": cards}, indent=1)
    report.append(f"[cards] 文件 {len(cards)}（期望≈57）；卡片 {nc}")

    sc = parse_selfcheck()
    ni = sum(len(c["items"]) for s in sc for c in s["chapters"])
    nq2 = sum(len(c["qas"]) for s in sc for c in s["chapters"])
    npf = sum(len(c["pitfalls"]) for s in sc for c in s["chapters"])
    write_json("selfcheck.json", {"subjects": sc}, indent=1)
    report.append(f"[selfcheck] 科目 {len(sc)}；章 {sum(len(s['chapters']) for s in sc)}；"
                  f"勾选项 {ni}（期望≈500）；问答 {nq2}（期望≈138）；易错点 {npf}")

    notes, man, search, total = parse_notes()
    write_json("notes.json", notes)
    (DATA / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    write_json("search.json", search)
    report.append(f"[notes] 笔记 {len(notes)} 篇 / {total/1024/1024:.1f} MB；"
                  f"manifest {'复用站点' if man else '未找到!'}；搜索页 {len(search['pages'])}")

    names = ["words.json", "politics.json", "quiz.json", "cards.json",
             "selfcheck.json", "notes.json", "manifest.json", "search.json"]
    idx = build_appdata_index(names)
    write_json("appdata_index.json", idx, indent=1)
    mirror_to_site(names + ["appdata_index.json"])
    # 站点约定文件名 index.json（app 拉取 URL）
    (SITE / "appdata" / "index.json").write_bytes((DATA / "appdata_index.json").read_bytes())
    report.append(f"[appdata] 版本 {idx['version']}；文件 {len(idx['files'])} 已镜像 site\\appdata")

    cidx = sync_code()
    report.append(f"[code] 应用代码 {len(cidx['files'])} 个文件已同步 site\\appdata\\code（t={cidx['t']}）")

    rep = "\n".join(report)
    (DATA / "_report.txt").write_text(rep + "\n", encoding="utf-8", newline="\n")
    print(rep)


if __name__ == "__main__":
    main()
