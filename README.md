# Question images in Telegram: an Agents Hub plugin

A session asks you which of several pictures to take, and the pictures themselves arrive in Telegram: as an album, replying to the question card, each with a caption. Selection buttons sit under the album: for pictures listed in the question, one button per picture - mark as many as you need and press "Done", and their captions go back as the answer, comma-separated (like the choice-images grid plugin on the page). Pictures in option descriptions become option buttons, like on the card. Marks are shared with the card; once answered, the buttons are removed from both.

The plugin takes pictures from the question:

- listed in the question text, one picture per line: ``- Blue `/path/to/a.png` `` - the caption is "Blue" (with no text, the file name). The choice-images page plugin understands the same format;
- from an option description: a picture path in the description - captioned with the option label.

An album holds up to 10 pictures; more go in several albums. A file over 10 MB or not an image (png, jpg, webp) is reported as a line under the album.

## Install

"Settings" -> "Plugins" -> paste the link to this repository -> "Check and install". You need a hub with Telegram whose module accepts the `telegram.album` fact. On a hub without it the plugin changes nothing: the question card arrives as before.

## Tests

```
PYTHONPATH=<hub code folder> python3 -m unittest discover -s tests
```

The plugin sends no text of its own to Telegram (captions come from the question), so it has no language-dependent strings; only the manifest description is bilingual (`i18n.ru` in `hub-plugin.json`).

Icon — [3D Fluency](https://icons8.com/icons/3d-fluency) by Icons8.
