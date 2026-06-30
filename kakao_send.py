"""
kakao_send.py
- refresh_token으로 access_token을 새로 발급받고
- '나에게 메시지 보내기' API로 텍스트 또는 사진+링크 메시지를 보낸다.
"""

import json
import requests


def refresh_access_token(client_id: str, refresh_token: str) -> str:
    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]


def send_text(access_token: str, text: str):
    """짧은 텍스트 알림 메시지 (예: '아직 안 올라왔어요')"""
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": "https://kakao.com", "mobile_web_url": "https://kakao.com"},
    }
    return _send(access_token, template_object)


def send_photo(access_token: str, title: str, image_url: str, link_url: str):
    """사진 + 제목(식당이름) + 게시물 링크 메시지"""
    template_object = {
        "object_type": "feed",
        "content": {
            "title": title,
            "description": "오늘의 메뉴",
            "image_url": image_url,
            "image_width": 640,
            "image_height": 640,
            "link": {
                "web_url": link_url,
                "mobile_web_url": link_url,
            },
        },
        "buttons": [
            {
                "title": "게시물 보기",
                "link": {"web_url": link_url, "mobile_web_url": link_url},
            }
        ],
    }
    return _send(access_token, template_object)


def _send(access_token: str, template_object: dict):
    resp = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=15,
    )
    ok = resp.status_code == 200
    print(f"[send] status={resp.status_code} body={resp.text}")
    return ok
