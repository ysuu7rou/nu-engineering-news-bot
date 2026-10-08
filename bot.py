"""Nagoya Engineering News to Slack; standard library only."""
import base64
import html
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SITE = "https://www.engg.nagoya-u.ac.jp"
STATE_PATH = "data/state.json"


def request_json(url, payload=None, headers=None, method=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers or {}, method=method)
    with urlopen(req, timeout=40) as response:
        return json.load(response)


def fetch_news():
    # Both are the public endpoints used by the university website itself.
    combined = {}
    for suffix in ("", "/past"):
        result = request_json(SITE + "/app/api/news/public" + suffix)
        records = result.get("allNews")
        if not isinstance(records, list):
            raise ValueError("University news schema changed; posting stopped")
        for item in records:
            if item.get("news_categories", {}).get("language") != "ja":
                continue
            if item.get("deleted_at") or not isinstance(item.get("title"), str):
                continue
            if not item["title"].strip() or not isinstance(item.get("id"), int):
                raise ValueError("Invalid news entry; posting stopped")
            combined[str(item["id"])] = item
    if not combined:
        raise ValueError("Empty Japanese news feed; posting stopped")
    return combined


def slack_text(item):
    # Escape Slack control characters and disable mention/link auto-parsing.
    title = html.unescape(item["title"]).strip()
    title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"📢 名古屋大学 工学部・工学研究科 News\n{title}\n<{SITE}/news.html?id={item['id']}|🔗 お知らせを読む>"


class StateStore:
    def __init__(self):
        repo = os.environ["GITHUB_REPOSITORY"]
        self.url = f"https://api.github.com/repos/{repo}/contents/{STATE_PATH}"
        self.branch = os.environ["GITHUB_REF_NAME"]
        self.headers = {
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "nuee-announce-news-monitor",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.sha = None

    def read(self):
        from urllib.parse import quote
        try:
            data = request_json(self.url + "?ref=" + quote(self.branch, safe=""), headers=self.headers)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        self.sha = data["sha"]
        state = json.loads(base64.b64decode(data["content"]))
        if state.get("version") != 1 or not isinstance(state.get("seen"), list):
            raise ValueError("Invalid stored state; posting stopped")
        return state

    def write(self, state):
        payload = {
            "message": "Update news delivery state [skip ci]",
            "branch": self.branch,
            "content": base64.b64encode(json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
        }
        if self.sha:
            payload["sha"] = self.sha
        result = request_json(self.url, payload, self.headers, "PUT")
        self.sha = result["content"]["sha"]


def deliver(news, store, send):
    state = store.read()
    if state is None:
        store.write({"version": 1, "seen": sorted(news), "pending": None})
        print(f"Initialized with {len(news)} existing articles; no posts sent")
        return
    if state.get("pending"):
        raise RuntimeError("Previous delivery outcome needs manual verification; not resending")
    seen = set(state["seen"])
    fresh = [entry for key, entry in news.items() if key not in seen]
    fresh.sort(key=lambda entry: (entry.get("created_at") or "", entry["id"]))
    for item in fresh:
        key = str(item["id"])
        # Persist intent before sending. Ambiguous outcomes are never retried.
        state["pending"] = {"id": key, "url": SITE + "/news.html?id=" + key}
        store.write(state)
        send(item)
        seen.add(key)
        state["seen"] = sorted(seen)
        state["pending"] = None
        store.write(state)
        print("Delivered article ID " + key)
    if not fresh:
        print("No new articles")


def send_slack(item):
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook.startswith("https://hooks.slack.com/services/"):
        raise ValueError("SLACK_WEBHOOK_URL must be set to the nuee-announce webhook")
    payload = {"text": slack_text(item), "unfurl_links": False, "unfurl_media": False, "parse": "none"}
    req = Request(webhook, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            if response.status != 200 or response.read().strip() != b"ok":
                raise RuntimeError("Slack did not confirm delivery")
    except Exception:
        # Never put the credential-bearing URL into logs.
        raise RuntimeError("Slack delivery unconfirmed; inspect channel and pending state before resuming") from None


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--preview" in sys.argv:
        articles = fetch_news()
        latest = max(articles.values(), key=lambda item: (item.get("created_at") or "", item["id"]))
        print(f"Read {len(articles)} Japanese articles. Preview only; no Slack post.")
        print(slack_text(latest))
    else:
        if not os.environ.get("SLACK_WEBHOOK_URL"):
            raise RuntimeError("Configure the channel webhook before enabling the schedule")
        deliver(fetch_news(), StateStore(), send_slack)
