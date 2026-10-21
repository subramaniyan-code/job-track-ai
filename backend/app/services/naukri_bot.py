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

_BOT_SESSION_LOCK = asyncio.Lock()

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


async def _human_delay(min_sec: float = 3.0, max_sec: float = 8.0):
    """Randomized human-like pause between browser actions."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def _smooth_scroll(page):
    """Simulates realistic human scrolling down and up."""
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(250, 500)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.8, 1.8))
    # Small scroll up
    await page.mouse.wheel(0, -random.randint(80, 200))
    await asyncio.sleep(random.uniform(0.6, 1.2))


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

    # Strict concurrency guard: never run multiple Chromium instances concurrently on low-spec server
    if _BOT_SESSION_LOCK.locked():
        msg = "A browsing session is already in progress. Preventing duplicate Chrome processes."
        print(f"[NAUKRI_BOT] {msg}", flush=True)
        return {"status": "skipped", "message": msg, "applied": 0}

    await _BOT_SESSION_LOCK.acquire()
    browser = None
    session_applied_count = 0

    try:
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
                c_name = str(c["name"]).strip()
                # Exclude stale Akamai/Cloudflare bot-telemetry cookies bound to previous IP/TLS profiles
                if c_name in ["_abck", "bm_sz", "bm_sv", "bm_mi", "ak_bmsc", "ak_bmsc_s"]:
                    continue

                domain_val = str(c.get("domain") or ".naukri.com").strip()
                if "naukri" not in domain_val:
                    continue
                clean_domain = ".naukri.com" if domain_val.endswith("naukri.com") else (domain_val if domain_val.startswith(".") else f".{domain_val}")
                clean_c = {
                    "name": c_name,
                    "value": str(c["value"]),
                    "domain": clean_domain,
                    "path": str(c.get("path") or "/"),
                    "secure": bool(c.get("secure", True)),
                    "httpOnly": bool(c.get("httpOnly", False)),
                }
                if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                    clean_c["sameSite"] = c["sameSite"]
                valid_cookies.append(clean_c)

        print(f"[NAUKRI_BOT] Found {len(valid_cookies)} sanitized Naukri session cookies for user {user_id}", flush=True)

        session_target = min(2, config.daily_max_applications - config.applications_today)

        # Prepare target queries and locations
        raw_targets = [k.strip() for k in (config.target_keywords or "Cloud & Infrastructure Engineer").split(",") if k.strip()]
        if not raw_targets:
            raw_targets = ["Cloud Infrastructure Engineer", "Cloud Engineer"]

        locations = [loc.strip() for loc in (config.target_locations or "Chennai").split(",") if loc.strip()]
        primary_loc = locations[0] if locations else "Chennai"
        loc_slug = re.sub(r'[^a-zA-Z0-9]', '', primary_loc.lower())

        async with async_playwright() as p:
            print("[NAUKRI_BOT] Launching stealth lightweight Chromium inside Docker...", flush=True)
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--renderer-process-limit=1",
                    "--js-flags=--max-old-space-size=256",
                    "--window-size=1440,900",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--disable-default-apps",
                    "--mute-audio",
                    "--no-first-run",
                ],
            )
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1440, "height": 900},
                locale="en-US",
                timezone_id="Asia/Kolkata",
                extra_http_headers={
                    "accept-language": "en-US,en;q=0.9",
                    "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )

            # Block heavy media, fonts, audio, video & trackers to keep RAM under 150MB
            _blocked_resources = re.compile(
                r"(\.(png|jpg|jpeg|gif|webp|svg|woff|woff2|ttf|eot|ico|mp4|webm|avi|mp3|wav)(\?.*)?$)|("
                r"google-analytics|googletagmanager|doubleclick|youtube|boomerang|facebook|hotjar|newrelic|criteo|adnxs|clarity\.ms)",
                re.IGNORECASE,
            )

            async def _intercept_lightweight(route):
                try:
                    req = route.request
                    if req.resource_type in ["image", "media", "font"] or _blocked_resources.search(req.url):
                        await route.abort()
                    else:
                        await route.continue_()
                except Exception:
                    pass

            await context.route("**/*", _intercept_lightweight)

            # Mask webdriver cleanly
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                if (!window.chrome) {
                    window.chrome = {};
                }
                if (!window.chrome.csi) {
                    window.chrome.csi = function() {};
                }
                if (!window.chrome.loadTimes) {
                    window.chrome.loadTimes = function() {};
                }
            """)

            # Inject session cookies
            added_count = 0
            for c in valid_cookies:
                try:
                    await context.add_cookies([c])
                    added_count += 1
                except Exception:
                    pass
            print(f"[NAUKRI_BOT] Injected {added_count}/{len(valid_cookies)} cookies into browser context", flush=True)

            page = await context.new_page()

            # Warm up session on homepage so Akamai validates the browser
            print("[NAUKRI_BOT] Warming up session at https://www.naukri.com...", flush=True)
            try:
                resp = await page.goto("https://www.naukri.com", wait_until="domcontentloaded", timeout=25000)
                await _human_delay(2, 3)
                warmup_title = await page.title()
                warmup_html = await page.content()
                print(f"[NAUKRI_BOT] Homepage warmup loaded: '{warmup_title}' (HTTP {resp.status if resp else 'N/A'}, {len(warmup_html)} bytes)", flush=True)

                logged_in = await page.query_selector(".nI-gNb-drawer__user-name, [class*='user-name'], a[href*='mnjuser/profile']")
                if logged_in:
                    print(f"[NAUKRI_BOT] Authenticated as: '{(await logged_in.inner_text()).strip()}'", flush=True)
            except Exception as e:
                print(f"[NAUKRI_BOT] Homepage warmup note: {e}", flush=True)

            # Discover job listings across configured target roles
            job_cards = []
            active_target_role = raw_targets[0]

            for raw_kw in raw_targets:
                if job_cards:
                    break

                clean_kw = re.sub(r'[^a-zA-Z0-9\s-]', ' ', raw_kw).strip()
                if primary_loc:
                    clean_kw = re.sub(rf'\b{re.escape(primary_loc)}\b', '', clean_kw, flags=re.IGNORECASE).strip()
                clean_kw = re.sub(r'\s+', ' ', clean_kw)
                if not clean_kw:
                    continue
                slug_kw = re.sub(r'[\s_]+', '-', clean_kw.lower())

                candidate_urls = []
                if loc_slug and loc_slug != "remote":
                    candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs-in-{loc_slug}")
                    candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs?k={quote_plus(clean_kw)}&l={quote_plus(primary_loc)}")
                candidate_urls.append(f"https://www.naukri.com/{slug_kw}-jobs")
                if "infrastructure" in slug_kw and loc_slug:
                    candidate_urls.append(f"https://www.naukri.com/cloud-engineer-jobs-in-{loc_slug}")

                for search_url in candidate_urls:
                    print(f"[NAUKRI_BOT] Trying search target: '{clean_kw}' in '{primary_loc}' -> {search_url}", flush=True)
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as goto_err:
                        print(f"[NAUKRI_BOT] Navigation failed for {search_url}: {goto_err}", flush=True)
                        continue

                    await _human_delay(2, 3)

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
                        await page.wait_for_selector(combined_selector, timeout=10000)
                    except Exception:
                        pass

                    await _smooth_scroll(page)
                    await asyncio.sleep(1.5)

                    job_cards = await page.query_selector_all(combined_selector)

                    if not job_cards:
                        job_cards = await page.query_selector_all("a[href*='/job-listings-'], a[href*='-job-details-']")

                    page_title = await page.title()
                    html_len = len(await page.content())
                    print(f"[NAUKRI_BOT] Page Title: '{page_title}' | URL: {page.url} | HTML size: {html_len} bytes", flush=True)
                    print(f"[NAUKRI_BOT] Found {len(job_cards)} job cards on search page", flush=True)

                    if job_cards:
                        active_target_role = clean_kw
                        break
                    else:
                        raw_html = await page.content()
                        snippet = raw_html[:350].replace('\n', ' ').replace('\r', ' ')
                        print(f"[NAUKRI_BOT] No cards on this URL. Raw HTML: {snippet}", flush=True)

            inspected_count = 0
            for card in job_cards[:15]:
                if session_applied_count >= session_target:
                    break

                inspected_count += 1
                detail_page = None
                try:
                    # Fast in-memory JS extraction with zero locator timeout risk
                    card_data = await card.evaluate("""el => {
                        const isLink = el.tagName.toLowerCase() === 'a';
                        const titleEl = isLink ? el : el.querySelector("a.title, a[class*='title'], a[href*='job-listings'], [class*='row1'] a, [class*='title'] a, h2 a, h3 a");
                        const compEl = el.querySelector("a.comp-name, a[class*='comp-name'], [class*='company'], [class*='compName'], [class*='row2'] a, [class*='subTitle']");
                        const locEl = el.querySelector(".loc-wrap, [class*='location'], [class*='locWdl'], [class*='locIcon'] ~ *, [class*='row3'] span");

                        return {
                            title: titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : '',
                            url: titleEl ? (titleEl.getAttribute('href') || '') : '',
                            company: compEl ? (compEl.innerText || compEl.textContent || '').trim() : 'Hiring Company',
                            location: locEl ? (locEl.innerText || locEl.textContent || '').trim() : ''
                        };
                    }""")

                    job_title = card_data.get("title") or active_target_role
                    company = card_data.get("company") or "Hiring Company"
                    job_loc = card_data.get("location") or primary_loc

                    raw_href = card_data.get("url") or ""
                    if raw_href.startswith("http"):
                        job_url = raw_href
                    elif raw_href:
                        job_url = f"https://www.naukri.com{raw_href}"
                    else:
                        job_url = page.url

                    # Check if already applied or tracked in DB
                    already_applied = db.query(models.Application).join(models.Job).filter(
                        models.Application.user_id == user_id,
                        models.Job.title == job_title,
                        models.Job.company == company,
                    ).first()
                    if already_applied:
                        print(f"[NAUKRI_BOT] Already applied to '{job_title}' at '{company}' in DB. Skipping.", flush=True)
                        continue

                    # Open job details in a new page/tab
                    print(f"[NAUKRI_BOT] Inspecting job #{inspected_count}: '{job_title}' at '{company}'", flush=True)
                    detail_page = await context.new_page()
                    await detail_page.goto(job_url, referer=page.url, wait_until="domcontentloaded", timeout=25000)
                    try:
                        await detail_page.wait_for_selector(
                            "#apply-button, button.apply-button, button:has-text('Apply'), [id*='apply-button'], [class*='apply-button'], [class*='company-site']",
                            timeout=6000,
                        )
                    except Exception:
                        pass
                    await _human_delay(2, 3)
                    await _smooth_scroll(detail_page)

                    detail_content = await detail_page.content()

                    # 1. Check for 'Already Applied'
                    if "already applied" in detail_content.lower():
                        print(f"[NAUKRI_BOT] Job '{job_title}' at '{company}' was already applied. Skipping.", flush=True)
                        continue

                    # 2. Check for 'Apply on Company Site' (External Redirect) - strictly skip
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
                        await _human_delay(2, 3)
                        continue

                    # 3. Look for direct apply button
                    apply_btn = await detail_page.query_selector("#apply-button, button.apply-button, button:has-text('Apply')")
                    if not apply_btn:
                        print(f"[NAUKRI_BOT] No direct apply button found for '{job_title}'. Skipping.", flush=True)
                        continue

                    # Click Apply
                    print(f"[NAUKRI_BOT] Direct apply button found! Clicking Apply for '{job_title}' at '{company}'...", flush=True)
                    try:
                        await apply_btn.click()
                    except Exception as click_err:
                        print(f"[NAUKRI_BOT] Note on apply click: {click_err}", flush=True)

                    # Allow post-click state to settle
                    try:
                        await detail_page.wait_for_load_state("domcontentloaded", timeout=6000)
                    except Exception:
                        pass
                    await _human_delay(2, 4)

                    # 4. Check for Questionnaires / Custom inputs
                    modal_questions = []
                    try:
                        modal_questions = await detail_page.query_selector_all(
                            ".chatbot-container, .apply-message, .apply-questions, form.custom-form, textarea, input[type='text']:visible"
                        )
                    except Exception:
                        pass

                    if modal_questions and len(modal_questions) > 1:
                        print(f"[NAUKRI_BOT] Job '{job_title}' has questionnaire questions. Skipping safely.", flush=True)
                        try:
                            close_btn = await detail_page.query_selector("button.crossIcon, [class*='close'], .icon-close")
                            if close_btn:
                                await close_btn.click()
                        except Exception:
                            pass
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
                        await _human_delay(2, 3)
                        continue

                    # 5. Success verification
                    await _human_delay(1, 2)
                    post_content = ""
                    post_url = ""
                    try:
                        post_content = await detail_page.content()
                        post_url = detail_page.url.lower()
                    except Exception:
                        pass

                    success_phrases = [
                        "applied successfully",
                        "application sent",
                        "successfully applied",
                        "application submitted",
                        "application successful",
                        "you have applied",
                        "your application has been sent",
                    ]
                    post_lower = post_content.lower()
                    has_phrase = any(p in post_lower for p in success_phrases)

                    button_applied = False
                    try:
                        btn_el = await detail_page.query_selector("button.apply-button, #apply-button, button[class*='applied']")
                        if btn_el:
                            btn_text = (await btn_el.inner_text()).strip().lower()
                            if "applied" in btn_text:
                                button_applied = True
                    except Exception:
                        pass

                    applied_success = (
                        has_phrase
                        or button_applied
                        or "apply/success" in post_url
                        or "success" in post_url
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

                        await _human_delay(5, 10)

                except Exception as card_err:
                    print(f"[NAUKRI_BOT] Error inspecting card #{inspected_count}: {card_err}", flush=True)
                    continue
                finally:
                    if detail_page and not detail_page.is_closed():
                        try:
                            await detail_page.close()
                        except Exception:
                            pass

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
            try:
                await browser.close()
            except Exception:
                pass
            print("[NAUKRI_BOT] Playwright Chromium browser closed. Memory freed.", flush=True)
        if config.status == "running":
            config.status = "idle"
            db.commit()
        if _BOT_SESSION_LOCK.locked():
            _BOT_SESSION_LOCK.release()
