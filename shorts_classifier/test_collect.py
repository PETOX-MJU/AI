"""python test_collect.py — 수집 스크립트의 기기 없이 도는 부분을 확인한다."""

import argparse
import io
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

import collect_android
from collect_android import (
    Scenario, bad_intervals, device_name, is_shorts, next_session_number, parse_activity_top, parse_nodes, screen_ok,
)


def test_parse_and_marker():
    xml = (
        '<hierarchy><node text="" content-desc="Remix" bounds="[912,1884][1080,2042]" />'
        '<node text="Home" content-desc="" bounds="[97,2293][174,2323]"></node></hierarchy>'
    )
    nodes = parse_nodes(xml)
    assert [(n.text, n.desc) for n in nodes] == [("", "Remix"), ("Home", "")]
    assert nodes[1].center == (135, 2308)
    assert is_shorts(nodes) and not is_shorts(nodes[1:])
    # 일반 영상 화면의 댓글 제목은 쇼츠 표시가 아니다
    assert not is_shorts(parse_nodes('<node text="Comments" content-desc="" bounds="[0,0][1,1]" />'))
    # 인스타 릴스 뷰어는 resource-id 로 찾는다. 스토리("reel_…")는 걸리면 안 된다
    ig = '<node text="" content-desc="" resource-id="com.instagram.android:id/{}" bounds="[0,0][1,1]" />'
    assert is_shorts(parse_nodes(ig.format("clips_viewer_view_pager")))
    assert not is_shorts(parse_nodes(ig.format("reel_viewer_root")))
    assert parse_nodes(ig.format("feed_tab"))[0].rid == "feed_tab"


def test_fallback_and_empty():
    top = (
        "  androidx.viewpager2.widget.ViewPager2{1 VFED..... 0,0-1080,2079 #7f0b1 app:id/clips_viewer_view_pager}\n"
        "  IgSimpleImageView{5b5a6d VFED..C.. 0,178-116,294 #7f0b0d88 app:id/comment_button}\n"
        "  FrameLayout{2 V.E...... 0,0-1080,2400 android:id/content}\n"
    )
    nodes = parse_activity_top(top)
    assert [n.rid for n in nodes] == ["clips_viewer_view_pager", "comment_button"]
    assert screen_ok(nodes, want_shorts=True) and not screen_ok(nodes, want_shorts=False)
    # 화면을 못 읽으면 숏폼·숏폼 아님 어느 쪽으로도 통과시키지 않는다
    assert not screen_ok([], want_shorts=True) and not screen_ok([], want_shorts=False)


def test_next_session_number():
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        assert next_session_number(raw) == 1
        for name in ("shorts/iphone_yt_s01_0001.jpg", "not_shorts/galaxy_yt_s09_0003.jpg", "not_shorts/Screenshot_1.png"):
            (raw / name).parent.mkdir(exist_ok=True)
            (raw / name).touch()
        assert next_session_number(raw) == 10


def test_bad_intervals():
    checks = [(0, True), (5, True), (10, False), (15, True), (20, True)]
    # 10초 검사가 실패 → 5~10, 10~15 버림. 마지막 검사 이후(20~30)는 정상
    assert bad_intervals(checks, 30) == [(5, 10), (10, 15)]
    # 마지막 검사가 실패 → 끝까지 버림
    assert bad_intervals([(0, True), (5, False)], 9) == [(0, 5), (5, 9)]


