"""Process of the "Question images in Telegram" plugin: reads the hub journal; for a session question (AskUserQuestion)
with images - paths listed in the question text (as in the choice-images plugin) or in option descriptions - it sends
the core a telegram.album fact: the Telegram bot posts them as an album replying to the question card, with the same
buttons under it. It does not touch the core: it reads the journal and writes only a fact to the spool (EXTENDING.md)."""
import json
import os
import re
import sys
import time

from core import journal, spool

NAME = os.environ.get("HUB_EXTENSION", "tg-choice-images")
IMAGE = r"\.(?:png|jpe?g|gif|webp)"
# full path (posix or C:\...) to an image, spaces allowed: up to an extension not followed by a letter or a dot
PATH = re.compile(r"((?:/|[A-Za-z]:[\\/])[^\n`\"'<>|]*?" + IMAGE + r")(?![\w.])", re.I)
KEEP = 500   # how many handled questions to remember


def stem(path):
    return os.path.splitext(re.split(r"[\\/]", path)[-1])[0]


def paths_in(text):
    return list(dict.fromkeys(m.group(1).strip() for m in PATH.finditer(text or "")))


def from_question(text):
    """Images from the question text: a line with one image - caption is its text without the path ("- MJ-3:2 `/path`"
    -> "MJ-3:2"); with no text, or several images in a line - the file name. Equal captions get a number."""
    items = []
    for line in (text or "").split("\n"):
        paths = paths_in(line)
        rest = line
        for p in paths:
            rest = rest.replace(p, "")
        rest = re.sub(r"[`*_]", "", rest)
        rest = re.sub(r"\s+", " ", rest).strip(" -–—:·•,.\t")
        items += [{"path": p, "caption": rest if len(paths) == 1 and rest else stem(p)} for p in paths]
    seen = {}
    for it in items:
        seen[it["caption"]] = n = seen.get(it["caption"], 0) + 1
        if n > 1:
            it["caption"] += f" ({n})"
    return items


def from_options(options):
    """An image in an option description - captioned with the option label (several - "label - file name")."""
    items = []
    for o in options or []:
        label, paths = o.get("label") or "", paths_in(o.get("description"))
        items += [{"path": p, "caption": label if len(paths) == 1 else f"{label} — {stem(p)}"} for p in paths]
    return items


def albums(data):
    """[(question number, images, pick)] for a permission.requested AskUserQuestion; pick - images listed in the question
    text (as in choice-images): the bot gives a button per image, the answer is the captions of the marked ones."""
    if data.get("tool") != "AskUserQuestion":
        return []
    out = []
    for qi, q in enumerate((data.get("input") or {}).get("questions") or []):
        items, seen, listed = [], set(), from_question(q.get("question"))
        for it in listed + from_options(q.get("options")):
            if it["path"] not in seen:
                seen.add(it["path"])
                items.append(it)
        if items:
            out.append((qi, items, bool(listed)))
    return out


class Plugin:
    def __init__(self, state_dir):
        self.dir, self.path = state_dir, os.path.join(state_dir, "journal.jsonl")
        self.spool = os.path.join(state_dir, "spool")
        self.mine = os.path.join(state_dir, "tg-choice-images", "state.json")
        try:
            with open(self.mine, encoding="utf-8") as f:
                self.st = json.load(f)
        except (OSError, ValueError):
            self.st = None
        self.ino, self.offset = journal.identity(self.path), self.size()
        if self.st is None:   # first run - start from the journal end: do not send old questions
            last = journal.read_tail(self.path)
            self.st = {"seq": last[-1]["seq"] if last else 0, "done": []}
            self.save()
        else:   # was down meanwhile - catch up from the journal tail (do not repeat handled ones)
            self.handle(journal.read_tail(self.path))

    def size(self):
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def save(self):
        os.makedirs(os.path.dirname(self.mine), exist_ok=True)
        tmp = self.mine + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.st, f)
        os.replace(tmp, self.mine)

    def handle(self, events):
        changed = False
        for ev in events:
            if ev.get("seq", 0) <= self.st["seq"]:
                continue
            self.st["seq"], changed = ev["seq"], True
            data = ev.get("data") or {}
            rid = data.get("request_id")
            if ev.get("type") != "permission.requested" or not rid or rid in self.st["done"]:
                continue
            for qi, items, pick in albums(data):
                spool.put(self.spool, "telegram.album", ev.get("entity"),
                          {"request_id": rid, "q": qi, "items": items, **({"pick": True} if pick else {})},
                          src=f"ext:{NAME}")
            self.st["done"] = (self.st["done"] + [rid])[-KEEP:]
        if changed:
            self.save()

    def poll(self):
        ino = journal.identity(self.path)
        if ino != self.ino or self.size() < self.offset:   # journal started anew - read the new one from the start
            self.ino, self.offset = ino, 0
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except OSError:
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self.offset += end + 1
        events = []
        for line in chunk[:end].split(b"\n"):
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        self.handle(events)


def main():
    state = os.environ.get("HUB_STATE_DIR")
    if not state:
        sys.exit("HUB_STATE_DIR is required (the hub starts the plugin)")
    p = Plugin(state)
    while True:
        p.poll()
        time.sleep(1)


if __name__ == "__main__":
    main()
