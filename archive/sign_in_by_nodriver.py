import asyncio
import nodriver as uc
import time

from common.config import Config
from pathlib import Path

async def is_already_signed_in(page) -> bool:
    """
    Returns True if the user is already logged in to X (Twitter).
    """
    try:
        # Common logged-in indicators
        selectors = [
            "a[href='/home']",
            "[data-testid='SideNav_AccountSwitcher_Button']",
            "[data-testid='primaryColumn']",
        ]

        for selector in selectors:
            el = await page.query_selector(selector)
            if el:
                return True

        # If login inputs exist, user is NOT logged in
        login_input = await page.query_selector("input[autocomplete='username']")
        if login_input:
            return False

        return False
    except Exception:
        return False


async def main():
    browser = None
    try:
        browser = await uc.start(
            headless=False,
            no_sandbox=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        
        page = await browser.get("https://x.com/login")
        print("✓ Page loaded")
        await asyncio.sleep(10)  # Wait for page to fully load

        # Save initial screenshot
        await page.save_screenshot("artifacts/login_screen.png")
        
        # Dump HTML
        html = await page.get_content()
        Path("artifacts").mkdir(exist_ok=True)
        with open("./artifacts/login.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✓ HTML saved")
        
        # Step 1: Enter username
        print("→ Entering username...")
        username_input = await page.wait_for("input[autocomplete='username']", timeout=20)
        await username_input.send_keys(Config.USER_NAME)
        print("✓ Username entered")
        
        await asyncio.sleep(2)
        
        # Click Next button
        print("→ Clicking Next...")
        next_btn = await page.find("Next", best_match=True, timeout=20)
        await next_btn.click()
        print("✓ Next clicked")
        
        await asyncio.sleep(10)  # Wait for password page
        
        # Save after username screenshot
        await page.save_screenshot("artifacts/after_username.png")
        
        # Step 2: Enter password
        print("→ Entering password...")
        password_input = await page.wait_for("input[type='password']", timeout=20)
        await password_input.send_keys(Config.PASSWORD)
        print("✓ Password entered")
        
        await asyncio.sleep(2)
        
        # Click Log in button
        print("→ Clicking Log in...")
        login_btn = await page.find("Log in", best_match=True, timeout=20)
        await login_btn.click()
        print("✓ Log in clicked")
        
        await asyncio.sleep(5)  # Wait for login to complete
        
        # Save final screenshot
        await page.save_screenshot("artifacts/after_login.png")
                
        if await is_already_signed_in(page):
            print("✓ Login completed!")
        
        # Get final HTML
        html_after = await page.get_content()
        with open("./artifacts/after_login.html", "w", encoding="utf-8") as f:
            f.write(html_after)
        
        await page.sleep(5)
        
    except asyncio.TimeoutError as e:
        print(f"❌ Timeout error: {e}")
        if browser:
            await page.save_screenshot("artifacts/timeout_error.png")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if browser:
            await page.save_screenshot("artifacts/error.png")
    finally:
        # Proper cleanup
        if browser:
            try:
                browser.stop()
                print("✓ Browser closed")
            except Exception as e:
                print(f"Error closing browser: {e}")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())

# Let asyncio process pending subprocess cleanup
loop.run_until_complete(asyncio.sleep(0.1))

loop.close()