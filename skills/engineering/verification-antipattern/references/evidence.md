# Evidence for the Thresholds and Facts

This file records what is published, what is measured, and what is merely convention. Use it when someone challenges a finding, or when the report needs a citation.

## The numbers, and their status

- **5 minutes** is the published ideal for a commit stage, from Humble & Farley, *Continuous Delivery* (2010): "The commit stage should ideally take less than five minutes to run, and certainly no more than ten minutes." The authors also state that the developer who checked in "waits for the results before moving on to the next task", while later pipeline stages "are lengthy activities". Status: professional guideline, not a measured harm point. Source: https://www.informit.com/articles/article.aspx?p=1621865&seqNum=4
- **10 minutes** is the most repeated published ceiling. Fowler, attributing Extreme Programming: "the XP guideline of a ten minute build is perfectly within reason", adding "every minute chiseled off the build time is a minute saved for each developer every time they commit". DORA's current capability page: developers should "get feedback from automated tests in less than ten minutes both on local workstations and from the continuous integration system". Hilton et al. (ESEC/FSE 2017, survey of 523 developers) found 10 minutes was "the most common answer" for maximum acceptable CI build time, while "Overly long build times" was a barrier for 38% of respondents and 78% had "actively worked to reduce their build times". Status: published guideline plus survey preference. Sources: https://martinfowler.com/articles/continuousIntegration.html, https://dora.dev/capabilities/test-automation/, https://mir.cs.illinois.edu/marinov/publications/HiltonETAL17TradeOffsInCI.pdf
- **7 minutes**: no published source for a 7-minute build or CI threshold was found. Treat it as a locally chosen line, not evidence.
- **15 minutes**: appears as Google's default timeout for large tests and similar platform rules, not as a statement that a 15-minute commit gate is acceptable. Treat it as a platform default, not a target.

The honest formulation: 5–10 minutes is above the published ideal but inside the published ceiling; over 10 minutes exceeds every major published guideline. The skill flags blocking gates above 5 minutes because the ideal is 5 and the cost of a wait is real, not because harm was measured at 5 minutes.

## What waits cost, with the caveats

- Task-switching costs are real but small per switch. Rubinstein, Meyer & Evans (2001) measured switch costs "sometimes just a few tenths of a second per switch". The often-quoted "40 percent of productive time" is an author's public remark (APA page), not a measured figure from the paper. Sources: https://www.apa.org/topics/research/multitasking, DOI 10.1037/0096-1523.27.4.763
- The popular "23 minutes and 15 seconds to refocus" is an average resumption time from Mark's CHI 2005 field study, in her own 2006 interview: interrupted work "was resumed, on average, in 23 minutes and 15 seconds". The variance is large, and the 2008 follow-up lab study found people "completed interrupted tasks in less time with no difference in quality" while reporting "more stress, higher frustration, time pressure and effort". Sources: https://news.gallup.com/businessjournal/23146/too-many-interruptions-work.aspx, https://ics.uci.edu/~gmark/chi08-mark.pdf
- Resumption in programming specifically: Parnin & Rugaber (2011) found "only 10% of the sessions have programming activity resume in less than 1 min after an interruption", and in about 30% of sessions the edit lag exceeded 30 minutes. This is about interruptions generally, not CI waits. Source: http://www.chrisparnin.me/pdf/parnin-sqj11.pdf
- CI waiting changes behavior: Durieux et al. (MSR 2020) found "in 54.42% of the restarted builds, the developers analyze and restart a build within an hour", and restarted builds slowed merging. Source: https://arxiv.org/pdf/2003.11772
- Real CI latencies are often far above the guideline: Beller, Gousios & Zaidman (MSR 2017) report a median build execution latency of 8.3 minutes across 2.64M builds, mean 19.6. Confidence: medium (indexed copy only). DOI 10.1109/MSR.2017.62
- Google accepts a practical submission wait near its guideline: *Software Engineering at Google* describes "the average wait time to submit a change is around 11 minutes", often run in the background, and presubmit tests limited to "only fast, reliable ones" because waiting for everything "can be severely disruptive, in some cases taking hours". Source: https://abseil.io/resources/swe-book/html/ch23.html

