"""안드로이드 기기(에뮬레이터 포함)에서 학습용 스크린샷을 adb 로 자동 수집한다.

시나리오 하나 = 세션 하나 = 라벨 하나. 시나리오가 화면을 조작하는 동안 1초마다 캡처한다.

    python collect_android.py yt_shorts --seconds 40
    python collect_android.py yt_shorts yt_home yt_search yt_video --repeat 3
    python collect_android.py ig_reels ig_feed ig_explore ig_stories --repeat 3

저장:  datasets/raw/{라벨}/{기기}_{앱}_{sNN}_{번호}.jpg
검수:  datasets/review/{기기}_{앱}_{sNN}.jpg — 세션 전체 썸네일. 훑어보고 이상한 세션은 raw 에서 지운다.

- 대상 앱이 화면에 떠 있을 때만 저장한다 (앱의 캡처 화이트리스트와 같은 규칙).
- 시나리오가 몇 초마다 화면 구조(uiautomator)를 읽어 기대한 화면인지 확인한다.
  아니면(광고, 엉뚱한 화면) 그 앞뒤 구간의 프레임을 버린다.
- 세션마다 다크 모드·글자 크기를 무작위로 바꾸고 끝나면 되돌린다 (--no-vary 로 끔).
- 화면 구조는 영어 UI 기준으로 찾는다. 한국어 UI 기기에서는 LABELS 를 확인하라.

주의: 추천 피드를 넘기면 타사 영상이 찍힌다. 상용 배포 전 자체 제작 영상 데이터로 대체한다 (README 데이터 전략).
"""

import argparse
import io
import random
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "datasets" / "raw"
REVIEW = ROOT / "datasets" / "review"
ADB = shutil.which("adb") or str(Path.home() / "Library/Android/sdk/platform-tools/adb")

YOUTUBE = "com.google.android.youtube"
INSTAGRAM = "com.instagram.android"
# 숏폼 플레이어에만 있는 표시. 일반 영상 화면의 "Comments" 는 여기 넣으면 안 된다.
SHORTS_MARK = re.compile(r"^(Remix|리믹스)$|See more videos using this sound")
# 인스타 릴스 뷰어. 스토리도 내부 이름이 "reel" 이라 reel 로 찾으면 스토리까지 걸린다.
SHORTS_IDS = {"clips_viewer_view_pager"}
LABELS = {
    "home": ("Home", "홈"),
    "shorts": ("Shorts",),
    "search": ("Search", "검색"),
}
QUERIES = ["cooking recipe", "piano cover", "science explained", "travel vlog", "news today", "football highlights"]


@dataclass
class Node:
    text: str
    desc: str
    x1: int
    y1: int
    x2: int
    y2: int
    rid: str = ""  # resource-id 의 마지막 조각

    @property
    def center(self) -> tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2


def parse_nodes(xml: str) -> list[Node]:
    nodes = []
    for m in re.finditer(r"<node [^>]*>", xml):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0)))
        box = re.findall(r"\d+", attr.get("bounds", ""))
        if len(box) == 4:
            rid = attr.get("resource-id", "").split("/")[-1]
            nodes.append(Node(attr.get("text", ""), attr.get("content-desc", ""), *map(int, box), rid))
    return nodes


def parse_activity_top(dump: str) -> list[Node]:
    """`dumpsys activity top` 에서 앱 resource-id 만 뽑는다. 좌표·글자는 없다."""
    return [Node("", "", 0, 0, 0, 0, rid) for rid in re.findall(r"app:id/(\w+)", dump)]


def next_session_number(raw: Path) -> int:
    """raw 아래 파일명 세 번째 조각(sNN)의 최댓값 + 1. 라벨과 상관없이 세션 번호는 하나로 이어진다."""
    nums = [int(m.group(1)) for p in raw.glob("*/*") if (m := re.fullmatch(r"s(\d+)", (p.stem.split("_") + ["", "", ""])[2]))]
    return max(nums, default=0) + 1


def bad_intervals(checks: list[tuple[float, bool]], end: float) -> list[tuple[float, float]]:
    """checks: (시각, 기대한 화면이었나). 틀린 검사의 앞 구간과 뒤 구간을 버린다."""
    return [(t0, t1) for (t0, ok0), (t1, ok1) in zip(checks, checks[1:] + [(end, True)]) if not (ok0 and ok1)]


