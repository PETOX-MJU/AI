"""python test_collect.py — 수집 스크립트의 기기 없이 도는 부분을 확인한다."""

import tempfile
from pathlib import Path

from collect_android import bad_intervals, is_shorts, next_session_number, parse_activity_top, parse_nodes, screen_ok


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


if __name__ == "__main__":
    test_parse_and_marker()
    test_fallback_and_empty()
    test_next_session_number()
    test_bad_intervals()
    print("OK")