def run_failing_session(step, fail_restore: bool = False) -> list[Path]:
    """가짜 기기로 세션을 돌려 adb 오류로 실패시키고, raw 에 남은 프레임을 돌려준다. 모듈 전역은 되돌린다."""
    buf = io.BytesIO()
    Image.new("RGB", (4, 8)).save(buf, "PNG")

    class FakeDevice:
        def shell(self, cmd):
            if fail_restore and cmd.startswith("settings delete"):  # 캡처가 끝난 뒤 설정 복원에서 실패
                raise subprocess.CalledProcessError(1, "adb")
            return ""

        def focus_and_png(self):
            return "com.fake/Main", buf.getvalue()

    raw_before = collect_android.RAW
    with tempfile.TemporaryDirectory() as tmp:
        collect_android.RAW = Path(tmp) / "raw"
        collect_android.SCENARIOS["fake"] = Scenario("not_shorts", "ig", "com.fake", lambda d: None, step)
        try:
            collect_android.run_session(FakeDevice(), "emu", "fake", 3, vary=False)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("실패가 삼켜졌다")
        finally:
            del collect_android.SCENARIOS["fake"]
            collect_android.RAW, raw = raw_before, collect_android.RAW
        return list(raw.rglob("*.jpg"))


def test_failed_session_leaves_no_frames():
    def step(d):
        time.sleep(2.5)  # 캡처가 몇 장 찍힐 시간
        raise subprocess.CalledProcessError(1, "adb")

    assert not run_failing_session(step)


def test_restore_failure_leaves_no_frames():
    def step(d):
        time.sleep(1)
        return False  # 화면 검사 실패 → 원래는 거를 프레임. 거르기 전에 설정 복원이 실패한다

    assert not run_failing_session(step, fail_restore=True)
    assert "fake" not in collect_android.SCENARIOS


def test_zero_frame_session_fails():
    class OtherAppDevice:  # 대상 앱이 한 번도 앞에 안 뜬다 → 저장되는 프레임이 없다
        def shell(self, cmd):
            return ""

        def focus_and_png(self):
            return "com.other/Main", b""

    raw_before = collect_android.RAW
    with tempfile.TemporaryDirectory() as tmp:
        collect_android.RAW = Path(tmp) / "raw"
        collect_android.SCENARIOS["fake"] = Scenario("shorts", "yt", "com.fake", lambda d: None, lambda d: time.sleep(0.5) or True)
        try:
            collect_android.run_session(OtherAppDevice(), "emu", "fake", 1, vary=False)
        except RuntimeError as e:
            assert "0장" in str(e)
        else:
            raise AssertionError("0장 세션이 성공으로 끝났다")
        finally:
            del collect_android.SCENARIOS["fake"]
            collect_android.RAW = raw_before


def run_main(results: list[bool]) -> int | str | None:
    """세션 결과(True=성공)를 흉내 내 main() 을 돌리고 종료 코드를 돌려준다 (정상 종료면 None)."""
    outcomes = iter(results)

    def fake_session(*_):
        if not next(outcomes):
            raise RuntimeError("실패")

    class FakeDevice:
        def __init__(self, serial):
            pass

        def name(self):
            return "emu"

    saved = collect_android.Device, collect_android.run_session, sys.argv
    collect_android.Device, collect_android.run_session = FakeDevice, fake_session
    sys.argv = ["collect_android.py", "yt_shorts", "--repeat", str(len(results))]
    try:
        collect_android.main()
        return None
    except SystemExit as e:
        return e.code
    finally:
        collect_android.Device, collect_android.run_session, sys.argv = saved


def test_all_sessions_failed_exits_nonzero():
    assert run_main([False, False]) not in (None, 0)
    assert run_main([False, True]) is None  # 일부 실패는 그 세션만 건너뛴다


def test_device_name():
    assert device_name("galaxya54") == "galaxya54"
    for bad in ("../raw", "my_phone", "Galaxy", "a/b", ""):
        try:
            device_name(bad)
        except argparse.ArgumentTypeError:
            continue
        raise AssertionError(f"{bad!r} 가 통과했다")


if __name__ == "__main__":
    test_parse_and_marker()
    test_fallback_and_empty()
    test_next_session_number()
    test_bad_intervals()
    test_failed_session_leaves_no_frames()
    test_restore_failure_leaves_no_frames()
    test_zero_frame_session_fails()
    test_all_sessions_failed_exits_nonzero()
    test_device_name()
    print("OK")
