import os

import httpx


async def send_line_group_message(message: str) -> tuple[bool, str]:
    token = os.getenv("LINE_NOTIFY_TOKEN")
    if not token:
        return False, "LINE_NOTIFY_TOKEN not configured"

    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://notify-api.line.me/api/notify", headers=headers, data=data)

    if response.status_code == 200:
        return True, "LINE message sent"
    return False, f"LINE notify failed: {response.status_code}"
