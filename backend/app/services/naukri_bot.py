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
            clean_c = {
                "name": str(c["name"]),
                "value": str(c["value"]),
                "domain": str(c.get("domain") or ".naukri.com"),
                "path": str(c.get("path") or "/"),
            }
            if clean_c["domain"].startswith("http"):
                clean_c["domain"] = ".naukri.com"
            valid_cookies.append(clean_c)

    session_applied_count = 0
    session_target = min(2, config.daily_max_applications - config.applications_today)  # conservative 1-2 per run

    # Prepare search terms
    keywords = (config.target_keywords or "Software Engineer").split(",")[0].strip()
    location = (config.target_locations or "Bengaluru").split(",")[0].strip()

    search_url = f"https://www.naukri.com/jobs-in-india?k={quote_plus(keywords)}&l={quote_plus(location)}"

    browser = None
    try:
        async with async_playwright() as p:
            log.info("Launching stealth Chromium instance...")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ],
            )
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )

            # Mask webdriver flag
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Inject session cookies
            if valid_cookies:
                try:
                    await context.add_cookies(valid_cookies)
                except Exception as e:
                    log.warning("Could not add all cookies: %s", e)

            page = await context.new_page()

            # Visit search page
            log.info("Navigating to Naukri search: %s", search_url)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await _human_delay(4, 7)

            # Check if user is logged in
            content = await page.content()
            if "login" in page.url.lower() or "naukri.com/nlogin" in content:
                msg = "Naukri session has expired or requires re-authentication. Please update cookies."
                log.warning(msg)
                config.status = "session_expired"
                config.status_message = msg
                db.commit()
                return {"status": "session_expired", "message": msg, "applied": 0}

            await _smooth_scroll(page)

            # Find job cards on the search results page
            # Naukri job tuples are typically under .srp-jobtuple-wrapper or article.jobTuple
            job_cards = await page.query_selector_all(".srp-jobtuple-wrapper, article.jobTuple, div[class*='jobTuple']")
            log.info("Found %d job cards on the search page", len(job_cards))

            if not job_cards:
                # Try finding standard job link anchors
                job_cards = await page.query_selector_all("a[class*='title'][href*='job-listings']")

            inspected_count = 0
            for card in job_cards[:10]:
                if session_applied_count >= session_target:
                    break

                inspected_count += 1
                try:
                    title_elem = await card.query_selector("a.title, a[class*='title']")
                    comp_elem = await card.query_selector("a.comp-name, a[class*='comp-name'], [class*='company']")
                    loc_elem = await card.query_selector(".loc-wrap, [class*='location']")

                    job_title = (await title_elem.inner_text()).strip() if title_elem else "Job Role"
                    company = (await comp_elem.inner_text()).strip() if comp_elem else "Company"
                    job_loc = (await loc_elem.inner_text()).strip() if loc_elem else location
                    job_url = await title_elem.get_attribute("href") if title_elem else page.url

                    # Check if already applied or tracked in DB
                    already_applied = db.query(models.Application).join(models.Job).filter(
                        models.Application.user_id == user_id,
                        models.Job.title == job_title,
                        models.Job.company == company,
                    ).first()

                    if already_applied:
                        log.info("Already tracked '%s' at '%s'. Skipping.", job_title, company)
                        continue

                    # Open job details in a new page/tab or navigate
                    log.info("Inspecting job %d: '%s' at '%s'", inspected_count, job_title, company)
                    detail_page = await context.new_page()
                    await detail_page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                    await _human_delay(3, 6)
                    await _smooth_scroll(detail_page)

                    detail_content = await detail_page.content()

                    # 1. Check for "Already Applied"
                    if "already applied" in detail_content.lower():
                        log.info("Job '%s' already applied on Naukri.", job_title)
                        await detail_page.close()
                        continue

                    # 2. Check for "Apply on Company Site" (External Redirect)
                    # We strictly skip company site redirects as requested
                    company_site_btn = await detail_page.query_selector(
                        "button[id*='company-site'], [class*='company-site'], a[href*='apply']:not([id*='apply-button'])"
                    )
                    has_redirect_text = False
                    for txt in ["apply on company site", "apply on company website", "company site"]:
                        if txt in detail_content.lower():
                            has_redirect_text = True
                            break

                    if company_site_btn or has_redirect_text:
                        log.info("Job '%s' at '%s' redirects to company site. Skipping.", job_title, company)
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
                        await _human_delay(3, 6)
                        continue

                    # 3. Look for direct apply button
                    apply_btn = await detail_page.query_selector("#apply-button, button.apply-button, button:has-text('Apply')")
                    if not apply_btn:
                        log.info("No direct apply button found for '%s'. Skipping.", job_title)
                        await detail_page.close()
                        continue

                    # Click Apply
                    log.info("Clicking direct apply for '%s' at '%s'...", job_title, company)
                    await apply_btn.click()
                    await _human_delay(3, 5)

                    # 4. Check for Questionnaires / Custom inputs
                    # If a modal appears with mandatory question inputs or textareas, skip!
                    modal_questions = await detail_page.query_selector_all(
                        ".chatbot-container, .apply-message, .apply-questions, form.custom-form, textarea, input[type='text']:visible"
                    )
                    if modal_questions and len(modal_questions) > 1:
                        log.info("Job '%s' at '%s' has screening questionnaire questions. Skipping.", job_title, company)
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
                        await _human_delay(3, 6)
                        continue

                    # 5. Success verification
                    await _human_delay(2, 4)
                    post_content = await detail_page.content()
                    applied_success = any(
                        s in post_content.lower()
                        for s in ["applied successfully", "application sent", "applied", "you have applied"]
                    )

                    if applied_success:
                        log.info("Successfully direct-applied to '%s' at '%s'!", job_title, company)
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
                    log.error("Error inspecting card: %s", card_err)
                    continue

            # Update final session state
            config.last_run_at = datetime.utcnow()
            config.status = "idle"
            config.status_message = (
                f"Completed run. Inspected {inspected_count} jobs, applied to {session_applied_count} jobs. "
                f"Today total: {config.applications_today}/{config.daily_max_applications}."
            )
            db.commit()

            return {
                "status": "success",
                "applied": session_applied_count,
                "inspected": inspected_count,
                "total_today": config.applications_today,
            }

    except Exception as e:
        log.error("Naukri bot session encountered error: %s", e, exc_info=True)
        config.status = "error"
        config.status_message = f"Error during session: {str(e)[:200]}"
        db.commit()
        return {"status": "error", "message": str(e), "applied": session_applied_count}
    finally:
        if browser:
            await browser.close()
            log.info("Playwright browser closed. Memory freed.")
