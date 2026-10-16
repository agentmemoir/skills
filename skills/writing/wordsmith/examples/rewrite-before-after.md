# Example rewrite — before / after

A worked example showing the style guide rules doing real work. The passage below is the kind of README intro that accumulates naturally; the rewrite is what `STYLE_GUIDE.md` + `templates/README.template.md` produce instead. Rule numbers refer to the style guide.

## Before

```markdown
## Introduction

Welcome to Deployer! 🎉 Deployer is a powerful, blazingly-fast, and flexible
deployment orchestration tool that was designed from the ground up to make
your deployment workflows as smooth and painless as possible. In today's
fast-paced software landscape, teams need tools that keep up with the demands
of modern continuous delivery pipelines, and Deployer rises to that challenge
with an elegant, intuitive interface.

It should be noted that Deployer is built on a robust, event-driven plugin
architecture, which allows for maximum extensibility while maintaining
simplicity at its core.

In order to get started, at this point in time you will want to make sure
that Node.js is installed on your system. Once you have completed the
installation of Node.js, Deployer can then be installed using npm, after
which you will be able to begin exploring its extensive feature set...
```

## After

```markdown
## Introduction

Deployer runs your deployment workflow: build, migrate, ship, roll back.
Built for teams deploying to multiple servers from one config file.

Requires Node.js 20+.

```bash
npm install -g deployer
deployer init     # creates deploy.yml
deployer run      # executes the pipeline
```

Full docs: [quickstart](…) · [how-to guides](…) · [CLI reference](…)
```

## What changed, and which rule did it

| Change | Rule |
|---|---|
| Deleted the welcome, the adjectives ("powerful", "blazingly-fast"), and the market commentary — none of it actionable | S24 (cut what the reader can't act on), S3 (use measurable words) |
| First sentence now says what it does, concretely: four verbs the reader will use | S9 (front-load), S8 (outcome first) |
| "It should be noted that…", "In order to…", "at this point in time…", "Once you have completed…" — all gone | S5 (filler list) |
| "you will be able to begin exploring" → the reader just runs three commands | S1 (present tense, active voice) |
| Code sample first, and it ends in a verifiable state (`deployer run`) | S13 (code before prose), S16 (one block, one outcome) |
| Node.js requirement moved from prose to a line the scanner catches | S11 (write for scanning) |
| Plugin-architecture praise deleted; if the design matters, it lives in an explanation page on the site | S7 (one page, one job), S19 (site owns explanation) |
| Page now fits on one screen and links out | S18 (README is a landing page), S22 (minimum viable docs) |

## The pattern to take away

The rewrite didn't compress the original — it replaced it. The before-passage spends ~120 words *describing a tool the reader hasn't used yet*; the after-passage spends ~30 words *getting the reader to use it*. That is the whole difference between docs that respect the reader's time and docs that consume it: every sentence either helps the reader act, decide, or find the next page — or it goes.
