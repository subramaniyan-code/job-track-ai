import asyncio
import json
import logging
import random
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from .. import models
from ..security import decrypt_str

log = logging.getLogger("naukri_bot")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


async def _human_delay(min_sec: float = 4.0, max_sec: float = 12.0):
    """Randomized human-like pause between browser actions."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def _smooth_scroll(page):
    """Simulates realistic human scrolling down and up."""
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(250, 500)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(1.2, 2.5))
    # Small scroll up
    await page.mouse.wheel(0, -random.randint(80, 200))
    await asyncio.sleep(random.uniform(1.0, 2.0))


async def run_naukri_auto_apply_session(db: Session, config: models.NaukriBotConfig) -> dict[str, Any]:
    """
    Executes a single conservative stealth auto-apply session for one user.
    Strictly applies only to 1-click 'Apply on Naukri' jobs and skips external redirects
    or multi-step questionnaires.
    """
    from playwright.async_api import async_playwright

    user_id = config.user_id
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Reset daily application counter at midnight
    if config.last_reset_date != today_str:
        config.applications_today = 0
        config.last_reset_date = today_str
        db.commit()

    # Safety checks
    if config.applications_today >= config.daily_max_applications:
        msg = f"Daily limit reached ({config.applications_today}/{config.daily_max_applications} applications). Session skipped for safety."
        log.info(msg)
        config.status = "idle"
        config.status_message = msg
        db.commit()
        return {"status": "skipped", "message": msg, "applied": 0}

    if not config.session_cookies_encrypted:
        msg = "No Naukri session configured. Please add your session cookies in Auto-Apply settings."
        config.status = "session_expired"
        config.status_message = msg
        db.commit()
        return {"status": "error", "message": msg, "applied": 0}

    # Decrypt session cookies
    cookies_json_str = decrypt_str(config.session_cookies_encrypted)
    if not cookies_json_str:
        msg = "Failed to decrypt Naukri session. Please re-enter your session cookies."
        config.status = "session_expired"
        config.status_message = msg
        db.commit()
        return {"status": "error", "message": msg, "applied": 0}

    try:
        raw_cookies = json.loads(cookies_json_str)
    except Exception as e:
        msg = f"Invalid cookie JSON format: {e}"
        config.status = "error"
        config.status_message = msg
        db.commit()
        return {"status": "error", "message": msg, "applied": 0}

    config.status = "running"
    config.status_message = "Starting stealth browsing session on Naukri..."
    db.commit()

    # Parse cookies list or storageState format
    cookies_to_add = []
    if isinstance(raw_cookies, dict) and "cookies" in raw_cookies:
        cookies_to_add = raw_cookies["cookies"]
    elif isinstance(raw_cookies, list):
        cookies_to_add = raw_cookies

    # Clean cookie fields for Playwright compatibility
    valid_cookies = []
    for c in cookies_to_add:
        if isinstance(c, dict) and "name" in c and "value" in c:
            domain_val = str(c.get("domain") or ".naukri.com").strip()
            if "naukri" not in domain_val:
                continue
            clean_domain = ".naukri.com" if domain_val.endswith("naukri.com") else (domain_val if domain_val.startswith(".") else f".{domain_val}")
            clean_c = {
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": clean_domain,
                "path": str(c.get("path") or "/"),
            }
            valid_cookies.append(clean_c)

    print(f"[NAUKRI_BOT] Found {len(valid_cookies)} sanitized Naukri session cookies for user {user_id}", flush=True)

    session_applied_count = 0
    session_target = min(2, config.daily_max_applications - config.applications_today)

    # Prepare target queries and locations
    raw_targets = [k.strip() for k in (config.target_keywords or "Cloud & Infrastructure Engineer").split(",") if k.strip()]
    if not raw_targets:
        raw_targets = ["Cloud Infrastructure Engineer", "Cloud Engineer"]

    locations = [loc.strip() for loc in (config.target_locations or "Chennai").split(",") if loc.strip()]
    primary_loc = locations[0] if locations else "Chennai"
    loc_slug = re.sub(r'[^a-zA-Z0-9]', '', primary_loc.lower())

    browser = None
    try:
        async with async_playwright() as p:
            print("[NAUKRI_BOT] Launching stealth Chromium instance inside Docker...", flush=True)
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--window-size=1920,1080",
                ],
            )
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )

            # Mask webdriver flag and spoof browser properties
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = { runtime: {} };
            """)

            # Inject session cookies individually so invalid entries don't block the rest
            added_count = 0
            for c in valid_cookies:
                try:
                    await context.add_cookies([c])
                    added_count += 1
                except Exception:
                    pass
            print(f"[NAUKRI_BOT] Injected {added_count}/{len(valid_cookies)} cookies into browser context", flush=True)

            page = await context.new_page()

            # Discover job listings across configured target roles
            job_cards = []
            active_target_role = raw_targets[0]

            for raw_kw in raw_targets:
                if job_cards:
                    break

                clean_kw = re.sub(r'[^a-zA-Z0-9\s-]', ' ', raw_kw).strip()
                clean_kw = re.sub(r'\s+', ' ', clean_kw)
                slug_kw = re.sub(r'[\s_]+', '-', clean_kw.lower())

                candidate_urls = []
                if loc_slug and loc_slug != "remote":
                    candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs-in-{loc_slug}")
                    candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs?k={quote_plus(clean_kw)}&l={quote_plus(primary_loc)}")
                candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs")
                candidate_urls.append(f"https://www.naukri.com/jobs-in-india?k={quote_plus(clean_kw)}&l={quote_plus(primary_loc)}")

                for search_url in candidate_urls:
                    print(f"[NAUKRI_BOT] Trying search target: '{clean_kw}' in '{primary_loc}' -> {search_url}", flush=True)
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as goto_err:
                        print(f"[NAUKRI_BOT] Navigation failed for {search_url}: {goto_err}", flush=True)
                        continue

                    await _human_delay(2, 4)

                    # Check if redirected to login page
                    current_url = page.url.lower()
                    if "nlogin/login" in current_url:
                        msg = "Naukri session has expired or requires fresh cookies. Please re-enter session cookies."
                        print(f"[NAUKRI_BOT] {msg}", flush=True)
                        config.status = "session_expired"
                        config.status_message = msg
                        db.commit()
                        return {"status": "session_expired", "message": msg, "applied": 0}

                    # Wait for Next.js hydration and job tuples to mount
                    card_selectors = [
                        "div.cust-job-tuple",
                        "div.srp-tuple",
                        "div[class*='cust-job-tuple']",
                        "div[class*='srp-tuple']",
                        "div[class*='tuple-wrap']",
                        "div[class*='styles_fcs__tuple']",
                        "div[class*='styles_fcs__reg-tuple']",
                        ".srp-jobtuple-wrapper",
                        "article.jobTuple",
                        "div[data-job-id]",
                        "div[data-jobid]",
                        "div[data-tuple-id]",
                        "a[class*='title'][href*='job-listings']",
                        "a[href*='-jobs-'][class*='title']",
                    ]
                    combined_selector = ", ".join(card_selectors)

                    try:
                        await page.wait_for_selector(combined_selector, timeout=12000)
                    except Exception:
                        pass

                    await _smooth_scroll(page)
                    await asyncio.sleep(2)

                    job_cards = await page.query_selector_all(combined_selector)

                    # Fallback: inspect any job listings links
                    if not job_cards:
                        job_cards = await page.query_selector_all("a[href*='/job-listings-'], a[href*='-job-details-']")

                    page_title = await page.title()
                    print(f"[NAUKRI_BOT] Page Title: '{page_title}' | Current URL: {page.url}", flush=True)
                    print(f"[NAUKRI_BOT] Found {len(job_cards)} job cards on search page", flush=True)

                    if job_cards:
                        active_target_role = clean_kw
                        break
                    else:
                        snippet = (await page.inner_text("body"))[:200].replace("\n", " ") if await page.query_selector("body") else ""
                        print(f"[NAUKRI_BOT] No cards on this URL. Snippet: {snippet}", flush=True)

            inspected_count = 0
            for card in job_cards[:15]:
                if session_applied_count >= session_target:
                    break

                inspected_count += 1
                try:
                    tag_name = await card.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == "a":
                        title_elem = card
                        comp_elem = None
                        loc_elem = None
                    else:
                        title_elem = await card.query_selector(
                            "a.title, a[class*='title'], a[href*='job-listings'], [class*='row1'] a, [class*='title'] a, h2 a, h3 a"
                        )
                        comp_elem = await card.query_selector(
                            "a.comp-name, a[class*='comp-name'], [class*='company'], [class*='compName'], [class*='row2'] a, [class*='subTitle']"
                        )
                        loc_elem = await card.query_selector(
                            ".loc-wrap, [class*='location'], [class*='locWdl'], [class*='locIcon'] ~ *, [class*='row3'] span"
                        )

                    job_title = (await title_elem.inner_text()).strip() if title_elem else active_target_role
                    company = (await comp_elem.inner_text()).strip() if comp_elem else "Hiring Company"
                    job_loc = (await loc_elem.inner_text()).strip() if loc_elem else primary_loc

                    if title_elem:
                        raw_href = (await title_elem.get_attribute("href")) or ""
                        if raw_href.startswith("http"):
                            job_url = raw_href
                        elif raw_href:
                            job_url = f"https://www.naukri.com{raw_href}"
                        else:
                            job_url = page.url
                    else:
                        job_url = page.url

                    # Check if already applied or tracked in DB
                    already_applied = db.query(models.Application).join(models.Job).filter(
                        models.Application.user_id == user_id,
                        models.Job.title == job_title,
                        models.Job.company == company,
                    ).first()

                    # Open job details in a new page/tab or navigate
                    print(f"[NAUKRI_BOT] Inspecting job #{inspected_count}: '{job_title}' at '{company}'", flush=True)
                    detail_page = await context.new_page()
                    await detail_page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                    try:
                        await detail_page.wait_for_selector(
                            "#apply-button, button.apply-button, button:has-text('Apply'), [id*='apply-button'], [class*='apply-button'], [class*='company-site']",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    await _human_delay(3, 5)
                    await _smooth_scroll(detail_page)

                    detail_content = await detail_page.content()

                    # 1. Check for "Already Applied"
                    if "already applied" in detail_content.lower():
                        print(f"[NAUKRI_BOT] Job '{job_title}' at '{company}' was already applied. Skipping.", flush=True)
                        await detail_page.close()
                        continue

                    # 2. Check for "Apply on Company Site" (External Redirect)
                    # We strictly skip company site redirects as requested
                    company_site_btn = await detail_page.query_selector(
                        "button[id*='company-site'], [class*='company-site'], a:has-text('Apply on company site'), a:has-text('Apply on Company Website')"
                    )
                    has_redirect_text = False
                    for txt in ["apply on company site", "apply on company website", "company site", "external site"]:
                        if txt in detail_content.lower():
                            has_redirect_text = True
                            break

                    if company_site_btn or has_redirect_text:
                        print(f"[NAUKRI_BOT] Job '{job_title}' redirects to external company portal. Skipping.", flush=True)
                        db.add(models.NaukriBotLog(
                            user_id=user_id,
                            job_title=job_title,
                            company=company,
                            location=job_loc,
                            url=job_url,
                            action="skipped_redirect",
                            notes="Skipped: Redirects to external company portal",
                        ))
                        db.commit()
                        await detail_page.close()
                        await _human_delay(2, 4)
                        continue

                    # 3. Look for direct apply button
                    apply_btn = await detail_page.query_selector("#apply-button, button.apply-button, button:has-text('Apply')")
                    if not apply_btn:
                        print(f"[NAUKRI_BOT] No direct apply button found for '{job_title}'. Skipping.", flush=True)
                        await detail_page.close()
                        continue

                    # Click Apply
                    print(f"[NAUKRI_BOT] Direct apply button found! Clicking Apply for '{job_title}' at '{company}'...", flush=True)
                    await apply_btn.click()
                    await _human_delay(3, 5)

                    # 4. Check for Questionnaires / Custom inputs
                    # If a modal appears with mandatory question inputs or textareas, skip!
                    modal_questions = await detail_page.query_selector_all(
                        ".chatbot-container, .apply-message, .apply-questions, form.custom-form, textarea, input[type='text']:visible"
                    )
                    if modal_questions and len(modal_questions) > 1:
                        print(f"[NAUKRI_BOT] Job '{job_title}' has questionnaire questions. Skipping safely.", flush=True)
                        # Try to close modal
                        close_btn = await detail_page.query_selector("button.crossIcon, [class*='close'], .icon-close")
                        if close_btn:
                            await close_btn.click()
                        db.add(models.NaukriBotLog(
                            user_id=user_id,
                            job_title=job_title,
                            company=company,
                            location=job_loc,
                            url=job_url,
                            action="skipped_questions",
                            notes="Skipped: Contains custom screening questions",
                        ))
                        db.commit()
                        await detail_page.close()
                        await _human_delay(2, 4)
                        continue

                    # 5. Success verification
                    await _human_delay(2, 4)
                    post_content = await detail_page.content()
                    applied_success = any(
                        s in post_content.lower()
                        for s in ["applied successfully", "application sent", "applied", "you have applied"]
                    )

                    if applied_success:
                        print(f"[NAUKRI_BOT] SUCCESS: Successfully 1-click direct applied to '{job_title}' at '{company}'!", flush=True)
                        session_applied_count += 1
                        config.applications_today += 1

                        # Save to JobTrack database
                        new_job = models.Job(
                            source="naukri_bot",
                            external_id=f"naukri-{job_url}",
                            title=job_title,
                            company=company,
                            location=job_loc,
                            url=job_url,
                            platform="Naukri (Auto-Bot)",
                            posted_at=datetime.utcnow(),
                        )
                        db.add(new_job)
                        db.flush()

                        new_app = models.Application(
                            user_id=user_id,
                            job_id=new_job.id,
                            status=models.ApplicationStatus.applied,
                            applied_at=datetime.utcnow(),
                            last_activity_at=datetime.utcnow(),
                            notes="Auto-applied with profile resume via Naukri Playwright Bot",
                        )
                        db.add(new_app)
                        db.flush()

                        db.add(models.ApplicationEvent(
                            application_id=new_app.id,
                            user_id=user_id,
                            event_type="created",
                            to_status="applied",
                            note=f"Auto-applied via Naukri Bot: {job_title} at {company}",
                        ))

                        db.add(models.NaukriBotLog(
                            user_id=user_id,
                            job_title=job_title,
                            company=company,
                            location=job_loc,
                            url=job_url,
                            action="applied",
                            notes="Successfully applied via 1-click apply",
                        ))
                        db.commit()

                    await detail_page.close()
                    await _human_delay(8, 16)  # Human reading pause between applications

                except Exception as card_err:
                    print(f"[NAUKRI_BOT] Error inspecting card #{inspected_count}: {card_err}", flush=True)
                    continue

            # Update final session state
            config.last_run_at = datetime.utcnow()
            config.status = "idle"
            config.status_message = (
                f"Completed run. Inspected {inspected_count} jobs, applied to {session_applied_count} jobs. "
                f"Today total: {config.applications_today}/{config.daily_max_applications}."
            )
            db.commit()
            print(f"[NAUKRI_BOT] {config.status_message}", flush=True)

            return {
                "status": "success",
                "applied": session_applied_count,
                "inspected": inspected_count,
                "total_today": config.applications_today,
            }

    except Exception as e:
        print(f"[NAUKRI_BOT] Session encountered exception: {e}", flush=True)
        import traceback
        traceback.print_exc()
        config.status = "error"
        config.status_message = f"Error during session: {str(e)[:200]}"
        db.commit()
        return {"status": "error", "message": str(e), "applied": session_applied_count}
    finally:
        if browser:
            await browser.close()
            print("[NAUKRI_BOT] Playwright Chromium browser closed. Memory freed.", flush=True)
