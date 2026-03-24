#!/usr/bin/env python3
# ============================================================
#
#   Telegram Auto Leave
#   Automatically leaves inactive groups & channels
#
#   Author  : Bores
#   Telegram: @AirdropUmbrellaX
#   GitHub  : github.com/AirdropUmbrellaX
#
#   Use responsibly. Do not abuse Telegram's API.
#
# ============================================================

import asyncio
import json
import logging
import os
import sys
import time
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, errors
from telethon.tl.types import (
    Channel, Chat,
    InputPeerChannel, InputPeerChat,
)
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import DeleteChatUserRequest, GetHistoryRequest

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
CONFIG_PATH     = BASE_DIR / "config" / "accounts.json"
SESSIONS_DIR    = BASE_DIR / "sessions"
LOGS_DIR        = BASE_DIR / "logs"
INACTIVE_DAYS   = 90          # 3 months
DELAY_MIN       = 3.0         # seconds between actions
DELAY_MAX       = 7.0
BATCH_DELAY_MIN = 10.0        # seconds between batches
BATCH_DELAY_MAX = 20.0
BATCH_SIZE      = 10          # process N dialogs before a longer pause


# ─────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────
def setup_logging(account_id: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger(account_id)
    logger.setLevel(logging.DEBUG)

    # File handler — full detail
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Console handler — info only, coloured
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter())

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG:    "\033[90m",   # grey
        logging.INFO:     "\033[0m",    # default
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[35m",   # magenta
    }
    RESET = "\033[0m"
    PREFIX = {
        logging.INFO:    "  ℹ",
        logging.WARNING: "  ⚠",
        logging.ERROR:   "  ✖",
        logging.DEBUG:   "  ·",
    }

    def format(self, record):
        color  = self.COLORS.get(record.levelno, self.RESET)
        prefix = self.PREFIX.get(record.levelno, "")
        record.msg = f"{color}{prefix}  {record.msg}{self.RESET}"
        return super().format(record)


# ─────────────────────────────────────────────
# Config Loader
# ─────────────────────────────────────────────
def load_config(path: Path) -> list[dict]:
    if not path.exists():
        sample = [
            {
                "account_id":   "account1",
                "api_id":       123456,
                "api_hash":     "your_api_hash_here",
                "phone":        "+628123456789",
                "session_file": "account1"
            }
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample, indent=2))
        print(f"\n[!] Config file created at: {path}")
        print("[!] Please fill in your account details and re-run the script.\n")
        sys.exit(0)

    with open(path, encoding="utf-8") as f:
        accounts = json.load(f)

    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Config must be a non-empty JSON array of account objects.")

    required = {"account_id", "api_id", "api_hash", "phone"}
    for idx, acc in enumerate(accounts):
        missing = required - acc.keys()
        if missing:
            raise ValueError(f"Account #{idx+1} is missing fields: {missing}")

    return accounts


