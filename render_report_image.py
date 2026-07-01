import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from report_generator import get_latest_report


async def render_latest_report_image():
    report_path = get_latest_report()
    if not report_path:
        raise RuntimeError("캡처할 HTML 리포트가 없습니다.")

    source = Path(report_path).resolve()
    output = source.with_suffix(".png")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1360, "height": 1800}, device_scale_factor=1)
        await page.goto(source.as_uri(), wait_until="networkidle")
        await page.screenshot(path=str(output), full_page=True)
        await browser.close()

    print(f"Rendered report image: {output}")
    return str(output)


if __name__ == "__main__":
    asyncio.run(render_latest_report_image())