Do not use Nielsen's 0.1 s / 1 s / 10 s response-time limits as evidence about build gates; they describe interactive UI response. Do not present the 23-minute or 40% figures as measured CI costs.

## When long gates are acceptable

- Later pipeline stages are expected to be slow. Humble & Farley describe acceptance, capacity, and manual testing as lengthy; Fowler notes an end-to-end stage "might take a couple of hours to run" and "may not run after every commit". The question is position on the critical path, not wall-clock time alone.
- Slow checks can stay, off the blocking path. GitHub's engineering blog reports developers "waited an average of 45 minutes for a successful run" before merging; after the fix, "This 45-minute CI now takes only 15 minutes to run!" by making long jobs non-blocking with a deferred compliance tool and a 72-hour fix timer. Source: https://github.blog/engineering/infrastructure/making-github-ci-workflow-3x-faster/
- Context changes the trade-off. Pivotal respondents in the Hilton et al. focused survey reported builds "greater than 60 minutes" and answered "varies by project" for acceptable time. Monorepos, hardware-in-the-loop, model training, and security scanning have inherent floors.
- Safety-critical verification accepts very long cycles because escaped defects are catastrophic; a vendor case study describes a single component taking "18–36 months at a cost of several million dollars". The skill's verdicts target interactive gates, not certification evidence.

The rule this yields: a gate is hostile when it blocks and exceeds the ideal, or blocks and exceeds the ceiling, or runs without an owner, deadline, or acting consumer. Duration alone does not condemn a scheduled gate.

## Thresholds practitioners use

| Threshold | Source | Kind |
|---|---|---|
| Ideally under 5 min, certainly no more than 10 | Humble & Farley, *Continuous Delivery* | Published guideline |
| Ten-minute build | Fowler, attributing XP; CI certification bliki | Published guideline |
| Under 10 min for automated test feedback | DORA capability page | Published recommendation |
| Most common maximum acceptable: 10 min; typical 5–10 | Hilton et al. 2017, 523 developers | Survey preference |
| Pipeline under 10 min | GitLab handbook, their own repo | Internal target |
| No numeric target | Joel Test, Microsoft playbook, GitHub Actions docs, CircleCI docs | Checked; none found |

Platform defaults are far higher than the guidelines: GitLab's default job timeout is 60 minutes, CircleCI jobs run up to hours, GitHub Actions jobs default to 360 minutes, Travis `travis_wait` adds 20 minutes by default. Defaults are limits, not targets.

## Verified tool facts

Checked against primary sources on 2026-10-09.

- PIT selects per test coverage ("pick a set of test cases targeted at the mutated code") and has an incremental history mode whose page calls it experimental and error-admitting. PIT timeouts default to factor 1.25 plus 4000 ms. Its "meta mutant" idea is not implemented, and its old test-distance filter was removed in 1.9.0. Git integration ships via the licensed Arcmutate plugin.
- StrykerJS defaults to `coverageAnalysis: perTest` (only covering tests per mutant); incremental mode exists; static mutants run all tests unless ignored.
- cargo-mutants `--in-diff` selects mutants, not tests; each selected mutant still runs all tests. Sharding is wall-clock speedup over more CPUs; the CPU model multiplies per-shard setup. The baseline run sets the test timeout; the automatic build timeout from 24.7.0 was removed in 24.7.1.
- Mull has a git-diff incremental mode (documented as experimental). Its SQLite output is an offline report, not a documented result cache.
- Google's mutation service is diff-scoped, suppresses "arid" AST nodes, generates at most one mutant per line, and limits surfaced findings. Median mutants per changelist: 820 traditional, 77 one-per-line, 7 with arid suppression; all arms are already diff-scoped. Developers initially called 85% of reported mutants unproductive; heuristics raised the productive share from 15% to 89% (the 11% figure is derived). Source: https://arxiv.org/html/2102.11378v2
- Meta's Mutation Monkey learns mutation templates and schedules execution off-peak, "between 7 p.m. and 7 a.m. Pacific time", evaluating hundreds to thousands of mutants per day. Source: https://arxiv.org/abs/2010.13464v3
- AccMut measured mutation schemata "on average 9.62 times faster" than per-mutant compilation, on the first 100 tests of two C subjects. Source: https://ar5iv.labs.arxiv.org/html/1702.06689
- Derived timeout rules (a multiple of a measured baseline) are established in tools but have no single canonical source; calibrate locally.

