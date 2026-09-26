"""한줄 요약 SLM 비교. 분석기 템플릿(Narratives.kt)과 같은 사실을 넣고 한 문장을 받아 자동 검사한다.

    python bench.py            # 모델 4개 전부
    python bench.py qwen08     # 하나만
"""

import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = {
    "hcx05": "HyperCLOVAX-SEED-Text-Instruct-0.5B.Q4_K_M.gguf",
    "qwen08": "Qwen_Qwen3.5-0.8B-Q4_K_M.gguf",
    "hcx15": "HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M.gguf",
    "qwen2": "Qwen_Qwen3.5-2B-Q4_K_M.gguf",
}
PORT = 8123
APPS = ["인스타그램", "유튜브", "틱톡"]
PURPOSES = ["학습", "업무", "여가", "연락", "기타"]

SYSTEM = """너는 스크린타임을 줄이도록 돕는 앱의 펫 캐릭터다. 사용자가 보낸 지난주 사실을 보고 주간 한줄 요약을 쓴다.
규칙:
1. 딱 한 문장. 60자 안팎.
2. 사실에 있는 숫자만 쓰고 그대로 옮긴다. 숫자를 계산하거나 단위를 바꾸지 않는다.
3. 사실에 없는 내용, 원인 추측, 중독·의지 같은 판단을 쓰지 않는다.
4. 다정한 존댓말. 꾸짖지 않는다.
5. 요약 문장만 출력한다."""
EXAMPLE_USER = "사실:\n- 전주 대비 주간 합계가 95분 줄었습니다.\n- 야간 구간에서 가장 많이 사용한 앱은 유튜브이고 40분입니다.\n요약:"
EXAMPLE_ASSISTANT = "지난주보다 95분이나 줄였어요, 밤에는 유튜브를 40분 봤네요."


def fmt_pct(x: float) -> str:
    return f"{x:.1f}"


def scenario(rng: random.Random) -> list[str]:
    """Narratives.renderInsights 와 같은 순서·문구로 사실 목록을 만든다."""
    facts = []
    lead = rng.randrange(3)
    early = rng.random() < 0.25
    if early:
        days, nights = rng.randint(0, 6), rng.randint(0, 6)
        head = ["분석에 사용할 수 있는 날은", "이번 주 확인된 날은", "복원에 성공한 날은"][lead]
        if rng.random() < 0.5:
            tail = "7개가 모이지 않아 이번 주 성과로는 다음 목표를 계산하지 않습니다. 현재 목표는 그대로 유지됩니다."
        else:
            tail = "각각 7개가 모여야 개인 기준선을 계산합니다. 그때까지는 처음 입력한 임시 목표를 사용합니다."
        facts.append(f"{head} {days}일, 야간 구간은 {nights}개입니다. {tail}")
    else:
        if rng.random() < 0.7:
            dropped, mean = rng.randint(5, 400), rng.randint(20, 240)
            pct = dropped / (mean * 7 + dropped) * 100
            text = f"지난주 선택한 앱 사용량은 하루 평균 {mean}분입니다. "
            text += ["그 전주보다", "전주 대비", "지난주와 견주면"][lead] + f" 주간 합계가 {dropped}분 줄었습니다."
            text += f" 변화율은 {fmt_pct(pct)}%입니다."
            facts.append(text)
            if rng.random() < 0.4:
                other = rng.randint(5, 300)
                facts.append(
                    ["선택한 앱은 줄었지만", "선택한 앱 사용은 감소했고", "선택한 앱 사용량은 줄었지만"][lead]
                    + f" 나머지 앱 사용이 {other}분 늘었습니다. 다른 앱 사용이 늘었다는 사실만 확인된 것이며 이유는 기록으로 알 수 없습니다."
                )
        if rng.random() < 0.9:
            app, mins, share = rng.choice(APPS), rng.randint(3, 300), rng.uniform(20, 100)
            text = ["야간 구간에서 가장 많이 사용한 앱은", "취침 전후로 가장 오래 사용한 앱은", "밤 시간대 사용이 가장 많았던 앱은"][lead]
            text += f" {app}이고 {mins}분입니다. 야간 사용의 {fmt_pct(share)}%입니다."
            if rng.random() < 0.3:
                text += f" 이 앱의 사용 목적은 '{rng.choice(PURPOSES)}'로 설정되어 있습니다."
            facts.append(text)
    if rng.random() < 0.8:
        de, ne = rng.randint(0, 7), rng.randint(0, 7)
        ds, ns = rng.randint(0, de), rng.randint(0, ne)
        phrase = lambda s, e: "판정 가능한 미션 없음" if e == 0 else f"{e}개 중 {s}개 달성"
        if de or ne:
            tpl = ["이번 주 일일 미션은 {d}, 야간 미션은 {n}입니다.", "이번 주 판정 결과는 일일 {d}, 야간 {n}입니다.", "이번 주 성적은 일일 {d}, 야간 {n}입니다."][lead]
            facts.append(tpl.format(d=phrase(ds, de), n=phrase(ns, ne)))
    return facts or ["분석에 사용할 수 있는 날은 0일, 야간 구간은 0개입니다. 각각 7개가 모여야 개인 기준선을 계산합니다. 그때까지는 처음 입력한 임시 목표를 사용합니다."]


NUM = re.compile(r"\d+(?:\.\d+)?")
BANNED = re.compile(r"중독|우울|불안|의지|게으|한심|실패자|잠든|수면")


