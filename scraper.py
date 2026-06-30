"""
scraper.py
카카오톡 채널 '소식' 페이지(pf.kakao.com/_xxx/posts)를 가상 브라우저로 열어서
가장 최신 게시물의 대표 이미지 URL과 게시물 링크를 추출한다.

카카오가 공식 API를 제공하지 않기 때문에, 페이지 구조에 맞춰 휴리스틱(추정 규칙)으로
"진짜 게시물 사진"을 찾아낸다. 화면 구조가 바뀌면 이 파일의 SELECTORS 부분만
조정하면 된다.

디버그 모드(DEBUG_MODE=1)로 실행하면 debug/ 폴더에 스크린샷과 추출된 HTML을 저장해서
실제로 무엇을 긁어왔는지 눈으로 확인할 수 있다.
"""

import os
import re
import time
from playwright.sync_api import sync_playwright

DEBUG_MODE = os.environ.get("DEBUG_MODE", "0") == "1"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug")


def _save_debug(page, restaurant_id, label):
    if not DEBUG_MODE:
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)
    shot_path = os.path.join(DEBUG_DIR, f"{restaurant_id}_{label}.png")
    html_path = os.path.join(DEBUG_DIR, f"{restaurant_id}_{label}.html")
    try:
        page.screenshot(path=shot_path, full_page=True)
    except Exception as e:
        print(f"[debug] screenshot 실패: {e}")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception as e:
        print(f"[debug] html 저장 실패: {e}")


def fetch_latest_post(restaurant_id: str, url: str):
    """
    반환값: dict {
        'image_url': str | None,
        'post_url': str | None,
        'found': bool
    }
    """
    result = {"image_url": None, "post_url": None, "found": False}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 480, "height": 900},  # 모바일 레이아웃이 더 단순한 경우가 많음
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; SM-S911N) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            # networkidle까지 못 가도 일단 진행 (SPA가 계속 polling할 수 있음)
            pass

        # 게시물이 lazy-load 되는 경우를 대비해 잠깐 대기 + 스크롤
        page.wait_for_timeout(2500)
        try:
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(1000)
        except Exception:
            pass

        _save_debug(page, restaurant_id, "loaded")

        # 1차 시도: 게시물 상세로 연결되는 <a href="*/posts/숫자"> 패턴 찾기
        post_links = page.eval_on_selector_all(
            "a[href*='/posts/']",
            "els => els.map(e => e.getAttribute('href'))",
        )
        post_links = [href for href in post_links if href and re.search(r"/posts/\d+", href)]

        first_post_href = post_links[0] if post_links else None

        # 2차: 본문 영역의 <img> 중 충분히 큰(=로고/아이콘이 아닌) 첫 이미지 찾기
        images = page.eval_on_selector_all(
            "img",
            """
            els => els.map(e => ({
                src: e.currentSrc || e.src,
                w: e.naturalWidth,
                h: e.naturalHeight
            }))
            """,
        )
        # 너비/높이가 200px 이상인 것만 '진짜 사진'으로 간주 (프로필/아이콘 제외)
        big_images = [
            img for img in images
            if img.get("w", 0) >= 200 and img.get("h", 0) >= 200 and img.get("src")
        ]

        if big_images:
            result["image_url"] = big_images[0]["src"]
            result["found"] = True

        if first_post_href:
            if first_post_href.startswith("http"):
                result["post_url"] = first_post_href
            else:
                result["post_url"] = "https://pf.kakao.com" + first_post_href
        else:
            # 개별 게시물 링크를 못 찾으면 채널 소식 목록 페이지로 대체
            result["post_url"] = url

        _save_debug(page, restaurant_id, "result")

        browser.close()

    return result


if __name__ == "__main__":
    # 단독 실행 테스트용: config.json의 모든 식당에 대해 추출 결과 출력
    import json

    os.environ["DEBUG_MODE"] = "1"
    DEBUG_MODE = True

    with open(os.path.join(os.path.dirname(__file__), "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    for r in cfg["restaurants"]:
        print(f"\n=== {r['name']} ===")
        res = fetch_latest_post(r["id"], r["url"])
        print(res)
        time.sleep(1)
