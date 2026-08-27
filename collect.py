#!/usr/bin/env python3
"""풀스택(백엔드·프론트엔드·모바일·풀스택) 채용 공고 수집기 (스크린샷 금지, 데이터 추출).
원티드(검색 JSON API) + 사람인(검색 HTML) + 잡코리아(검색 HTML)에서
분야별 키워드로 검색해 경력(2~3년차)·지역(서울/수원/용인/성남/과천/광명) 필터 후
중복 제거·분야별 쿼터를 적용해 CLAUDE.md 템플릿의 다이제스트(digest.txt)를 만든다.

리멤버는 SPA + 비공개 API라 requests로 수집 불가(추후 보강).
사용: python collect.py          (digest.txt 저장 + 화면 출력)
      python collect.py --send   (수집 + 카카오 전송, 이미 보낸 공고는 제외, 하루 1회)
      python collect.py --send --force   (오늘 이미 보냈어도 재전송)
"""
import sys, os, json, requests, re, html as ihtml, datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}

# ---------- 조정 가능한 상수 ----------
TARGET_GG = ["수원", "용인", "성남", "과천", "광명"]   # 서울 + 경기 대상 시
SENIOR = ["시니어", "리드", "lead", "팀장", "매니저", "수석", "책임", "senior", "head", "cto", "tech lead", "principal", "staff"]
MAX_EXP_FLOOR = 4          # 요구 경력 하한이 이 값 이하면 통과
PER_CATEGORY = 3           # 분야별 최대 개수
TOTAL = 10                 # 전체 최대 개수
SENT_FILE = "sent.json"    # 이미 보낸 공고 기록 (링크 → 보낸 날짜). 워크플로가 커밋해서 유지
SENT_KEEP_DAYS = 45        # 이 기간 지난 기록은 정리 (공고 재게시 대비)
KST = datetime.timezone(datetime.timedelta(hours=9))


def today_kst():
    """GitHub 러너는 UTC라 '오늘'을 한국 기준으로 계산한다."""
    return datetime.datetime.now(KST).date()

# 분야 → 검색 키워드 (사이트별로 각 키워드 1회 검색). 순서 = 우선순위.
CATEGORIES = {
    "백엔드":   ["백엔드 개발자", "서버 개발자"],
    "프론트엔드": ["프론트엔드 개발자", "React 개발자"],
    "모바일":   ["iOS 개발자", "Android 개발자", "React Native", "Flutter"],
    "풀스택":   ["풀스택 개발자"],
}
# 제목에 이게 있으면 개발 직무가 아니므로 제외
NON_DEV = ["퍼블리셔", "퍼블리싱", "qa", "기획", "디자이너", "pm", "영업", "마케팅", "cs ", "운영자", "강사", "교육"]
# 제목으로 분야를 재판정할 때 쓰는 힌트 (검색 키워드보다 제목이 우선)
CAT_HINT = {
    "풀스택": ["풀스택", "full stack", "fullstack", "full-stack"],
    "모바일": ["ios", "android", "안드로이드", "swift", "kotlin 앱", "flutter", "react native", "앱 개발", "모바일"],
    "프론트엔드": ["프론트", "front", "react", "next.js", "vue", "웹 개발"],
    "백엔드": ["백엔드", "backend", "back-end", "서버", "server", "spring", "django", "node", "api"],
}


def region_ok(loc: str) -> bool:
    if not loc:
        return False
    if "서울" in loc:
        return True
    return any(c in loc for c in TARGET_GG)


def exp_ok(text: str) -> bool:
    """2~3년차 지원 가능(요구 하한 ≤ MAX_EXP_FLOOR, 시니어/신입전용 제외)이면 True."""
    t = (text or "").lower()
    if any(k in t for k in SENIOR):
        return False
    tt = (text or "").replace(" ", "")
    if "경력무관" in tt:
        return True
    m = re.search(r"(\d+)[~\-](\d+)년", tt)            # N~M년 / N-M년
    if m:
        return int(m.group(1)) <= MAX_EXP_FLOOR
    m = re.search(r"경력(\d+)년|(\d+)년이상|(\d+)년↑", tt)  # N년 이상류
    if m:
        n = int(next(g for g in m.groups() if g))
        return n <= MAX_EXP_FLOOR
    if "신입" in tt and "경력" not in tt:               # 신입 전용 제외
        return False
    return True                                         # 애매하면 포함


def dev_ok(title: str) -> bool:
    t = (title or "").lower()
    return not any(k in t for k in NON_DEV)


def classify(title: str, default: str) -> str:
    """제목으로 분야를 재판정. 힌트가 없으면 검색 키워드의 분야를 쓴다."""
    t = (title or "").lower()
    for cat, hints in CAT_HINT.items():
        if any(h in t for h in hints):
            return cat
    return default