# ─────────────────────────────────────────────
# Core Functions
# ─────────────────────────────────────────────
def random_delay(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


async def get_last_message_date(client: TelegramClient, dialog) -> Optional[datetime]:
    """Return the date of the most recent message in a dialog, or None."""
    try:
        history = await client(GetHistoryRequest(
            peer      = dialog.input_entity,
            limit     = 1,
            offset_id = 0,
            offset_date = None,
            add_offset  = 0,
            max_id      = 0,
            min_id      = 0,
            hash        = 0,
        ))
        if history.messages:
            return history.messages[0].date
        return None
    except errors.ChatAdminRequiredError:
        return None
    except Exception:
        return None


async def leave_dialog(client: TelegramClient, dialog, logger: logging.Logger) -> bool:
    """Leave a group or channel. Returns True on success."""
    entity = dialog.entity
    name   = dialog.name or "Unnamed"

    try:
        if isinstance(entity, Channel):
            await client(LeaveChannelRequest(entity))
        elif isinstance(entity, Chat):
            me = await client.get_me()
            await client(DeleteChatUserRequest(
                chat_id = entity.id,
                user_id = me.id,
            ))
        else:
            return False

        logger.info(f"LEFT  ✓  [{entity.id}] {name}")
        return True

    except errors.FloodWaitError as e:
        logger.warning(f"FloodWait {e.seconds}s — sleeping...")
        await asyncio.sleep(e.seconds + 5)
        return False
    except errors.UserNotParticipantError:
        logger.debug(f"Already not a participant: {name}")
        return True
    except Exception as ex:
        logger.error(f"Failed to leave '{name}': {ex}")
        return False


async def process_account(account: dict, dry_run: bool, logger: logging.Logger) -> dict:
    """Process a single Telegram account."""
    session_path = SESSIONS_DIR / account.get("session_file", account["account_id"])
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(
        str(session_path),
        account["api_id"],
        account["api_hash"],
        device_model    = "Desktop",
        system_version  = "Windows 11",
        app_version     = "4.16.4",
        lang_code       = "en",
        system_lang_code= "en-US",
    )

    stats = {
        "account"  : account["account_id"],
        "checked"  : 0,
        "left"     : 0,
        "skipped"  : 0,
        "errors"   : 0,
        "left_list": [],
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS)

    try:
        await client.start(phone=account["phone"])
        me = await client.get_me()
        logger.info(f"Logged in as: {me.first_name} (@{me.username})")

        logger.info("Fetching all dialogs…")
        dialogs = await client.get_dialogs(limit=None)

        groups_channels = [
            d for d in dialogs
            if isinstance(d.entity, (Channel, Chat))
            and not (isinstance(d.entity, Channel) and d.entity.broadcast and d.entity.creator)
        ]

        logger.info(f"Found {len(groups_channels)} groups/channels to evaluate.")

        for i, dialog in enumerate(groups_channels, 1):
            name = dialog.name or "Unnamed"
            stats["checked"] += 1

            # Batch pause
            if i > 1 and (i - 1) % BATCH_SIZE == 0:
                logger.info(f"Batch pause after {i-1} dialogs…")
                random_delay(BATCH_DELAY_MIN, BATCH_DELAY_MAX)

            logger.debug(f"[{i}/{len(groups_channels)}] Checking: {name}")

            last_date = await get_last_message_date(client, dialog)

            if last_date is None:
                # No messages — treat as inactive
                is_inactive = True
                last_str = "no messages"
            else:
                is_inactive = last_date < cutoff
                last_str = last_date.strftime("%Y-%m-%d")

            if not is_inactive:
                stats["skipped"] += 1
                logger.debug(f"Active (last: {last_str}) — skip: {name}")
                random_delay(0.5, 1.5)
                continue

            logger.info(f"Inactive (last: {last_str}) → leaving: {name}")

            if dry_run:
                logger.info(f"[DRY RUN] Would leave: {name}")
                stats["left"] += 1
                stats["left_list"].append({"id": dialog.entity.id, "name": name, "last_message": last_str})
            else:
                success = await leave_dialog(client, dialog, logger)
                if success:
                    stats["left"] += 1
                    stats["left_list"].append({"id": dialog.entity.id, "name": name, "last_message": last_str})
                else:
                    stats["errors"] += 1

            random_delay(DELAY_MIN, DELAY_MAX)

    except errors.SessionPasswordNeededError:
        logger.error("Two-step verification is enabled. Please add 'password' to config.")
        stats["errors"] += 1
    except errors.PhoneNumberInvalidError:
        logger.error("Invalid phone number in config.")
        stats["errors"] += 1
    except Exception as ex:
        logger.error(f"Unexpected error: {ex}")
        stats["errors"] += 1
    finally:
        await client.disconnect()

    return stats


# ─────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────
def print_report(all_stats: list[dict]) -> None:
    print("\n" + "═" * 60)
    print("  📊  SUMMARY REPORT")
    print("═" * 60)

    for s in all_stats:
        print(f"\n  Account : {s['account']}")
        print(f"  Checked : {s['checked']}")
        print(f"  Left    : {s['left']}")
        print(f"  Skipped : {s['skipped']} (still active)")
        print(f"  Errors  : {s['errors']}")

        if s["left_list"]:
            print("\n  Groups/Channels left:")
            for item in s["left_list"]:
                print(f"    · [{item['id']}] {item['name']}  (last: {item['last_message']})")

    print("\n" + "═" * 60 + "\n")

    # Save JSON report
    report_path = LOGS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)
    print(f"  Report saved: {report_path}\n")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="Telegram Auto Leave — removes inactive groups/channels (3+ months)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--config", type=Path, default=CONFIG_PATH,
        help=f"Path to accounts config JSON (default: {CONFIG_PATH})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate only — do NOT actually leave any group/channel"
    )
    parser.add_argument(
        "--account", type=str, default=None,
        help="Run only for a specific account_id"
    )
    parser.add_argument(
        "--days", type=int, default=INACTIVE_DAYS,
        help=f"Inactivity threshold in days (default: {INACTIVE_DAYS})"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    global INACTIVE_DAYS
    INACTIVE_DAYS = args.days

    print("\n" + "═" * 60)
    print("  🤖  Telegram Auto Leave")
    print(f"  Threshold : {INACTIVE_DAYS} days of inactivity")
    print(f"  Dry Run   : {'YES — no changes will be made' if args.dry_run else 'NO — will actually leave'}")
    print("═" * 60 + "\n")

    accounts = load_config(args.config)

    if args.account:
        accounts = [a for a in accounts if a["account_id"] == args.account]
        if not accounts:
            print(f"[!] No account found with id: {args.account}")
            sys.exit(1)

    all_stats = []

    for i, account in enumerate(accounts, 1):
        acc_id = account["account_id"]
        logger = setup_logging(acc_id)

        print(f"\n{'─'*60}")
        logger.info(f"Processing account {i}/{len(accounts)}: {acc_id}")
        print(f"{'─'*60}")

        stats = await process_account(account, dry_run=args.dry_run, logger=logger)
        all_stats.append(stats)

        if i < len(accounts):
            wait = random.uniform(15, 30)
            logger.info(f"Waiting {wait:.0f}s before next account…")
            await asyncio.sleep(wait)

    print_report(all_stats)


if __name__ == "__main__":
    asyncio.run(main())
