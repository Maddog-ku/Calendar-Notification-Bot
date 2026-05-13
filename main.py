import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import caldav
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

ICLOUD_USERNAME = os.environ["ICLOUD_USERNAME"]
ICLOUD_APP_PASSWORD = os.environ["ICLOUD_APP_PASSWORD"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
TIMEZONE = os.environ.get("TZ", "Asia/Taipei")
NOTIFY_HOUR = int(os.environ.get("NOTIFY_HOUR", "8"))
NOTIFY_MINUTE = int(os.environ.get("NOTIFY_MINUTE", "0"))

CALDAV_URL = "https://caldav.icloud.com"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("calendar-bot")


def fetch_today_events(tz: ZoneInfo) -> list[dict]:
    now = datetime.now(tz)
    start = datetime.combine(now.date(), time.min, tzinfo=tz)
    end = start + timedelta(days=1)

    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=ICLOUD_USERNAME,
        password=ICLOUD_APP_PASSWORD,
    )
    principal = client.principal()

    events: list[dict] = []
    for calendar in principal.calendars():
        try:
            results = calendar.search(start=start, end=end, event=True, expand=True)
        except Exception as e:
            log.warning("Skip calendar %s: %s", calendar.name, e)
            continue

        for item in results:
            vevent = item.icalendar_component
            summary = str(vevent.get("summary", "(無標題)"))
            location = str(vevent.get("location", "") or "")
            dtstart = vevent.get("dtstart").dt
            dtend_raw = vevent.get("dtend")
            dtend = dtend_raw.dt if dtend_raw else None

            all_day = not isinstance(dtstart, datetime)
            if isinstance(dtstart, datetime):
                dtstart = dtstart.astimezone(tz)
            if isinstance(dtend, datetime):
                dtend = dtend.astimezone(tz)

            events.append({
                "summary": summary,
                "location": location,
                "start": dtstart,
                "end": dtend,
                "all_day": all_day,
            })

    events.sort(key=lambda e: (
        not e["all_day"],
        e["start"] if isinstance(e["start"], datetime) else datetime.combine(e["start"], time.min, tzinfo=tz),
    ))
    return events


def format_message(events: list[dict], tz: ZoneInfo) -> str:
    today_str = datetime.now(tz).strftime("%Y-%m-%d (%a)")
    header = f"**📅 今日行程 {today_str}**"

    if not events:
        return f"{header}\n\n今天沒有安排，好好休息 ☕"

    lines = [header, ""]
    for e in events:
        if e["all_day"]:
            time_part = "全天"
        else:
            start_s = e["start"].strftime("%H:%M")
            end_s = e["end"].strftime("%H:%M") if isinstance(e["end"], datetime) else ""
            time_part = f"{start_s}–{end_s}" if end_s else start_s

        loc = f"  📍 {e['location']}" if e["location"] else ""
        lines.append(f"• `{time_part}`  {e['summary']}{loc}")

    return "\n".join(lines)


def send_to_discord(content: str) -> None:
    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": content},
        timeout=15,
    )
    resp.raise_for_status()


def run_job() -> None:
    tz = ZoneInfo(TIMEZONE)
    log.info("Fetching today's events...")
    try:
        events = fetch_today_events(tz)
        message = format_message(events, tz)
        send_to_discord(message)
        log.info("Sent %d event(s) to Discord.", len(events))
    except Exception:
        log.exception("Job failed")
        try:
            send_to_discord("⚠️ 行事曆通知 bot 執行失敗，請檢查 log。")
        except Exception:
            log.exception("Failed to send error notification")


def main() -> None:
    tz = ZoneInfo(TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        run_job,
        CronTrigger(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE, timezone=tz),
        id="daily_notify",
        misfire_grace_time=3600,
    )
    log.info(
        "Scheduler started. Daily notify at %02d:%02d %s",
        NOTIFY_HOUR, NOTIFY_MINUTE, TIMEZONE,
    )

    if os.environ.get("RUN_ON_START") == "1":
        run_job()

    scheduler.start()


if __name__ == "__main__":
    main()