def norm(s: str) -> str:
    s = re.sub(r"\([^)]*\)|주식회사|㈜|\(주\)|\s+", "", s or "")
    return s.lower()


def make(site, cat, company, title, exp, core, due, link, size="미상"):
    return {"site": site, "cat": classify(title, cat), "company": company, "title": title,
            "size": size, "exp": exp or "경력무관", "core": core, "due": due or "상시채용", "link": link}


# ---------- 원티드 (검색 JSON API) ----------
def collect_wanted():
    out = []
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            try:
                r = requests.get("https://www.wanted.co.kr/api/v4/jobs", headers=H, timeout=12, params={
                    "query": kw, "country": "kr", "job_sort": "job.latest_order",
                    "years": [1, MAX_EXP_FLOOR], "locations": "all", "limit": 20, "offset": 0,
                })
                jobs = r.json().get("data", [])
            except Exception as e:
                print("wanted err", kw, repr(e)[:60]); continue
            for job in jobs:
                jid = job.get("id")
                af, at = job.get("annual_from"), job.get("annual_to")
                if af is None:
                    exp = "경력무관"
                elif at is None or at >= 100:
                    exp = f"{af}년 이상"
                else:
                    exp = f"{af}-{at}년"
                due = job.get("due_time")
                due = "상시채용" if not due else f"~ {str(due)[:10]} 마감"
                addr = (job.get("address") or {}).get("location", "")
                title = job.get("position", "")
                skills = ", ".join(s.get("title", "") for s in (job.get("skill_tags") or [])[:4]) or f"{cat} 개발"
                if not dev_ok(title) or not exp_ok(title + " " + exp) or not region_ok(addr):
                    continue
                out.append(make("원티드", cat, (job.get("company") or {}).get("name", ""), title,
                                exp, skills, due, f"https://www.wanted.co.kr/wd/{jid}"))
    return out


# ---------- 사람인 (검색 HTML) ----------
def collect_saramin():
    out = []

    def grab(p, s):
        m = re.search(p, s, re.S)
        return ihtml.unescape(re.sub("<[^>]+>", "", m.group(1)).strip()) if m else ""

    for cat, kws in CATEGORIES.items():
        for kw in kws:
            url = ("https://www.saramin.co.kr/zf_user/search/recruit"
                   f"?searchword={requests.utils.quote(kw)}&loc_mcd=101000,102000&recruitSort=relation")
            try:
                h = requests.get(url, headers=H, timeout=15).text
            except Exception as e:
                print("saramin err", kw, repr(e)[:60]); continue
            for b in re.split(r'<div class="item_recruit"', h)[1:]:
                title = grab(r'job_tit">\s*<a[^>]*title="([^"]+)"', b)
                href = grab(r'job_tit">\s*<a[^>]*href="([^"]+)"', b)
                corp = grab(r'corp_name">\s*<a[^>]*>(.*?)</a>', b)
                condraw = re.search(r'job_condition">(.*?)</div>', b, re.S)
                conds = []
                if condraw:
                    conds = [ihtml.unescape(re.sub("<[^>]+>", "", x).strip())
                             for x in re.findall(r"<span[^>]*>(.*?)</span>", condraw.group(1), re.S)]
                loc = conds[0] if conds else ""
                exp = next((c for c in conds if "경력" in c or "신입" in c), "")
                jobtype = re.sub(r"\s+", " ", " ".join(conds)).strip()
                date = grab(r'class="date">(.*?)</span>', b)
                if "프리랜서" in jobtype and "정규직" not in jobtype:
                    continue
                if re.search(r"신입|인턴", title) or not dev_ok(title):
                    continue
                if not region_ok(loc) or not exp_ok(title + " " + exp):
                    continue
                ridm = re.search(r"rec_idx=(\d+)", href)
                link = (f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={ridm.group(1)}"
                        if ridm else "https://www.saramin.co.kr" + href)
                clean = title
                if corp and clean.startswith(corp):
                    clean = clean[len(corp):].strip()
                out.append(make("사람인", cat, corp, clean or title, exp, jobtype, date, link))
    return out