## Source list

1. Humble & Farley, *Continuous Delivery*, commit stage excerpt: https://www.informit.com/articles/article.aspx?p=1621865&seqNum=4
2. Fowler, "Continuous Integration": https://martinfowler.com/articles/continuousIntegration.html
3. Fowler, "Continuous Integration Certification": https://martinfowler.com/bliki/ContinuousIntegrationCertification.html
4. DORA, "Capabilities: Test automation": https://dora.dev/capabilities/test-automation/
5. Hilton et al., "Trade-offs in Continuous Integration" (ESEC/FSE 2017): https://mir.cs.illinois.edu/marinov/publications/HiltonETAL17TradeOffsInCI.pdf
6. Durieux et al., "Empirical Study of Restarted and Flaky Builds on Travis CI" (MSR 2020): https://arxiv.org/pdf/2003.11772
7. Beller, Gousios & Zaidman, "Oops, My Tests Broke the Build" (MSR 2017): DOI 10.1109/MSR.2017.62
8. *Software Engineering at Google*, ch. 23 (Continuous Integration): https://abseil.io/resources/swe-book/html/ch23.html
9. GitHub engineering, "Making GitHub CI workflow 3x faster": https://github.blog/engineering/infrastructure/making-github-ci-workflow-3x-faster/
10. GitLab handbook direction (pipeline target): https://handbook.gitlab.com/handbook/about/direction/
11. Rubinstein, Meyer & Evans (2001), APA summary: https://www.apa.org/topics/research/multitasking
12. Mark, Gudith & Klocke, CHI 2008: https://ics.uci.edu/~gmark/chi08-mark.pdf
13. Gallup interview with Gloria Mark (2006, on the CHI 2005 resumption figure): https://news.gallup.com/businessjournal/23146/too-many-interruptions-work.aspx
14. Parnin & Rugaber, "Resumption strategies for interrupted programming tasks" (2011): http://www.chrisparnin.me/pdf/parnin-sqj11.pdf
15. Nielsen, "Response Time Limits" (UI, not builds): https://www.nngroup.com/articles/response-times-3-important-limits/
16. GitHub Actions workflow syntax (timeouts, matrix, defaults): https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
17. Google mutation testing (arXiv 2102.11378): https://arxiv.org/html/2102.11378v2
18. Meta Mutation Monkey (arXiv 2010.13464): https://arxiv.org/abs/2010.13464v3
19. AccMut (arXiv 1702.06689): https://ar5iv.labs.arxiv.org/html/1702.06689
20. cargo-mutants book: https://mutants.rs/ (in-diff, baseline, shards, changelog)
21. PIT docs: https://pitest.org/quickstart/basic_concepts/, https://pitest.org/quickstart/incremental_analysis/, https://pitest.org/quickstart/maven
22. StrykerJS docs: https://stryker-mutator.io/docs/stryker-js/configuration/, https://stryker-mutator.io/docs/stryker-js/incremental/, https://stryker-mutator.io/docs/mutation-testing-elements/static-mutants
23. Mull docs: https://mull.readthedocs.io/en/latest/IncrementalMutationTesting.html
