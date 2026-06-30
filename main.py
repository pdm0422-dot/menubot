"""
main.py
매일 08:50(KST)에 GitHub Actions가 이 스크립트를 실행한다.

흐름:
1. config.json에서 식당 목록을 읽는다
2. 각 식당의 카카오 채널 '소식' 페이지에서 최신 게시물 사진을 가져온다 (scraper.py)
3. state.json(직전 실행 때 보냈던 이미지 URL)과 비교해서
   - 이미지가 바뀌었으면(=새 메뉴 올라옴) -> 사진+식당이름+링크 발송
   - 안 바뀌었으면(=아직 안 올라옴) -> "아직 안 올라왔어요" 텍스트 발송
4. state.json을 갱신한다 (GitHub Actions 워크플로에서 커밋해서 다음 실행 때도 기억하게 함)
"""

import json
import os
import sys

from scraper import fetch_latest_post
from kakao_send import refresh_access_token, send_text, send_photo

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    client_id = os.environ["KAKAO_REST_API_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]

    config = load_json(CONFIG_PATH, {"restaurants": []})
    state = load_json(STATE_PATH, {})

    try:
        access_token = refresh_access_token(client_id, refresh_token)
    except Exception as e:
        print(f"[fatal] access_token 갱신 실패: {e}")
        sys.exit(1)

    had_error = False

    for r in config["restaurants"]:
        rid, name, url = r["id"], r["name"], r["url"]
        print(f"\n--- {name} 확인 중 ---")

        try:
            result = fetch_latest_post(rid, url)
        except Exception as e:
            print(f"[error] {name} 스크래핑 실패: {e}")
            had_error = True
            continue

        if not result["found"]:
            print(f"[warn] {name}: 이미지를 못 찾음 (페이지 구조 변경 가능성)")
            send_text(access_token, f"[{name}] 메뉴 페이지를 확인하지 못했어요. 직접 확인해주세요.\n{url}")
            continue

        prev_image = state.get(rid, {}).get("image_url")
        new_image = result["image_url"]

        if new_image == prev_image:
            print(f"{name}: 새 게시물 없음")
            send_text(access_token, f"[{name}] 아직 오늘 메뉴가 안 올라왔어요.")
        else:
            print(f"{name}: 새 메뉴 발견, 발송")
            ok = send_photo(
                access_token,
                title=name,
                image_url=new_image,
                link_url=result["post_url"] or url,
            )
            if ok:
                state[rid] = {"image_url": new_image, "post_url": result["post_url"]}
            else:
                had_error = True

    save_json(STATE_PATH, state)

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
