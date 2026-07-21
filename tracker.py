import json
import os
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests


def get_price(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    try:
        # Wait for the price element to load
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "originalprice"))
        )
        price_text = price_element.text

        # Clean the string: remove '₹', commas, and whitespace
        clean_price = float(price_text.replace('₹', '').replace(',', '').strip())
        return clean_price
    finally:
        driver.quit()


def load_books():
    """Load book list from books.json (same directory as this script)."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_all_prices(books):
    """Fetch prices for all books. Returns list of dicts with name, url, price/error."""
    results = []
    for book in books:
        name = book["name"]
        url = book["url"]
        try:
            price = get_price(url)
            results.append({"name": name, "url": url, "price": price, "error": None})
            print(f"✅ {name}: ₹{price}")
        except Exception as e:
            results.append({"name": name, "url": url, "price": None, "error": str(e)})
            print(f"❌ {name}: Failed — {e}")
    return results


def build_message(results):
    """Build a formatted price report message."""
    lines = ["📚 *Bookswagon Price Report*", ""]
    for r in results:
        if r["error"]:
            lines.append(f"❌ *{r['name']}*: Could not fetch price")
            lines.append(f"   Error: {r['error'][:100]}")
        else:
            lines.append(f"📖 *{r['name']}*: ₹{r['price']}")
            lines.append(f"   🔗 {r['url']}")
        lines.append("")
    return "\n".join(lines)


def build_discord_message(results):
    """Build a Discord-formatted price report (uses ** for bold instead of *)."""
    lines = ["📚 **Bookswagon Price Report**", ""]
    for r in results:
        if r["error"]:
            lines.append(f"❌ **{r['name']}**: Could not fetch price")
            lines.append(f"   Error: {r['error'][:100]}")
        else:
            lines.append(f"📖 **{r['name']}**: ₹{r['price']}")
            lines.append(f"   🔗 {r['url']}")
        lines.append("")
    return "\n".join(lines)


# ─── Notification Channels ────────────────────────────────────────────

def send_telegram(message):
    """Send message via Telegram Bot API. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⏭️  Telegram: skipped (secrets not configured)")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        print("✅ Telegram: sent")
    else:
        print(f"❌ Telegram: failed — {resp.status_code} {resp.text[:200]}")


def send_discord(message):
    """Send message via Discord webhook. Requires DISCORD_WEBHOOK_URL."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⏭️  Discord: skipped (secret not configured)")
        return

    payload = {"content": message}
    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.ok:
        print("✅ Discord: sent")
    else:
        print(f"❌ Discord: failed — {resp.status_code} {resp.text[:200]}")


def send_ntfy(message):
    """Send mobile push via ntfy.sh. Requires NTFY_TOPIC."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("⏭️  ntfy: skipped (secret not configured)")
        return

    # Strip markdown formatting for plain-text push notification
    plain = message.replace("*", "").replace("**", "")
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=plain.encode("utf-8"),
        headers={"Title": "Bookswagon Price Alert", "Priority": "default"},
        timeout=10,
    )
    if resp.ok:
        print("✅ ntfy: sent")
    else:
        print(f"❌ ntfy: failed — {resp.status_code} {resp.text[:200]}")


# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    books = load_books()
    print(f"Tracking {len(books)} book(s)...\n")

    results = fetch_all_prices(books)

    # Build messages
    tg_message = build_message(results)
    discord_message = build_discord_message(results)

    print("\n--- Report ---")
    print(tg_message)

    # Send notifications
    print("\n--- Sending Notifications ---")
    send_telegram(tg_message)
    send_discord(discord_message)
    send_ntfy(tg_message)