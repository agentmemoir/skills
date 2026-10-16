# Third-party material

This repository is MIT (see [`LICENSE`](LICENSE)). One thing in it ships verbatim, and one is distilled from published standards.

## 1. Vendored: the humanizer catalog

`skills/writing/wordsmith/references/voice-and-tells.md` embeds the pattern catalog from **blader/humanizer**, verbatim, between `BEGIN GENERATED` and `END GENERATED` markers.

| | |
|---|---|
| Source | <https://github.com/blader/humanizer> |
| License | MIT, © 2025 Siqi Chen — shipped at `skills/writing/wordsmith/references/upstream/humanizer-LICENSE.txt` so an installed skill carries the notice with it |
| Pinned at | the release, commit, and content digest in `skills/writing/wordsmith/references/upstream/humanizer.json` |
| Upstream snapshot | `skills/writing/wordsmith/references/upstream/humanizer-<version>.SKILL.md` — the exact bytes we vendored from |
| Derives from | Wikipedia, ["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup |

**Never edit the generated region by hand.** `npm run sync:humanizer` regenerates it from the snapshot, and `npm test` fails when the file and the pin disagree. To adopt a newer upstream release run `npm run update:humanizer`, then work the review list at the end of `voice-and-tells.md`. A weekly workflow (`.github/workflows/humanizer-upstream.yml`) files an issue when upstream moves while we are idle.

## 2. Referenced, not vendored: the documentation method

Wordsmith's 28 style rules are **distilled** from published standards; no text is reproduced. Per-rule sources live in `skills/writing/wordsmith/references/research-notes.md`:

- **Diátaxis** — page types, and the reference quadrant's completeness obligation
- the **Google** and **Microsoft** developer style guides — prose rules, minimum viable documentation, duplication
- **Carroll's minimalism** and **Every Page Is Page One** — what to cut, why pages stand alone
- **standard-readme** and the **Good Docs Project** — artifact shapes and the template catalogue
- **GitLab's docs workflow** and **Keep a Changelog** — docs in the same change as code, release notes as content

Referenced sources carry no vendored text, so they need no license file. If a future change copies anything verbatim, it belongs under section 1 with its own notice.