# ---------- 잡코리아 (검색 HTML) ----------
def collect_jobkorea():
    out = []
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            try:
                h = requests.get("https://www.jobkorea.co.kr/Search/", headers=H, timeout=15,
                                 params={"stext": kw}).text
            except Exception as e:
                print("jobkorea err", kw, repr(e)[:60]); continue
            for c in h.split('data-sentry-component="CardJob"')[1:]:
                c = c[:4000]
                midm = re.search(r"GI_Read/(\d+)", c)
                if not midm:
                    continue
                gid = midm.group(1)
                txt = ihtml.unescape(re.sub("<[^>]+>", " | ", c))
                txt = re.sub(r"(\s*\|\s*)+", " | ", txt)
                toks = [t.strip() for t in txt.split("|") if t.strip() and "sentry" not in t]
                title = company = ""
                for i, t in enumerate(toks):
                    if t == "스크랩" and i + 1 < len(toks):
                        title = toks[i + 1]
                        company = toks[i + 2] if i + 2 < len(toks) else ""
                        break
                if not title or re.search(r"신입|인턴", title) or not dev_ok(title):
                    continue
                em = re.search(r"(경력\s*\d+~?\d*년?[↑]?|경력무관|신입)", re.sub(r"\s+", " ", " ".join(toks)))
                exp = em.group(1) if em else ""
                loc = next((t for t in toks if t.startswith("서울") or t.startswith("경기")
                            or any(t.startswith(x) for x in ["인천", "부산", "대구", "대전", "광주", "울산", "세종", "강원", "충", "전", "경상", "제주"])), "")
                due = next((t for t in toks if re.search(r"D-\d+|~\s?\d{1,2}/\d{1,2}|상시|마감", t)), "상시채용")
                if not region_ok(loc) or not exp_ok(title + " " + exp):
                    continue
                out.append(make("잡코리아", cat, company, title, exp, loc or f"{cat} 개발", due,
                                f"https://www.jobkorea.co.kr/Recruit/GI_Read/{gid}"))
    return out


def load_sent():
    """sent.json → {link: 'YYYY-MM-DD'}; 오래된 항목은 버린다."""
    try:
        data = json.load(open(SENT_FILE, encoding="utf-8"))
    except Exception:
        return {}
    cutoff = (today_kst() - datetime.timedelta(days=SENT_KEEP_DAYS)).isoformat()
    return {k: v for k, v in data.items() if v >= cutoff}


def save_sent(sent, items):
    today = today_kst().isoformat()
    for it in items:
        sent[it["link"]] = today
    json.dump(sent, open(SENT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def already_sent_today(sent):
    return today_kst().isoformat() in sent.values()


def dedup(items):
    seen, out = set(), []
    for it in items:
        key = (norm(it["company"]), norm(it["title"])[:10])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def pick(items):
    """분야별 PER_CATEGORY 이내, 사이트별 라운드로빈, 총 TOTAL 이내."""
    by_cat = {c: [] for c in CATEGORIES}
    for it in items:
        by_cat.setdefault(it["cat"], []).append(it)
    picked = []
    for cat, lst in by_cat.items():
        by_site = {}
        for it in lst:
            by_site.setdefault(it["site"], []).append(it)
        got, idx = [], 0
        while len(got) < PER_CATEGORY and any(idx < len(v) for v in by_site.values()):
            for site in ["원티드", "사람인", "잡코리아"]:
                v = by_site.get(site, [])
                if idx < len(v) and len(got) < PER_CATEGORY:
                    got.append(v[idx])
            idx += 1
        picked += got
    return picked[:TOTAL]


def build_digest(items):
    today = today_kst().isoformat()
    lines = [f"📅 {today} 풀스택 채용 공고 브리핑", ""]
    n = len(items)
    for i, it in enumerate(items, 1):
        lines += [
            f"[{i}/{n}] {it['cat']}",
            f"[{it['company']}] {it['title']}  ({it['site']})",
            f"  - 규모 : {it['size']}",
            f"  - 경력 : {it['exp']}",
            f"  - 핵심 : {it['core']}",
            f"  - 모집 기간 : {it['due']}",
            f"  - 링크 : {it['link']}",
            "",
        ]
    return "\n".join(lines).strip() + "\n"


def main():
    sent = load_sent()
    if "--send" in sys.argv and already_sent_today(sent) and "--force" not in sys.argv:
        print("오늘 이미 보냈으므로 종료합니다. (강제 재전송: --force)")
        return
    items = []
    for fn in (collect_wanted, collect_saramin, collect_jobkorea):
        try:
            got = fn()
            print(f"{fn.__name__}: {len(got)}건")
            items += got
        except Exception as e:
            print(f"{fn.__name__} 실패:", repr(e)[:80])
    fresh = [it for it in dedup(items) if it["link"] not in sent]
    print(f"중복 제거 후 {len(dedup(items))}건, 이미 보낸 것 제외 후 {len(fresh)}건")
    picked = pick(fresh)
    if not picked:
        print("새 공고가 없어 전송을 건너뜁니다(빈 브리핑 금지).")
        return
    digest = build_digest(picked)
    open("digest.txt", "w", encoding="utf-8").write(digest)
    print("\n===== DIGEST (총 %d건) =====\n" % len(picked))
    print(digest)
    if "--send" in sys.argv:
        import send_kakao
        send_kakao.send(digest)
        save_sent(sent, picked)
        print("\n[전송 완료] 카카오톡으로 발송했습니다. sent.json 갱신.")


if __name__ == "__main__":
    main()
