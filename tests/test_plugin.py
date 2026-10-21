"""Plugin on journal events: question images go to the spool as a telegram.album fact, once per question, also
after a restart."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import journal, spool  # noqa: E402

import main  # noqa: E402


class Plugin(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tgci-")
        os.environ["HUB_STATE_DIR"] = self.dir   # not the live hub
        self.j = journal.Journal(os.path.join(self.dir, "journal.jsonl"))
        self.j.append("session.requested", "w", {"cwd": "/w", "session_id": "w"})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def ask(self, rid, question, options=None, multi=True):
        self.j.append("permission.requested", "w", {"request_id": rid, "tool": "AskUserQuestion", "input": {
            "questions": [{"question": question, "multiSelect": multi, "options": options or [{"label": "All"}]}]}})

    def taken(self):
        d = os.path.join(self.dir, "spool")
        out = [e for _, e in spool.take(d)]
        for n in os.listdir(d) if os.path.isdir(d) else []:
            os.unlink(os.path.join(d, n))
        return out

    def test_pictures_in_question_and_options_become_an_album(self):
        p = main.Plugin(self.dir)
        self.ask("r1", "Which icons do we take?\n- Frutiger, blue `/w/icons/a.png`\n- `/w/icons/b 2.jpg`\n"
                       "- Frutiger, blue `/w/icons/c.png`\nboth /w/x.webp and /w/y.png", [
                           {"label": "First", "description": "here it is `/w/opt/1.png`"},
                           {"label": "No picture", "description": "text"}])
        self.ask("r2", "No pictures?", [{"label": "Yes"}])
        self.j.append("permission.requested", "w", {"request_id": "r3", "tool": "Bash", "input": {"command": "ls /w/a.png"}})
        p.poll()
        got = self.taken()
        self.assertEqual(len(got), 1)
        ev = got[0]
        self.assertEqual((ev["type"], ev["entity"], ev["src"], ev["data"]["request_id"], ev["data"]["q"]),
                         ("telegram.album", "w", "ext:tg-choice-images", "r1", 0))
        self.assertEqual([(i["path"], i["caption"]) for i in ev["data"]["items"]], [
            ("/w/icons/a.png", "Frutiger, blue"), ("/w/icons/b 2.jpg", "b 2"),
            ("/w/icons/c.png", "Frutiger, blue (2)"), ("/w/x.webp", "x"), ("/w/y.png", "y"),
            ("/w/opt/1.png", "First")])
        self.assertTrue(ev["data"]["pick"])   # images listed in the question - a button for each

    def test_first_start_skips_old_questions_and_restart_does_not_repeat(self):
        self.ask("old", "- a `/w/a.png`")
        p = main.Plugin(self.dir)
        p.poll()
        self.assertEqual(self.taken(), [])   # a question from before the first run - do not send
        self.ask("r1", "- a `/w/a.png`")
        p.poll()
        self.assertEqual(len(self.taken()), 1)
        self.ask("r2", "- b `/w/b.png`")   # arrived while the plugin was down
        p = main.Plugin(self.dir)
        p.poll()
        self.assertEqual([e["data"]["request_id"] for e in self.taken()], ["r2"])
        self.ask("r1", "- a `/w/a.png`")   # the same question again in the journal (hook repeat) - do not repeat
        p.poll()
        self.assertEqual(self.taken(), [])


if __name__ == "__main__":
    unittest.main()