class Device:
    def __init__(self, serial: str | None):
        self.base = [ADB] + (["-s", serial] if serial else [])
        size = self.shell("wm size").strip().splitlines()[-1]
        self.w, self.h = map(int, size.split(":")[-1].strip().split("x"))

    def run(self, *args: str) -> bytes:
        return subprocess.run(self.base + list(args), capture_output=True, check=True, timeout=60).stdout

    def shell(self, cmd: str) -> str:
        return self.run("shell", cmd).decode(errors="replace")

    def name(self) -> str:
        avd = self.shell("getprop ro.boot.qemu.avd_name").strip()
        raw = f"emu{avd}" if avd else self.shell("getprop ro.product.model").strip()
        return re.sub(r"[^a-z0-9]", "", raw.lower())  # "_" 는 파일명 구분자라 쓰면 안 된다

    def focus_and_png(self) -> tuple[str, bytes]:
        """포그라운드 창과 스크린샷을 한 번에 받는다."""
        out = self.run("exec-out", "dumpsys window | grep -m1 mCurrentFocus; screencap -p")
        i = out.find(b"\x89PNG")
        return (out[:i].decode(errors="replace"), out[i:]) if i >= 0 else (out.decode(errors="replace"), b"")

    def nodes(self) -> list[Node]:
        xml = self.run("exec-out", "uiautomator dump /dev/tty").decode(errors="replace")
        if "<hierarchy" in xml:
            return parse_nodes(xml)
        # 화면이 계속 움직이면(다크 모드 인스타 릴스 등) uiautomator 가 idle 을 못 기다리고 실패한다.
        # dumpsys 는 기다리지 않지만 좌표·글자가 없어 resource-id 로만 판정할 수 있다.
        return parse_activity_top(self.shell("dumpsys activity top"))

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def tap_label(self, key: str, bottom: bool = False, nodes: list[Node] | None = None) -> None:
        found = [n for n in (nodes or self.nodes()) if n.desc in LABELS[key] or n.text in LABELS[key]]
        if not found:
            raise RuntimeError(f"화면에서 {LABELS[key]} 를 찾지 못했습니다")
        self.tap(*max(found, key=lambda n: n.y1).center if bottom else found[0].center)

    def tap_id(self, rid: str) -> None:
        found = [n for n in self.nodes() if n.rid == rid]
        if not found:
            raise RuntimeError(f"화면에서 {rid} 를 찾지 못했습니다")
        self.tap(*found[0].center)

    def swipe(self, frac_from: float, frac_to: float, ms: int) -> None:
        x = self.w // 2
        self.shell(f"input swipe {x} {int(self.h * frac_from)} {x} {int(self.h * frac_to)} {ms}")

    def key(self, name: str) -> None:
        self.shell(f"input keyevent KEYCODE_{name}")

    def launch(self, package: str) -> None:
        self.shell(f"am force-stop {package}")
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
        time.sleep(6)
        # 권한 요청 창(알림 등)이 뜨면 거절한다. 허용하면 알림이 캡처에 찍힌다.
        deny = [n for n in self.nodes() if n.rid in ("permission_deny_and_dont_ask_again_button", "permission_deny_button")]
        if deny:
            self.tap(*deny[0].center)
            time.sleep(3)


