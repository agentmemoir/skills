#!/usr/bin/env node
/**
 * generate-report.cjs
 * Renders an autopsy HTML report from findings.json.
 *
 * Usage:
 *   node generate-report.cjs <findings.json | scratch_dir> [output.html] [--inline-css] [--no-open]
 *   node generate-report.cjs --self-check
 *
 * After writing report.html, opens it in the default browser when a GUI is
 * available (a desktop session on Linux, or macOS/Windows). Set --no-open or
 * AUTOPSY_NO_OPEN=1 to
 * disable; CI runs never open. The result JSON
 * reports `opened` plus `open_status` (launched | disabled | env | ci | no-gui
 * | failed) so callers can present the report deterministically.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeVerdict(verdict) {
  const v = (typeof verdict === 'string' ? verdict : (verdict && verdict.status) || 'Adequate').trim();
  const lower = v.toLowerCase();
  if (lower.includes('excellent')) {
    return { name: 'Excellent', class: 'b-green', icon: 'sparkles' };
  }
  if (lower.includes('good')) {
    return { name: 'Good', class: 'b-blue', icon: 'circle-check' };
  }
  if (lower.includes('inadequate')) {
    return { name: 'Inadequate', class: 'b-red', icon: 'octagon-x' };
  }
  return { name: 'Adequate', class: 'b-amber', icon: 'circle-alert' };
}

function normalizeReqStatus(status) {
  const s = (status || '').trim();
  const lower = s.toLowerCase();
  if (lower.includes('fully') || lower === 'satisfied' || lower === 'pass') {
    return { name: 'Fully satisfied', class: 'b-green', icon: 'check' };
  }
  if (lower.includes('partially')) {
    return { name: 'Partially satisfied', class: 'b-amber', icon: 'circle-minus' };
  }
  if (lower.includes('miss') || lower === 'fail') {
    return { name: 'Missed', class: 'b-red', icon: 'circle-x' };
  }
  if (lower.includes('n/a') || lower.includes('not applicable')) {
    return { name: 'Not applicable', class: '', icon: 'minus' };
  }
  return { name: s || 'Unclear', class: 'b-amber', icon: 'circle-alert' };
}

function normalizeVerificationClass(classification) {
  const c = (classification || '').trim();
  const lower = c.toLowerCase();
  if (lower.includes('established')) return { name: 'Established', class: 'b-green' };
  if (lower.includes('supported')) return { name: 'Supported', class: 'b-blue' };
  if (lower.includes('inferred')) return { name: 'Inferred', class: '' };
  if (lower.includes('uncertain')) return { name: 'Uncertain', class: 'b-amber' };
  if (lower.includes('contradicted')) return { name: 'Contradicted', class: 'b-red' };
  return { name: c || 'Unknown', class: 'b-amber' };
}

function renderReportHtml(data, options = {}) {
  const subject = data.subject || data.title || data.review_of || 'Work under review';
  const displaySubject = subject.startsWith('Autopsy of:') ? subject : `Autopsy of: ${subject}`;
  const verdictObj = normalizeVerdict(data.verdict);
  const justification = data.verdict_justification || data.justification || data.summary || (data.verdict && (data.verdict.justification || data.verdict.summary)) || '';

  const meta = data.metadata || data.meta || {};
  const today = new Date().toISOString().slice(0, 10);
  const generatedDate = meta.generated || data.generated || today;
  const appliesTo = meta.applies_to || data.applies_to || 'Current revision';
  const sourceDesc = meta.source || data.source || 'Work artifacts under review';

  const standards = Array.isArray(data.standard) ? data.standard : (Array.isArray(data.standards) ? data.standards : []);
  const requirements = Array.isArray(data.requirements) ? data.requirements : [];
  const rawIssues = Array.isArray(data.issues) ? data.issues : [];

  const criticalIssues = [];
  const importantIssues = [];
  const minorIssues = [];
  const dismissedFromIssues = [];

  for (const item of rawIssues) {
    const sev = (item.severity || '').toLowerCase();
    if (sev === 'critical') {
      criticalIssues.push(item);
    } else if (sev === 'important' || sev === 'high') {
      importantIssues.push(item);
    } else if (sev === 'dismissed' || sev === 'non-issue' || sev === 'non_issue') {
      dismissedFromIssues.push(item.why_it_matters || item.title || item.evidence || JSON.stringify(item));
    } else {
      minorIssues.push(item);
    }
  }

  let chipNum = 1;
  for (const issue of criticalIssues) {
    issue._chip = String(chipNum++).padStart(2, '0');
    if (issue.id === undefined) issue.id = chipNum - 1;
  }
  for (const issue of importantIssues) {
    issue._chip = String(chipNum++).padStart(2, '0');
    if (issue.id === undefined) issue.id = chipNum - 1;
  }
  for (const issue of minorIssues) {
    issue._chip = String(chipNum++).padStart(2, '0');
    if (issue.id === undefined) issue.id = chipNum - 1;
  }

  const dismissedRaw = Array.isArray(data.dismissed) ? data.dismissed : [];
  const dismissedItems = [
    ...dismissedRaw.map(d => (typeof d === 'string' ? d : (d.title || d.description || JSON.stringify(d)))),
    ...dismissedFromIssues
  ];

  const verificationItems = Array.isArray(data.verification) ? data.verification : (Array.isArray(data.verifications) ? data.verifications : []);
  const unknownsItems = Array.isArray(data.unknowns) ? data.unknowns : [];
  const strengths = Array.isArray(data.strengths) ? data.strengths : [];
  const regrets = Array.isArray(data.regrets) ? data.regrets : [];
  const processChanges = Array.isArray(data.process_changes) ? data.process_changes : (Array.isArray(data.process) ? data.process : []);
  const plan1hr = Array.isArray(data.plan_1hr) ? data.plan_1hr : (Array.isArray(data.plan_one_hour) ? data.plan_one_hour : []);
  const planUnlimited = Array.isArray(data.plan_unlimited) ? data.plan_unlimited : [];

  function isIssueFixed(issue) {
    if (!issue) return false;
    if (issue.fixed === true) return true;
    if (typeof issue.status === 'string' && issue.status.toLowerCase() === 'fixed') return true;
    if (issue.commentary || issue.fix_commentary || issue.fix_applied || issue.resolution || issue.fixed_at) return true;
    return false;
  }

  // Summary counts and fixed tracking
  const criticalFixed = criticalIssues.filter(isIssueFixed).length;
  const importantFixed = importantIssues.filter(isIssueFixed).length;
  const minorFixed = minorIssues.filter(isIssueFixed).length;
  const totalIssues = criticalIssues.length + importantIssues.length + minorIssues.length;
  const totalFixed = criticalFixed + importantFixed + minorFixed;

  function formatCountPart(count, fixedCount, label) {
    if (fixedCount > 0) {
      return `${count} ${label} (${fixedCount} fixed)`;
    }
    return `${count} ${label}`;
  }

  const summaryParts = [];
  if (criticalIssues.length > 0) summaryParts.push(formatCountPart(criticalIssues.length, criticalFixed, 'critical'));
  if (importantIssues.length > 0) summaryParts.push(formatCountPart(importantIssues.length, importantFixed, 'important'));
  if (minorIssues.length > 0) summaryParts.push(formatCountPart(minorIssues.length, minorFixed, 'minor'));
  if (dismissedItems.length > 0) summaryParts.push(`${dismissedItems.length} dismissed`);
  if (summaryParts.length === 0) summaryParts.push('0 issues found');
  const countsSummary = summaryParts.join(' · ');

  // TOC items (only include sections that exist)
  const toc = [];
  if (standards.length > 0) toc.push({ id: 'standard', label: 'Standard' });
  if (requirements.length > 0) toc.push({ id: 'coverage', label: 'Coverage' });
  if (criticalIssues.length > 0) toc.push({ id: 'critical', label: 'Critical' });
  if (importantIssues.length > 0) toc.push({ id: 'important', label: 'Important' });
  if (minorIssues.length > 0) toc.push({ id: 'minor', label: 'Minor' });
  if (dismissedItems.length > 0) toc.push({ id: 'dismissed', label: 'Dismissed' });
  if (verificationItems.length > 0) toc.push({ id: 'verification', label: 'Verification' });
  if (unknownsItems.length > 0) toc.push({ id: 'unknowns', label: 'Unknowns' });
  if (strengths.length > 0) toc.push({ id: 'strengths', label: 'Strengths' });
  if (regrets.length > 0 || processChanges.length > 0) toc.push({ id: 'process', label: 'Process' });
  if (plan1hr.length > 0 || planUnlimited.length > 0) toc.push({ id: 'plans', label: 'Plans' });

  // CSS handling
  let cssBlock = '<link rel="stylesheet" href="style.css">';
  if (options.inlineCss && options.cssContent) {
    cssBlock = `<style>\n${options.cssContent}\n</style>`;
  }

  const reportPath = options.reportPath || 'report.html';
  const findingsPath = options.findingsPath || 'findings.json';

  // Section renderers
  function renderStandard() {
    if (standards.length === 0) return '';
    const lis = standards.map(s => `        <li>${escapeHtml(typeof s === 'string' ? s : JSON.stringify(s))}</li>`).join('\n');
    return `    <section id="standard">
      <h2 class="sh"><i data-lucide="target" class="ic"></i>What this was judged against</h2>
      <ul class="dash">
${lis}
      </ul>
    </section>`;
  }

  function renderCoverage() {
    if (requirements.length === 0) return '';
    const satisfiedCount = requirements.filter(r => (r.status || '').toLowerCase().includes('fully')).length;
    const preText = `${satisfiedCount} of ${requirements.length} requirements fully satisfied`;
    const rows = requirements.map(r => {
      const st = normalizeReqStatus(r.status);
      const iconTag = st.icon ? `<i data-lucide="${st.icon}" class="ic"></i>` : '';
      const badgeClass = st.class ? `badge ${st.class}` : 'badge';
      const severity = r.severity ? `<span class="badge">${escapeHtml(r.severity)}</span>` : '<span class="badge">—</span>';
      const fixedBadge = r.fixed === true ? ' <span class="badge b-green"><i data-lucide="check" class="ic"></i>Fixed</span>' : '';
      return `            <tr>
              <td>${escapeHtml(r.requirement || r.name || '')}</td>
              <td><span class="${badgeClass}">${iconTag}${escapeHtml(st.name)}</span>${fixedBadge}</td>
              <td class="mut">${escapeHtml(r.evidence || '')}</td>
              <td>${severity}</td>
            </tr>`;
    }).join('\n');

    return `    <section id="coverage">
      <h2 class="sh"><i data-lucide="clipboard-check" class="ic"></i>Requirement coverage</h2>
      <p class="pre">${escapeHtml(preText)}</p>
      <div class="card tw">
        <table>
          <thead><tr><th>Requirement</th><th>Status</th><th>Evidence</th><th>Severity</th></tr></thead>
          <tbody>
${rows}
          </tbody>
        </table>
      </div>
    </section>`;
  }

  function renderIssueCard(issue, badgeClass, badgeLabel) {
    const chip = issue._chip || '01';
    const title = escapeHtml(issue.title || 'Untitled issue');
    const why = escapeHtml(issue.why_it_matters || '');
    const impact = escapeHtml(issue.impact || '');
    const evidence = escapeHtml(issue.evidence || '');
    const confidence = escapeHtml(issue.confidence || 'Medium');
    const proposedFix = escapeHtml(issue.proposed_fix || '');
    const isFixed = isIssueFixed(issue);

    const cardClass = isFixed ? 'card issue is-fixed' : 'card issue';
    const badgesHtml = isFixed
      ? `<div class="ibadges">
              <span class="badge ${badgeClass}"><span class="dot"></span>${badgeLabel}</span>
              <span class="badge b-green"><i data-lucide="check" class="ic"></i>Fixed</span>
            </div>`
      : `<span class="badge ${badgeClass}"><span class="dot"></span>${badgeLabel}</span>`;

    const fixLabel = isFixed
      ? '<p class="fl">Proposed fix</p>'
      : '<p class="fl">Proposed fix (not yet applied)</p>';

    const commentaryText = issue.commentary || issue.fix_commentary || issue.fix_applied || issue.resolution;
    const fixNoteHtml = isFixed
      ? `
            <div class="fix-note">
              <p class="fl"><i data-lucide="check" class="ic"></i>Resolution: What was done</p>
              <p>${escapeHtml(commentaryText || 'Addressed as proposed.')}</p>
            </div>`
      : '';

    return `        <article class="${cardClass}">
          <span class="chip">${chip}</span>
          <div>
            <div class="ihead">
              <h3>${title}</h3>
              ${badgesHtml}
            </div>
            <dl>
              <div><dt>Why it matters</dt><dd>${why}</dd></div>
              <div><dt>Impact if unaddressed</dt><dd>${impact}</dd></div>
              <div><dt>Evidence</dt><dd>${evidence}</dd></div>
              <div><dt>Confidence</dt><dd class="cnt">${confidence}</dd></div>
            </dl>
            <div class="fix">
              ${fixLabel}
              <p>${proposedFix}</p>${fixNoteHtml}
            </div>
          </div>
        </article>`;
  }

  function renderCritical() {
    if (criticalIssues.length === 0) return '';
    const cnt = String(criticalIssues.length).padStart(2, '0');
    const cards = criticalIssues.map(i => renderIssueCard(i, 'b-red', 'Critical')).join('\n');
    return `    <section id="critical">
      <h2 class="sh"><i data-lucide="octagon-alert" class="ic c-red"></i>Critical <span class="cnt">${cnt}</span></h2>
      <p class="lede">Address these before considering the work done.</p>
      <div class="stack">
${cards}
      </div>
    </section>`;
  }

  function renderImportant() {
    if (importantIssues.length === 0) return '';
    const cnt = String(importantIssues.length).padStart(2, '0');
    const cards = importantIssues.map(i => renderIssueCard(i, 'b-amber', 'Important')).join('\n');
    return `    <section id="important">
      <h2 class="sh"><i data-lucide="triangle-alert" class="ic c-amber"></i>Important <span class="cnt">${cnt}</span></h2>
      <p class="lede">Usable as is. These would materially improve it.</p>
      <div class="stack">
${cards}
      </div>
    </section>`;
  }

  function renderMinor() {
    if (minorIssues.length === 0) return '';
    const cnt = String(minorIssues.length).padStart(2, '0');
    const cards = minorIssues.map(i => renderIssueCard(i, 'b-blue', 'Minor')).join('\n');
    return `    <section id="minor">
      <h2 class="sh"><i data-lucide="info" class="ic c-sky"></i>Minor <span class="cnt">${cnt}</span></h2>
      <p class="lede">Worth considering. Unlikely to change the substantive result.</p>
      <div class="stack">
${cards}
      </div>
    </section>`;
  }

  function renderDismissed() {
    if (dismissedItems.length === 0) return '';
    const lis = dismissedItems.map(d => `        <li>${escapeHtml(d)}</li>`).join('\n');
    return `    <section id="dismissed">
      <h2 class="sh"><i data-lucide="circle-check" class="ic"></i>Considered and dismissed</h2>
      <ul class="dash dim">
${lis}
      </ul>
    </section>`;
  }

  function renderVerification() {
    if (verificationItems.length === 0) return '';
    const rows = verificationItems.map(v => {
      const cls = normalizeVerificationClass(v.classification || v.status);
      const note = v.source_note || v.source || v.notes || '';
      const text = note ? `${v.claim || ''} — ${note}` : (v.claim || '');
      const badgeClass = cls.class ? `badge ${cls.class}` : 'badge';
      return `        <div class="card vrow">
          <span class="${badgeClass}">${escapeHtml(cls.name)}</span>
          <p>${escapeHtml(text)}</p>
        </div>`;
    }).join('\n');

    return `    <section id="verification">
      <h2 class="sh"><i data-lucide="search-check" class="ic"></i>External verification</h2>
      <div class="stack">
${rows}
      </div>
    </section>`;
  }

  function renderUnknowns() {
    if (unknownsItems.length === 0) return '';
    const cards = unknownsItems.map(u => {
      const what = escapeHtml(u.what || u.title || '');
      const detailParts = [u.why_unknown, u.what_would_resolve_it, u.materiality].filter(Boolean);
      const detail = escapeHtml(u.description || (detailParts.length ? detailParts.join(' · ') : ''));
      return `        <div class="card unk">
          <p class="t">${what}</p>
          <p class="d">${detail}</p>
        </div>`;
    }).join('\n');

    return `    <section id="unknowns">
      <h2 class="sh"><i data-lucide="circle-help" class="ic"></i>What remains unknown</h2>
      <div class="stack">
${cards}
      </div>
    </section>`;
  }

  function renderStrengths() {
    if (strengths.length === 0) return '';
    const lis = strengths.map(s => `        <li>${escapeHtml(s)}</li>`).join('\n');
    return `    <section id="strengths">
      <h2 class="sh"><i data-lucide="thumbs-up" class="ic c-green"></i>Strongest aspects</h2>
      <ul class="dash">
${lis}
      </ul>
    </section>`;
  }

  function renderProcess() {
    if (regrets.length === 0 && processChanges.length === 0) return '';
    const regretsLis = regrets.map(r => `          <li>${escapeHtml(r)}</li>`).join('\n');
    const processLis = processChanges.map(p => `          <li>${escapeHtml(p)}</li>`).join('\n');

    return `    <section id="process" class="cols2">
      <div>
        <h2 class="sub"><i data-lucide="rotate-ccw" class="ic"></i>Regrets</h2>
        <ul class="list">
${regretsLis || '          <li>None noted</li>'}
        </ul>
      </div>
      <div>
        <h2 class="sub"><i data-lucide="settings" class="ic"></i>Process changes for next time</h2>
        <ul class="list">
${processLis || '          <li>None noted</li>'}
        </ul>
      </div>
    </section>`;
  }

  function renderPlans() {
    if (plan1hr.length === 0 && planUnlimited.length === 0) return '';
    const oneHrLis = plan1hr.map(p => `          <li>${escapeHtml(p)}</li>`).join('\n');
    const unlimitedLis = planUnlimited.map(p => `          <li>${escapeHtml(p)}</li>`).join('\n');

    return `    <section id="plans" class="cols2">
      <div class="card pad">
        <h2 class="sub"><i data-lucide="clock" class="ic"></i>If given one hour</h2>
        <ol class="list num">
${oneHrLis || '          <li>No immediate changes required</li>'}
        </ol>
      </div>
      <div class="card pad">
        <h2 class="sub"><i data-lucide="telescope" class="ic"></i>With unlimited resources</h2>
        <ul class="list">
${unlimitedLis || '          <li>No major redesigns indicated</li>'}
        </ul>
      </div>
    </section>`;
  }

  const sections = [
    renderStandard(),
    renderCoverage(),
    renderCritical(),
    renderImportant(),
    renderMinor(),
    renderDismissed(),
    renderVerification(),
    renderUnknowns(),
    renderStrengths(),
    renderProcess(),
    renderPlans()
  ].filter(Boolean).join('\n\n');

  const tocLinks = toc.map(t => `      <a href="#${t.id}">${t.label}</a>`).join('\n');

    const closingIcon = totalFixed > 0
      ? '<i data-lucide="check-circle-2" class="ic c-green"></i>'
      : '<i data-lucide="pause-circle" class="ic"></i>';

    const closingTitle = totalFixed > 0
      ? (totalFixed === totalIssues ? 'All identified issues have been fixed.' : `${totalFixed} issue(s) marked fixed.`)
      : 'No changes have been made yet.';

    const closingDesc = totalFixed > 0
      ? 'Fixes have been applied to the work and recorded in findings.json. Review the updated report or specify any remaining items to address.'
      : 'This report only diagnoses. Tell me which issues to fix: all of them, just the critical ones, specific items by number, or none. I will apply exactly that.';

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Autopsy report: ${escapeHtml(subject)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&family=Newsreader:opsz,wght@6..72,600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
${cssBlock}
</head>
<body>
<a class="skip" href="#content">Skip to report content</a>

<header>
  <div class="wrap">
    <p class="eyebrow">Autopsy</p>
    <h1>${escapeHtml(displaySubject)}</h1>
    <div class="vline">
      <span class="badge ${verdictObj.class}"><i data-lucide="${verdictObj.icon}" class="ic"></i>${escapeHtml(verdictObj.name)}</span>
      <span class="mono">${escapeHtml(countsSummary)}</span>
    </div>
    <p class="sum">${escapeHtml(justification)}</p>
    <p class="meta mono">
      <span><b>Generated</b>${escapeHtml(generatedDate)}</span>
      <span><b>Applies to</b>${escapeHtml(appliesTo)}</span>
      <span><b>Source</b>${escapeHtml(sourceDesc)}</span>
    </p>
  </div>
</header>

<div class="wrap layout">
  <aside class="no-print">
    <nav class="toc" aria-label="On this page">
      <p>On this page</p>
${tocLinks}
    </nav>
  </aside>

  <main id="content">

${sections}

    <section id="closing" class="closing">
      ${closingIcon}
      <div>
        <h2>${escapeHtml(closingTitle)}</h2>
        <p>${escapeHtml(closingDesc)}</p>
        <div class="paths">
          <span><b>Report:</b>${escapeHtml(reportPath)}</span>
          <span><b>Findings:</b>${escapeHtml(findingsPath)}</span>
        </div>
      </div>
    </section>

  </main>
</div>

<script>
if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
  lucide.createIcons();
}
(function () {
  var links = [].slice.call(document.querySelectorAll('.toc a[href^="#"]'));
  if (!links.length || !('IntersectionObserver' in window)) return;
  var map = {};
  links.forEach(function (a) { map[a.hash.slice(1)] = a; });
  var sections = Object.keys(map).map(function (id) { return document.getElementById(id); }).filter(Boolean);
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) {
        if (a.hash === '#' + e.target.id) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
    });
  }, { rootMargin: '-20% 0px -70% 0px', threshold: 0 });
  sections.forEach(function (s) { obs.observe(s); });
})();
</script>
</body>
</html>
`;
}

function resolveAssetPath(relPath) {
  // assets live beside scripts: ../assets/
  const p = path.resolve(__dirname, '..', 'assets', relPath);
  if (fs.existsSync(p)) return p;
  return null;
}

function isCiEnvironment() {
  const ci = process.env.CI;
  return !!ci && ci !== 'false' && ci !== '0';
}

// Returns the platform opener when a GUI session can display the report,
// or null when there is no display to open it on.
function resolveGuiOpener(reportPath) {
  if (process.platform === 'darwin') {
    return { cmd: 'open', args: [reportPath] };
  }
  if (process.platform === 'win32') {
    return { cmd: 'cmd', args: ['/c', 'start', '', reportPath] };
  }
  if (process.env.DISPLAY || process.env.WAYLAND_DISPLAY) {
    return { cmd: 'xdg-open', args: [reportPath] };
  }
  return null;
}

// Opens report.html only when a GUI is available and opening is not disabled.
// Returns { opened, reason } where reason is one of:
//   disabled | env | ci | no-gui | failed | launched
async function openReportInGui(reportPath, options = {}) {
  if (options.disabled) return { opened: false, reason: 'disabled' };
  const envOff = process.env.AUTOPSY_NO_OPEN ?? process.env.ADVERSARIAL_REVIEW_NO_OPEN;
  if (envOff === '1' || envOff === 'true') return { opened: false, reason: 'env' };
  if (isCiEnvironment()) return { opened: false, reason: 'ci' };
  const opener = options.opener || resolveGuiOpener(reportPath);
  if (!opener) return { opened: false, reason: 'no-gui' };
  try {
    const child = spawn(opener.cmd, opener.args, {
      detached: true,
      stdio: 'ignore',
      windowsHide: true
    });
    child.unref();
    const launched = await waitForSpawn(child, 1500);
    return { opened: launched, reason: launched ? 'launched' : 'failed' };
  } catch (_) {
    return { opened: false, reason: 'failed' };
  }
}

// Resolves true once the child actually spawns, false on launch error or timeout.
// spawn() returns before the OS resolves the command, so this is the only way to
// tell a real opener from a missing one (ENOENT is emitted asynchronously).
function waitForSpawn(child, timeoutMs) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (opened) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(opened);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    child.once('spawn', () => finish(true));
    child.once('error', () => finish(false));
  });
}

async function runSelfCheck() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'autopsy-selfcheck-'));
  try {
    const sample = {
      subject: "Sample Task Evaluation",
      verdict: "Adequate",
      verdict_justification: "Meets basic functionality but lacks automated tests and input validation.",
      metadata: {
        generated: "2026-09-16",
        applies_to: "HEAD",
        source: "scripts/example.cjs"
      },
      standard: ["Must be deterministic", "Must handle errors cleanly"],
      requirements: [
        { requirement: "Valid input handling", status: "Fully satisfied", evidence: "Tested with valid inputs", severity: "Low" },
        { requirement: "Error boundaries", status: "Partially satisfied", evidence: "Some errors unhandled", severity: "Medium" }
      ],
      issues: [
        {
          id: 1,
          title: "Missing input sanitization",
          severity: "Critical",
          why_it_matters: "Can lead to crash on invalid JSON",
          impact: "Process exits unexpectedly",
          evidence: "No try/catch around JSON.parse",
          confidence: "High",
          proposed_fix: "Wrap JSON.parse in try/catch block",
          fixed: true,
          commentary: "Added try/catch wrapper around JSON.parse with graceful error return."
        },
        {
          id: 2,
          title: "Incomplete documentation",
          severity: "Minor",
          why_it_matters: "Developers cannot see all flags",
          impact: "Harder to use",
          evidence: "README omits --inline-css",
          confidence: "High",
          proposed_fix: "Document all flags in README"
        }
      ],
      dismissed: ["Performance under 1000 items is fine"],
      verification: [
        { claim: "Node.js 18+ is supported", classification: "Established", source_note: "Node compatibility matrix" }
      ],
      unknowns: [
        { what: "Peak memory usage", why_unknown: "No load test performed", what_would_resolve_it: "Benchmarking script", materiality: "Low" }
      ],
      strengths: ["Clean modular design"],
      regrets: ["Should have written tests first"],
      process_changes: ["Add pre-commit lint check"],
      plan_1hr: ["Add try/catch around parse", "Add basic test file"],
      plan_unlimited: ["Add full test suite with coverage reporting"]
    };

    const findingsFile = path.join(tmpDir, 'findings.json');
    const reportFile = path.join(tmpDir, 'report.html');
    fs.writeFileSync(findingsFile, JSON.stringify(sample, null, 2), 'utf8');

    const cssPath = resolveAssetPath('style.css');
    const cssContent = cssPath ? fs.readFileSync(cssPath, 'utf8') : '';

    const html = renderReportHtml(sample, {
      reportPath: reportFile,
      findingsPath: findingsFile,
      inlineCss: false,
      cssContent
    });

    fs.writeFileSync(reportFile, html, 'utf8');

    // Verify generated HTML
    if (!html.includes('<title>Autopsy report: Sample Task Evaluation</title>')) {
      throw new Error('Self-check failed: title mismatch');
    }
    if (!html.includes('<p class="eyebrow">Autopsy</p>')) {
      throw new Error('Self-check failed: eyebrow branding missing');
    }
    if (!html.includes('<h1>Autopsy of: Sample Task Evaluation</h1>')) {
      throw new Error('Self-check failed: heading branding missing');
    }
    if (!html.includes('Missing input sanitization')) {
      throw new Error('Self-check failed: issue missing');
    }
    if (!html.includes('01') || !html.includes('02')) {
      throw new Error('Self-check failed: rank chips missing');
    }
    if (!html.includes('id="critical"') || !html.includes('id="minor"')) {
      throw new Error('Self-check failed: sections missing');
    }
    if (html.includes('id="important"')) {
      throw new Error('Self-check failed: empty important section should have been omitted');
    }
    if (!html.includes('is-fixed') || !html.includes('badge b-green"><i data-lucide="check" class="ic"></i>Fixed')) {
      throw new Error('Self-check failed: fixed visual cues missing');
    }
    if (!html.includes('Wrap JSON.parse in try/catch block')) {
      throw new Error('Self-check failed: original proposed fix text must be preserved');
    }
    if (!html.includes('Resolution: What was done') || !html.includes('Added try/catch wrapper around JSON.parse')) {
      throw new Error('Self-check failed: resolution commentary missing');
    }
    if (!html.includes('1 critical (1 fixed)')) {
      throw new Error('Self-check failed: header fixed count summary missing');
    }
    if (!html.includes('1 issue(s) marked fixed.')) {
      throw new Error('Self-check failed: closing panel fixed status missing');
    }

    // GUI-gate checks. None of these launch a real browser.
    const disabledGate = await openReportInGui(reportFile, { disabled: true });
    if (disabledGate.opened !== false || disabledGate.reason !== 'disabled') {
      throw new Error('Self-check failed: --no-open gate should report disabled');
    }

    const savedNoOpen = process.env.AUTOPSY_NO_OPEN;
    process.env.AUTOPSY_NO_OPEN = '1';
    const envGate = await openReportInGui(reportFile, {});
    if (savedNoOpen === undefined) delete process.env.AUTOPSY_NO_OPEN;
    else process.env.AUTOPSY_NO_OPEN = savedNoOpen;
    if (envGate.opened !== false || envGate.reason !== 'env') {
      throw new Error('Self-check failed: env opt-out should report env');
    }

    const savedCi = process.env.CI;
    delete process.env.CI;
    try {
      const launched = await openReportInGui(reportFile, {
        opener: { cmd: process.execPath, args: ['-e', '0'] }
      });
      if (launched.opened !== true || launched.reason !== 'launched') {
        throw new Error('Self-check failed: a present opener should launch');
      }
      const missing = await openReportInGui(reportFile, {
        opener: { cmd: 'autopsy-no-such-command-xyz', args: [] }
      });
      if (missing.opened !== false || missing.reason !== 'failed') {
        throw new Error('Self-check failed: a missing opener should report failed');
      }
    } finally {
      if (savedCi !== undefined) process.env.CI = savedCi;
    }

    const resolvedOpener = resolveGuiOpener(reportFile);
    const onDesktop =
      process.platform === 'darwin' ||
      process.platform === 'win32' ||
      Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
    if (onDesktop && !resolvedOpener) {
      throw new Error('Self-check failed: a desktop session should resolve an opener');
    }
    if (!onDesktop && resolvedOpener) {
      throw new Error('Self-check failed: a headless session should not resolve an opener');
    }

    console.log(JSON.stringify({ ok: true, self_check: true, dir: tmpDir, report: reportFile, findings: findingsFile }));
  } finally {
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch (_) {}
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--self-check')) {
    await runSelfCheck();
    return;
  }

  const inlineCss = args.includes('--inline-css') || args.includes('--single-file');
  const noOpen = args.includes('--no-open');
  const cleanArgs = args.filter(a => !a.startsWith('--'));

  if (cleanArgs.length === 0) {
    console.error('Usage: node generate-report.cjs <findings.json | scratch_dir> [output.html] [--inline-css] [--no-open]');
    process.exit(1);
  }

  const inputTarget = path.resolve(cleanArgs[0]);
  let findingsPath;
  let reportPath;
  let workDir;

  if (fs.existsSync(inputTarget) && fs.statSync(inputTarget).isDirectory()) {
    workDir = inputTarget;
    findingsPath = path.join(workDir, 'findings.json');
    reportPath = cleanArgs[1] ? path.resolve(cleanArgs[1]) : path.join(workDir, 'report.html');
  } else {
    findingsPath = inputTarget;
    workDir = path.dirname(findingsPath);
    reportPath = cleanArgs[1] ? path.resolve(cleanArgs[1]) : path.join(workDir, 'report.html');
  }

  if (!fs.existsSync(findingsPath)) {
    console.error(`Error: findings file not found at ${findingsPath}`);
    process.exit(1);
  }

  let data;
  try {
    const raw = fs.readFileSync(findingsPath, 'utf8');
    data = JSON.parse(raw);
  } catch (err) {
    console.error(`Error parsing JSON at ${findingsPath}: ${err.message}`);
    process.exit(1);
  }

  // Lightweight schema warning for recommended keys
  const recommendedKeys = ['subject', 'verdict', 'requirements', 'issues'];
  for (const key of recommendedKeys) {
    if (data[key] === undefined) {
      console.warn(`Warning: findings.json is missing recommended field '${key}'`);
    }
  }

  // Ensure style.css is beside report.html if not inlining (sync fresh content if stale)
  const destDir = path.dirname(reportPath);
  const targetCss = path.join(destDir, 'style.css');
  const sourceCss = resolveAssetPath('style.css');

  let cssContent = '';
  if (sourceCss && fs.existsSync(sourceCss)) {
    cssContent = fs.readFileSync(sourceCss, 'utf8');
    if (!inlineCss) {
      try {
        const needsCopy = !fs.existsSync(targetCss) || fs.readFileSync(targetCss, 'utf8') !== cssContent;
        if (needsCopy) {
          fs.copyFileSync(sourceCss, targetCss);
        }
      } catch (err) {
        console.warn(`Warning: failed to sync style.css: ${err.message}`);
      }
    }
  }

  const html = renderReportHtml(data, {
    reportPath,
    findingsPath,
    inlineCss,
    cssContent
  });

  fs.writeFileSync(reportPath, html, 'utf8');
  const stat = fs.statSync(reportPath);
  const openResult = await openReportInGui(reportPath, { disabled: noOpen });

  const result = {
    ok: true,
    report: reportPath,
    findings: findingsPath,
    bytes: stat.size,
    opened: openResult.opened,
    open_status: openResult.reason
  };

  console.log(JSON.stringify(result));
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err && err.message ? err.message : err);
    process.exitCode = 1;
  });
}

module.exports = {
  renderReportHtml,
  normalizeVerdict,
  normalizeReqStatus,
  escapeHtml,
  resolveGuiOpener,
  openReportInGui
};
