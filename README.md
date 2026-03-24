# Telegram Auto Leave

A Python automation tool that leaves inactive Telegram groups and channels — built for multi-account use with safety delays and detailed logging.

Built with [Telethon](https://github.com/LonamiWebs/Telethon).

---

## Features

- Leaves groups and channels with no activity beyond a set threshold (default: 90 days)
- Multi-account support via a single JSON config file
- Dry run mode to preview results before making any changes
- Randomized delays between actions to stay within Telegram's rate limits
- Color-coded console output with per-account log files
- JSON summary report generated after each run

---

## Requirements

- Python 3.11+
- Telegram API credentials (see below)

---

## Installation

**Clone the repository**

```bash
git clone https://github.com/AirdropUmbrellaX/tg-auto-leave.git
cd tg-auto-leave
```

**Create a virtual environment** *(recommended)*

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

**Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Getting API Credentials

1. Open [https://my.telegram.org](https://my.telegram.org) and log in
2. Go to **API development tools**
3. Fill in the form — app name and platform are up to you
4. Copy the **App api_id** and **App api_hash**

> Never share your API credentials publicly.

---

## Configuration

Edit `config/accounts.json` with your account details:

```json
[
  {
    "account_id":   "main_account",
    "api_id":       123456,
    "api_hash":     "your_api_hash_here",
    "phone":        "+628123456789",
    "session_file": "main_account"
  },
  {
    "account_id":   "second_account",
    "api_id":       789012,
    "api_hash":     "your_api_hash_here",
    "phone":        "+628987654321",
    "session_file": "second_account"
  }
]
```

| Field | Description |
|---|---|
| `account_id` | A unique label for this account |
| `api_id` | From my.telegram.org |
| `api_hash` | From my.telegram.org |
| `phone` | Phone number in international format |
| `session_file` | Local session filename — keep it the same as `account_id` |

Using two-step verification? Add `"password": "your_2fa_password"` to the account entry.

---

## Usage

**Dry run** — always start with this to preview what will be left:

```bash
python main.py --dry-run
```

**Run all accounts:**

```bash
python main.py
```

**Run a specific account only:**

```bash
python main.py --account main_account
```

**Custom inactivity threshold:**

```bash
python main.py --days 60   # 2 months
python main.py --days 30   # 1 month
python main.py --days 180  # 6 months
```

**Combined flags:**

```bash
python main.py --dry-run --account main_account --days 60
```

---

## Output

- **Console** — real-time colored logs
- **Log files** — saved to `logs/<account_id>_<timestamp>.log`
- **JSON report** — saved to `logs/report_<timestamp>.json` at the end of each run

```
════════════════════════════════════════════════════
  Telegram Auto Leave
  Threshold : 90 days of inactivity
  Dry Run   : NO
════════════════════════════════════════════════════

  i  Logged in as: Bores (@AirdropUmbrellaX)
  i  Found 456 groups/channels to evaluate.
  i  Inactive (last: 2024-09-12) -> leaving: Old Group
  i  LEFT  [1234567890] Old Group

════════════════════════════════════════════════════
  SUMMARY REPORT
════════════════════════════════════════════════════

  Account : main_account
  Checked : 456
  Left    : 38
  Skipped : 415 (still active)
  Errors  : 3
```

---

## Project Structure

```
tg-auto-leave/
├── main.py              # Main script
├── requirements.txt     # Python dependencies
├── README.md
├── config/
│   └── accounts.json    # Account credentials (excluded from git)
├── sessions/            # Session files — auto-generated on first login
└── logs/                # Execution logs and reports — auto-generated
```

---

## Tips

- Always do a dry run before executing for real
- Keep sessions per run to around 30–40 groups maximum
- Run at most once a week per account
- Do not delete the `sessions/` folder — it stores your login state
- Avoid switching VPNs mid-session

---

## FAQ

**The script is asking for a code — is that normal?**  
Yes. On first login, Telegram sends a verification code to your Telegram app. Enter it in the terminal. After that, the session is saved and you won't be asked again.

**Are session files safe to store?**  
Session files contain authentication tokens, not passwords. Keep them private and do not share or upload them.

**What happens to private groups?**  
The script can still read message history for groups you're a member of. If a group throws a permission error, it gets treated as inactive.

---

## Credits

Created by **Bores**  
Telegram: [@AirdropUmbrellaX](https://t.me/AirdropUmbrellaX)
