"""逐个接口实测：接口1 图像识别 / 接口3 制作教程 / 接口4 分享卡片"""
import base64
import io
import json
import sys
import time

import requests
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8001"


def make_test_image(kind: str) -> str:
    """生成一张测试图，返回 dataURL"""
    img = Image.new("RGB", (800, 600))
    d = ImageDraw.Draw(img)
    if kind == "sunset":
        # 日落海面：上橙下蓝紫
        for y in range(600):
            if y < 300:
                r = int(232 - y * 0.2)
                g = int(168 - y * 0.25)
                b = int(124 + y * 0.1)
            else:
                r = int(140 - (y - 300) * 0.2)
                g = int(108 - (y - 300) * 0.15)
                b = int(158 + (y - 300) * 0.05)
            d.line([(0, y), (800, y)], fill=(max(r, 60), max(g, 40), min(b, 220)))
        d.ellipse([350, 180, 450, 280], fill=(250, 200, 120))  # 太阳
    else:  # bouquet 作品照
        img.paste((245, 242, 235), [0, 0, 800, 600])
        for cx, cy, col in [(300, 250, (230, 150, 160)), (450, 220, (240, 200, 210)),
                            (520, 300, (220, 130, 140)), (380, 320, (235, 170, 180))]:
            d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=col)
        d.rectangle([360, 350, 440, 560], fill=(210, 200, 180))  # 花瓶
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def show(name, resp):
    try:
        d = resp.json()
    except Exception:
        print(f"[{name}] HTTP {resp.status_code} 非JSON: {resp.text[:200]}")
        return None
    code = d.get("code")
    print(f"\n===== {name} ===== HTTP {resp.status_code} code={code}")
    if code == 0:
        print(json.dumps(d.get("data"), ensure_ascii=False, indent=2)[:1200])
    else:
        print("失败:", d.get("message"))
    return d


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    if which in ("all", "1"):
        print(">>> 接口1 图像识别")
        t = time.time()
        r = requests.post(f"{BASE}/api/analyze-image", json={"image": make_test_image("sunset")}, timeout=120)
        show("接口1 analyze-image", r)
        print(f"耗时 {time.time()-t:.1f}s")

    if which in ("all", "3"):
        print("\n>>> 接口3 制作教程")
        t = time.time()
        r = requests.post(f"{BASE}/api/generate-tutorial", json={
            "bouquet_image": "",
            "flowers": ["落日珊瑚芍药", "白玫瑰", "尤加利叶"],
            "with_images": False,  # 先不生成配图，快速验证文本步骤
        }, timeout=180)
        show("接口3 generate-tutorial(无配图)", r)
        print(f"耗时 {time.time()-t:.1f}s")

    if which in ("all", "3img"):
        print("\n>>> 接口3 制作教程(异步含配图)")
        t = time.time()
        r = requests.post(f"{BASE}/api/generate-tutorial", json={
            "bouquet_image": "",
            "flowers": ["落日珊瑚芍药", "白玫瑰", "尤加利叶"],
            "with_images": True,
        }, timeout=180)
        d = show("接口3 generate-tutorial(提交任务)", r)
        print(f"提交耗时 {time.time()-t:.1f}s")
        if d and d.get("code") == 0:
            tid = d["data"].get("task_id")
            total = d["data"].get("total", 0)
            print(f"task_id={tid} total={total}，开始轮询...")
            while True:
                time.sleep(3)
                rs = requests.get(f"{BASE}/api/tutorial-status", params={"task_id": tid}, timeout=30)
                ds = rs.json()
                if ds.get("code") != 0:
                    print("轮询失败:", ds.get("message"))
                    break
                dd = ds["data"]
                print(f"  进度 {dd['done']}/{dd['total']} status={dd['status']} 已耗时 {time.time()-t:.1f}s")
                if dd["status"] in ("done", "error"):
                    n_img = sum(1 for s in dd["steps"] if s.get("image_url"))
                    print(f"完成：{n_img}/{len(dd['steps'])} 张配图成功，总耗时 {time.time()-t:.1f}s")
                    for s in dd["steps"]:
                        print(f"  step{s.get('step')}: {s.get('image_url') or '(无图)'}")
                    break
                if time.time() - t > 300:
                    print("超时退出")
                    break

    if which in ("all", "4"):
        print("\n>>> 接口4 生成分享卡片")
        t = time.time()
        r = requests.post(f"{BASE}/api/generate-card", json={
            "before": make_test_image("sunset"),
            "after": make_test_image("bouquet"),
            "title": "日落为礼",
        }, timeout=120)
        d = show("接口4 generate-card", r)
        print(f"耗时 {time.time()-t:.1f}s")
        if d and d.get("code") == 0:
            print("card_image:", d["data"].get("card_image"))


if __name__ == "__main__":
    main()
