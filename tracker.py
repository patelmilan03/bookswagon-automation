import json
import os
import sys
import time

import requests
import cloudscraper
from bs4 import BeautifulSoup


# cloudscraper mimics a real browser's TLS fingerprint to bypass anti-bot
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "desktop": True}
)


def get_price(url, retries=2):
    """Fetch the selling price from a Bookswagon product page."""
    api_key = os.environ.get("SCRAPER_API_KEY")

    for attempt in range(retries + 1):
        try:
            if api_key:
                # Route through ScraperAPI to bypass IP blocks in CI.
                # Timeout is generous because ScraperAPI's own anti-bot
                # bypass for protected sites can take well over 30s.
                payload = {'api_key': api_key, 'url': url}
                resp = requests.get('https://api.scraperapi.com', params=payload, timeout=70)
            else:
                # Local execution using cloudscraper
                resp = scraper.get(url, timeout=20)

            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            price_el = soup.find(class_="originalprice")
            if not price_el:
                raise ValueError("Could not find price element (class='originalprice') on page")

            price_text = price_el.text.strip()
            clean_price = float(price_text.replace('₹', '').replace(',', '').strip())
            return clean_price
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 429 and attempt < retries:
                retry_after = e.response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.strip().isdigit() else 3 * (attempt + 1)
                print(f"    ⚠️  Rate limited (429), retrying in {wait}s...")
                time.sleep(wait)
            elif attempt < retries:
                wait = 3 * (attempt + 1)
                print(f"    ⚠️  Attempt {attempt + 1} failed, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < retries:
                wait = 3 * (attempt + 1)
                print(f"    ⚠️  Attempt {attempt + 1} failed, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def load_books():
    """Load book list from books.json (same directory as this script)."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _history_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_history.json")


def load_history():
    """Load last-seen prices per book URL (same directory as this script)."""
    path = _history_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    """Persist last-seen prices per book URL."""
    with open(_history_path(), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def fetch_all_prices(books, history):
    """Fetch prices for all books, comparing against history for drops.

    Mutates `history` in place with the latest prices. Returns list of dicts
    with name, url, price/error, previous_price, dropped.
    """
    results = []
    for i, book in enumerate(books):
        name = book["name"]
        url = book["url"]
        try:
            price = get_price(url)
            previous_price = history.get(url, {}).get("price")
            dropped = previous_price is not None and price < previous_price
            results.append({
                "name": name,
                "url": url,
                "price": price,
                "error": None,
                "previous_price": previous_price,
                "dropped": dropped,
            })
            history[url] = {"price": price}
            if dropped:
                print(f"  📉 {name}: ₹{previous_price} → ₹{price}")
            else:
                print(f"  ✅ {name}: ₹{price}")
        except Exception as e:
            results.append({
                "name": name,
                "url": url,
                "price": None,
                "error": str(e),
                "previous_price": None,
                "dropped": False,
            })
            print(f"  ❌ {name}: Failed — {e}")
        # Small delay between requests to avoid rate limiting
        if i < len(books) - 1:
            time.sleep(2)
    return results


def build_message(results):
    """Build a formatted price report message (Telegram Markdown)."""
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


def build_drop_alert(results, bold="*"):
    """Build a standalone alert message for books whose price just dropped.

    Returns None if nothing dropped this run.
    """
    dropped = [r for r in results if r["dropped"]]
    if not dropped:
        return None

    lines = [f"{bold}📉 Price Drop Alert!{bold}", ""]
    for r in dropped:
        lines.append(f"📖 {bold}{r['name']}{bold}: ₹{r['previous_price']} → ₹{r['price']}")
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
    plain = message.replace("*", "")
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
    history = load_history()
    print(f"Tracking {len(books)} book(s)...\n")

    results = fetch_all_prices(books, history)
    save_history(history)

    # Immediate alert on price drops, regardless of digest schedule
    drop_alert_tg = build_drop_alert(results, bold="*")
    if drop_alert_tg:
        print("\n--- Sending Price Drop Alerts ---")
        send_telegram(drop_alert_tg)
        send_discord(build_drop_alert(results, bold="**"))
        send_ntfy(drop_alert_tg)

    # Full digest: always on local runs; on GitHub Actions only on the
    # evening run (SEND_DIGEST=false skips it for the morning run).
    send_digest = os.environ.get("SEND_DIGEST", "true").lower() == "true"
    if send_digest:
        tg_message = build_message(results)
        discord_message = build_discord_message(results)

        print("\n--- Report ---")
        print(tg_message)

        print("\n--- Sending Digest Notifications ---")
        send_telegram(tg_message)
        send_discord(discord_message)
        send_ntfy(tg_message)
    else:
        print("\n--- Skipping digest (morning run) ---")