def wait(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def is_shorts(nodes: list[Node]) -> bool:
    return any(SHORTS_MARK.search(n.desc) or SHORTS_MARK.search(n.text) or n.rid in SHORTS_IDS for n in nodes)


def screen_ok(nodes: list[Node], want_shorts: bool) -> bool:
    """화면을 못 읽었으면(빈 목록) 기대한 화면이라고 볼 근거가 없으므로 실패다."""
    return bool(nodes) and is_shorts(nodes) == want_shorts


# ── 시나리오: setup 은 캡처 전에 한 번, step 은 시간이 끝날 때까지 반복. step 은 기대한 화면이었는지 돌려준다.

def yt_shorts_setup(d: Device) -> None:
    d.launch(YOUTUBE)
    d.tap_label("shorts", bottom=True)
    time.sleep(3)


def shorts_step(d: Device) -> bool:
    nodes = d.nodes()
    if not screen_ok(nodes, want_shorts=True):
        d.swipe(0.75, 0.25, 250)  # 광고·엉뚱한 화면이면 넘긴다
        return False
    comments = [  # dumpsys 로 읽은 노드는 좌표가 없어(x2=0) 누를 수 없다
        n for n in nodes
        if n.x2 > 0 and (n.rid == "comment_button" or (re.search(r"comments|댓글", n.desc, re.I) and n.x1 > d.w * 0.7))
    ]
    if comments and random.random() < 0.2:
        d.tap(*comments[0].center)  # 쇼츠 위 댓글창도 숏폼 라벨이다
        wait(2, 4)
        d.swipe(0.8, 0.6, 400)
        wait(1, 2)
        d.key("BACK")
    wait(3, 7)
    d.swipe(0.75, 0.25, 250)
    return True


def yt_home_setup(d: Device) -> None:
    d.launch(YOUTUBE)
    d.tap_label("home", bottom=True)
    time.sleep(3)


def scroll_step(d: Device) -> bool:
    nodes = d.nodes()
    ok = screen_ok(nodes, want_shorts=False)
    if is_shorts(nodes):
        # 스크롤이 게시물을 눌러 릴스·쇼츠가 열렸다 (인스타 탐색에서 잦다). 빠져나온다. 이 구간은 버려진다.
        d.key("BACK")
        time.sleep(2)
        return ok
    for _ in range(3):  # 화면 검사가 3~6초 걸려서, 검사 한 번에 여러 번 스크롤한다
        if random.random() < 0.15:
            d.swipe(0.4, 0.7, 500)
        else:
            d.swipe(0.7, 0.4, 600)
        wait(1.5, 3)
    return ok


def search(d: Device) -> None:
    d.launch(YOUTUBE)
    d.tap_label("home", bottom=True)  # 비로그인 유튜브는 쇼츠 화면으로 열릴 때가 있어 검색 버튼 위치가 다르다
    time.sleep(3)
    d.tap_label("search")
    time.sleep(2)
    d.shell("input text " + random.choice(QUERIES).replace(" ", "%s"))
    d.key("ENTER")
    time.sleep(4)


def yt_video_setup(d: Device) -> None:
    search(d)
    for _ in range(4):
        cards = [
            n for n in d.nodes()
            if n.desc and n.y1 > d.h * 0.12 and n.y2 - n.y1 > d.h * 0.1
            and not re.search(r"Short|Sponsored|광고", n.desc)
        ]
        if cards:
            d.tap(*cards[0].center)
            time.sleep(5)
            if not is_shorts(d.nodes()):
                return
            d.key("BACK")
        d.swipe(0.7, 0.4, 600)
        time.sleep(2)
    raise RuntimeError("검색 결과에서 일반 영상을 찾지 못했습니다")


def yt_video_step(d: Device) -> bool:
    ok = screen_ok(d.nodes(), want_shorts=False)
    if random.random() < 0.3:
        d.swipe(0.75, 0.6, 500)  # 설명·댓글·관련 영상 쪽으로 조금 내린다
    wait(3, 6)
    return ok


def ig_tab(rid: str) -> Callable[[Device], None]:
    def setup(d: Device) -> None:
        d.launch(INSTAGRAM)
        d.tap_id(rid)
        time.sleep(4)
    return setup


def ig_stories_setup(d: Device) -> None:
    ig_tab("feed_tab")(d)
    tray = sorted((n for n in d.nodes() if n.rid == "outer_container" and n.y2 < d.h * 0.35), key=lambda n: n.x1)
    if len(tray) < 2:  # 첫 칸은 내 스토리 (누르면 카메라가 열린다)
        raise RuntimeError("볼 수 있는 스토리가 없습니다. 스토리를 올리는 계정을 몇 개 팔로우하세요")
    d.tap(*tray[1].center)
    time.sleep(3)


def ig_stories_step(d: Device) -> bool:
    ok = screen_ok(d.nodes(), want_shorts=False)  # 스토리가 끝나면 피드로 돌아오는데, 피드도 숏폼 아님이라 괜찮다
    if random.random() < 0.5:
        d.tap(int(d.w * 0.85), d.h // 2)  # 다음 스토리
    wait(2, 4)
    return ok


@dataclass
class Scenario:
    label: str
    app: str
    package: str
    setup: Callable[[Device], None]
    step: Callable[[Device], bool]


SCENARIOS = {
    "yt_shorts": Scenario("shorts", "yt", YOUTUBE, yt_shorts_setup, shorts_step),
    "yt_home": Scenario("not_shorts", "yt", YOUTUBE, yt_home_setup, scroll_step),
    "yt_search": Scenario("not_shorts", "yt", YOUTUBE, search, scroll_step),
    "yt_video": Scenario("not_shorts", "yt", YOUTUBE, yt_video_setup, yt_video_step),
    # DM·프로필은 개인정보가 찍혀서 넣지 않는다. 피드 안에서 자동 재생되는 영상은 숏폼 아님으로 본다.
    "ig_reels": Scenario("shorts", "ig", INSTAGRAM, ig_tab("clips_tab"), shorts_step),
    "ig_feed": Scenario("not_shorts", "ig", INSTAGRAM, ig_tab("feed_tab"), scroll_step),
    "ig_explore": Scenario("not_shorts", "ig", INSTAGRAM, ig_tab("search_tab"), scroll_step),
    "ig_stories": Scenario("not_shorts", "ig", INSTAGRAM, ig_stories_setup, ig_stories_step),
}


def capture(d: Device, package: str, stem: Path, stop: threading.Event, frames: list) -> None:
    tick = 0
    while not stop.is_set():
        t = time.time()
        tick += 1  # 저장하지 않은 틱도 번호를 소비해 시간 간격이 파일명에 남는다
        focus, png = d.focus_and_png()
        if package in focus and png:
            path = stem.with_name(f"{stem.name}_{tick:04d}.jpg")
            Image.open(io.BytesIO(png)).convert("RGB").save(path, quality=95)
            frames.append((t, path))
        stop.wait(max(0.0, 1.0 - (time.time() - t)))


def review_sheet(paths: list[Path], out: Path, cols: int = 10, width: int = 108) -> None:
    if not paths:
        return
    first = Image.open(paths[0])
    height = width * first.height // first.width
    sheet = Image.new("RGB", (cols * width, -(-len(paths) // cols) * height), "white")
    for i, p in enumerate(paths):
        sheet.paste(Image.open(p).resize((width, height)), (i % cols * width, i // cols * height))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)


def run_session(d: Device, device_name: str, key: str, seconds: int, vary: bool) -> None:
    sc = SCENARIOS[key]
    stem = f"{device_name}_{sc.app}_s{next_session_number(RAW):02d}"
    out_dir = RAW / sc.label
    out_dir.mkdir(parents=True, exist_ok=True)

    night_before = "yes" if "yes" in d.shell("cmd uimode night") else "no"
    font_before = d.shell("settings get system font_scale").strip()
    try:
        if vary:
            night, font = random.choice(["yes", "no"]), random.choice(["0.85", "1.0", "1.15", "1.3"])
            d.shell(f"cmd uimode night {night}")
            d.shell(f"settings put system font_scale {font}")
            print(f"[{stem}] {key} → {sc.label}  다크모드 {night}, 글자 {font}")
        else:
            print(f"[{stem}] {key} → {sc.label}")

        sc.setup(d)

        frames, stop = [], threading.Event()
        start = time.time()
        thread = threading.Thread(target=capture, args=(d, sc.package, out_dir / stem, stop, frames))
        thread.start()
        checks = [(start, True)]
        try:
            while time.time() - start < seconds:
                t = time.time()
                checks.append((t, sc.step(d)))
        finally:
            stop.set()
            thread.join()
        end = time.time()
    finally:
        d.shell(f"cmd uimode night {night_before}")
        if font_before in ("", "null"):
            d.shell("settings delete system font_scale")
        else:
            d.shell(f"settings put system font_scale {font_before}")

    bad = bad_intervals(checks, end)
    kept = []
    for t, path in frames:
        if any(t0 <= t <= t1 for t0, t1 in bad):
            path.unlink()
        else:
            kept.append(path)
    fails = sum(not ok for _, ok in checks)
    print(f"[{stem}] 저장 {len(kept)}장, 버림 {len(frames) - len(kept)}장 (화면 검사 실패 {fails}/{len(checks) - 1})")
    if len(kept) < seconds / 3:
        print(f"[{stem}] [경고] 남은 프레임이 적습니다. 검수 격자를 확인하세요.")
    review_sheet(kept, REVIEW / f"{stem}.jpg")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="+", choices=sorted(SCENARIOS))
    parser.add_argument("--seconds", type=int, default=40)
    parser.add_argument("--repeat", type=int, default=1, help="시나리오마다 세션 몇 개")
    parser.add_argument("--serial", help="adb 기기 (여러 대 연결 시)")
    parser.add_argument("--device", help="파일명의 기기 이름 (기본: 기기에서 읽음)")
    parser.add_argument("--no-vary", action="store_true", help="다크 모드·글자 크기를 바꾸지 않는다")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    random.seed(args.seed)
    d = Device(args.serial)
    name = args.device or d.name()
    for _ in range(args.repeat):
        for key in args.scenarios:
            try:
                run_session(d, name, key, args.seconds, not args.no_vary)
            except RuntimeError as e:
                print(f"[{key}] 건너뜀 — {e}")
    print(f"\n검수: {REVIEW} 의 격자를 훑어보고 이상한 세션은 datasets/raw 에서 지우세요.")


if __name__ == "__main__":
    main()
