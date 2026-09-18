"""Real-browser source playback, editing and download proof; server supplied separately."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import retain
from watch.training_draft import TrainingDraft


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--url")
    target.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.review:
        args.url = (args.review.resolve() / "index.html").as_uri()
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        retain(args.output / "initial-media.json", page.locator("video").evaluate("v=>({readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null,source:v.currentSrc})"))
        page.wait_for_function("document.querySelector('video').readyState >= 1")
        page.evaluate("document.querySelector('video').play()")
        page.wait_for_function("document.querySelector('video').currentTime > .25")
        played = page.locator("video").evaluate("v=>({time:v.currentTime,width:v.videoWidth,height:v.videoHeight})")
        page.locator("video").evaluate("v=>v.pause()")
        page.locator("#scrub").fill("20")
        page.locator("#scrub").dispatch_event("input")
        page.wait_for_function("Math.abs(document.querySelector('video').currentTime-10)<.1")
        page.locator("#start").fill("9")
        page.locator("#end").fill("11")
        page.locator("#caption").fill("The viewport changes scale. This footage alone does not establish which input caused it.")
        page.get_by_role("button", name="Add draft segment", exact=True).click()
        assert page.locator("#drafts li").count() == 1
        with page.expect_download() as download:
            page.get_by_role("button", name="Download source-linked plan").click()
        destination = args.output / "training-draft.json"
        download.value.save_as(destination)
        plan = TrainingDraft.model_validate_json(destination.read_bytes())
        page.screenshot(path=str(args.output / "review-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(args.output / "review-mobile.png"), full_page=True)
        assert not errors, errors
        retain(args.output / "report.json", {"actual_playback": played, "seek_seconds": 10,
            "exported_segments": len(plan.steps), "browser_errors": errors, "mobile_overflow": False,
            "caption_author": "test operator; not automatic semantic understanding"})
        browser.close()


if __name__ == "__main__":
    main()