def check(facts: list[str], out: str) -> dict[str, bool]:
    fact_nums = set(NUM.findall(" ".join(facts)))
    body = out.strip()
    return {
        "빈 출력": not body,
        "숫자 오류": any(n not in fact_nums for n in NUM.findall(body)),
        "여러 문장": "\n" in body or len(re.findall(r"[.!?](?=\s|$)", body)) > 1,
        "너무 김": len(body) > 90,
        # 한자·가나는 늘 오류. 로마자는 사실에 나온 것(앱 이름 "아프리카TV" 등)만 허용
        "외국 문자": bool(re.search(r"[一-鿿぀-ヿ]", body))
        or any(w not in " ".join(facts) for w in re.findall(r"[A-Za-z]+", body)),
        "금지어": bool(BANNED.search(body)),
    }


def meaning_errors(facts: list[str], out: str) -> list[str]:
    """단위·방향까지 본다. 숫자가 사실에 있어도 엉뚱한 사실에 붙으면 잡는다.
    숫자는 앞뒤가 숫자가 아닐 때만 같은 숫자로 본다 ("363분" 안의 "3분"을 따로 세지 않는다)."""
    fact = " ".join(facts)
    body = re.sub(r"(\d)\s+(분|개|일|%)", r"\1\2", out)  # "38 분" → "38분"

    def at(token: str) -> re.Match | None:
        return re.search(r"(?<![\d.])" + re.escape(token), fact)

    errs = []
    for n, unit in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)(분|%)", body):
        if not at(f"{n}{unit}"):
            errs.append(f"{n}{unit} 없음")
    for e, s_ in re.findall(r"(?<![\d.])(\d+)개 중 (\d+)개", body):
        if not at(f"{e}개 중 {s_}개"):
            errs.append(f"{e}개 중 {s_}개 없음")
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)(분|%)?[^,.]{0,12}?(늘|증가|많아)", body):
        hit = at(f"{m.group(1)}{m.group(2) or ''}")
        if hit and "늘었" not in fact[hit.end():hit.end() + 40]:
            errs.append(f"{m.group(1)} 방향(늘) 틀림")
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)(분|%)?[^,.]{0,12}?(줄|감소)", body):
        hit = at(f"{m.group(1)}{m.group(2) or ''}")
        if hit and not re.search(r"줄었|변화율", fact[max(0, hit.start() - 25):hit.end() + 25]):
            errs.append(f"{m.group(1)} 방향(줄) 틀림")
    if re.search(r"모두 (달성|완료)|다 달성", body) and not any(a == b for a, b in re.findall(r"(\d+)개 중 (\d+)개", fact)):
        errs.append("모두 달성 아님")
    return errs


def post(payload: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions", json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def run_model(key: str, cases: list[list[str]]) -> dict:
    model = HERE / "models" / MODELS[key]
    server = subprocess.Popen(
        ["llama-server", "-m", str(model), "--port", str(PORT), "-c", "2048", "-ngl", "0", "-t", "4", "--jinja"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # -ngl 0: GPU 없이 CPU 4스레드. 폰 CPU 추론에 가깝게 맞춘다
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        rows = []
        for facts in cases:
            user = "사실:\n" + "\n".join(f"- {f}" for f in facts) + "\n요약:"
            t = time.time()
            res = post({
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": EXAMPLE_USER},
                    {"role": "assistant", "content": EXAMPLE_ASSISTANT},
                    {"role": "user", "content": user},
                ],
                "temperature": 0, "max_tokens": 120,
                "chat_template_kwargs": {"enable_thinking": False},
            })
            out = res["choices"][0]["message"]["content"].strip()
            out = re.sub(r"^요약\s*[:：]\s*", "", out)
            rows.append({
                "facts": facts, "out": out, "sec": time.time() - t,
                "tok_s": res.get("timings", {}).get("predicted_per_second"),
                "prompt_ms": res.get("timings", {}).get("prompt_ms"),
                "fail": [k for k, v in check(facts, out).items() if v],
            })
        rss = int(subprocess.run(["ps", "-o", "rss=", "-p", str(server.pid)], capture_output=True, text=True).stdout or 0) // 1024
        return {"model": key, "file_mb": model.stat().st_size // 1_000_000, "rss_mb": rss, "rows": rows}
    finally:
        server.terminate()
        server.wait()


def main() -> None:
    rng = random.Random(7)
    cases = [scenario(rng) for _ in range(40)]
    single = "--single" in sys.argv  # 2차: 사실 하나씩
    if single:
        cases = [[f] for c in cases for f in c]
    keys = [a for a in sys.argv[1:] if not a.startswith("--")] or list(MODELS)
    for key in keys:
        result = run_model(key, cases)
        (HERE / f"result_{key}{'_single' if single else ''}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
        rows = result["rows"]
        ok = sum(not r["fail"] for r in rows)
        fails = {}
        for r in rows:
            for f in r["fail"]:
                fails[f] = fails.get(f, 0) + 1
        speed = sum(r["tok_s"] or 0 for r in rows) / len(rows)
        print(f"{key:7} 통과 {ok}/{len(rows)}  실패 {fails}  {speed:.0f} tok/s  평균 {sum(r['sec'] for r in rows)/len(rows):.1f}s  "
              f"파일 {result['file_mb']}MB  메모리 {result['rss_mb']}MB", flush=True)


if __name__ == "__main__":
    main()
