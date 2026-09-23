---
name: opus-orchestration
description: "Delegation policy for a Claude Pro + ChatGPT Plus stack (no Fable/Max access) where Opus runs the main orchestration loop and is the only dispatcher. On the GPT side (via Codex CLI) Luna is the default executor for basit and orta work (bulk, research, scoped implementation), Sol does precision execution, and Astra is reserved for hard reasoning only. Sonnet is the Claude-side lane for work needing Claude-side tools, second-opinion review, and fallback when GPT fails; its use is gated by ~/.claude/rate-limit-status.json. Opus classifies tasks inline (no Haiku triage gate); Haiku is a fallback only. Includes routing for 3D modelling/printing and computer use (with the 3dprint skill). Load whenever spawning sub-agents (Agent tool) or Codex CLI lanes, or planning any delegation."
---

# Orchestration & delegation policy (Claude Pro + ChatGPT Plus stack)

A routing policy for a stack with **one scarce top-tier model (Opus, capped by
Claude Pro's baseline quota)** and cheaper delegate tiers split across two
providers: Luna / Sol / Astra on the GPT side (reached through Codex CLI,
billed against the ChatGPT Plus quota) carry most execution, with Luna as the
default; Sonnet on the Claude side covers what needs Claude-side tools,
review, and GPT fallback. Haiku is kept only as a fallback lane (see
"Choosing the delegate").

This policy assumes **no Claude Max and no Fable access**. If that changes,
see "Future: Max/Fable migration" at the bottom before continuing to use this
policy as-is.

Core law: **Opus's quota is the tightest constraint in the whole stack, so it
must never do work that is cheaper to delegate.** Its turns buy judgment, not
throughput.

## The hard rules

1. **Opus classifies inline — no separate triage agent.** Every task already
   arrives at Opus first, so spawning another model just to classify it costs
   more than classifying it. Opus labels each task **basit / orta / zor** as
   it reads it and routes per "Routing flow". One exception to delegation:
   a task so small that writing its spec would cost more than doing it (a
   one-line edit, a single file read to answer a question) Opus does inline.
2. **Opus orchestrates, never executes anything cheaper to delegate.**
   Architecture, task decomposition, spec-writing, synthesis of results,
   conflict resolution, final judgment calls — done by Opus, kept lean.
   Anything scoped and larger than the rule 1 inline threshold gets
   delegated, even if Opus "could" do it faster itself.
3. **Delegation is one level deep; Opus is the only dispatcher.** Only the
   top-level Opus session spawns agents or runs `codex exec`. Workers
   (sonnet-worker, haiku-worker) never spawn agents and never call Codex CLI.
   If a worker's task needs GPT-side execution, the worker drafts the spec and
   returns it; Opus re-reads it and dispatches. This keeps every dispatch
   auditable, and keeps the quota check (rule 5) in the one place that reads
   `~/.claude/rate-limit-status.json`.
4. **Dispatch through the named presets, not a raw model override.** Use
   `Agent(subagent_type: "sonnet-worker")` (and `haiku-worker` only in its
   fallback role) — defined in `~/.claude/agents/` — rather than a generic
   Agent call with a manually-set `model:` field, so a dispatch can never
   accidentally omit-and-inherit Opus. If a preset is ever unavailable, fall
   back to an explicit `model:` field — never omit it.
5. **Luna is the default for orta work; Sonnet is the exception.** Claude
   Pro quota is the scarcer side of the stack, and Sonnet load is what drives
   the Claude 5h/7d windows up fastest. Orta tasks go to Luna unless one of
   these applies, in which case Sonnet takes it:
   - the task needs Claude-side tools or context Luna can't reach (e.g.
     WebFetch on a site Codex can't use, files outside the Codex sandbox);
   - a second-opinion review of a Luna result is worth the Claude quota
     (high-stakes change, Luna's output looks off);
   - GPT-side dispatches are failing (see "Continuity").
   Before sending anything to Sonnet, read `~/.claude/rate-limit-status.json`:
   if `five_hour.used_percentage >= 60` OR `seven_day.used_percentage >= 70`,
   skip optional Sonnet work (second-opinion reviews) and keep Sonnet only
   for work that genuinely can't run on Luna. Thresholds are a starting
   point — tune them in practice.
   - **Basis:** a 2026-09-23 head-to-head on three orta tasks (bug fix with a
     second unreported bug, loose-brief feature, cross-file code questions),
     identical prompts, graded by hidden tests / answer key. Luna 6/6, 5/7
     (lost 2 only on an under-specified output format), 12/12 within the
     length limit; Sonnet 4/6 (missed the unreported bug), 6/7 (crashed on
     invalid input), 12/12 but over the length limit. Similar token use.
     One run per task on a small repo — directional, not conclusive; revisit
     if Luna underperforms on real work.
6. **Astra is for hard reasoning only.** Astra burns Codex quota fastest
   (API price 5× Sol, 100× Luna). Use it only when the task's difficulty is
   the reasoning itself — tricky algorithm/math design, a subtle root cause
   Luna and Sol have both failed to find, a correctness argument, or complex
   CAD geometry Opus has failed on (see "3D printing and computer use"). Not for
   terminal-heavy, computer-use, bulk, or long-context work: published
   numbers show Opus 5.5 ahead of Astra on Terminal-Bench 4.0 and OSWorld
   2.0, and every GPT tier already has a ~1M context.
7. **Spec quality gates every Codex CLI dispatch.** Sol and Luna execute a
   spec precisely but don't fill gaps well. A vague spec costs a wasted retry
   (and wasted GPT quota). Whoever drafts the spec (Opus, or Sonnet returning
   a draft per rule 3), Opus re-reads it once before dispatching.
8. **GPT is a tool call, not a native agent.** Sol/Luna/Astra are invoked
   through Codex CLI as a Bash tool call, authenticated against the ChatGPT
   Plus login. Real model IDs (confirmed via `codex` → `/model`):

   - Luna: `codex exec --model gpt-6-luna "<spec>"`
   - Sol: `codex exec --model gpt-6-sol "<spec>"`
   - Astra: `codex exec --model gpt-6-astra "<spec>"` (rule 6 only)

   `gpt-6-luna` / `gpt-6-sol` replaced `gpt-5.6-luna` / `gpt-5.6-sol`. The
   old Terra tier has no gpt-6 successor and is retired from this policy; if
   a gpt-6-terra ships, revisit the policy rather than silently adding it.

   Every dispatch uses this shape:

   ```
   codex exec --model <id> --skip-git-repo-check -s workspace-write \
     -o <scratch>/<task>-last-message.txt "<spec>" \
     < /dev/null > <scratch>/<task>.log 2>&1
   ```

   - `--skip-git-repo-check`: `codex exec` refuses outside a trusted git repo
     without it.
   - `< /dev/null` is mandatory, especially for background runs. `codex exec`
     checks stdin even when the prompt is an argument; left open, it blocks
     forever on "Reading additional input from stdin..." with no error. This
     already cost one 18+ minute stall.
   - `-o` + log redirect: read only the last-message file (and the files the
     spec asked for) into Opus's context, not the full transcript.
   - For web research add `-c web_search='"live"'`.
9. **Review family follows risk, not every change.** For high-risk work
   (auth/permissions, money, security, data-destroying migrations, deploy,
   external access), the reviewer must come from the **other family** than
   the executor: Claude wrote it → Sol reviews; GPT wrote it → Sonnet (or
   Opus for the highest-stakes calls) reviews. For routine work, tests, CI
   and a break-it verification scenario are the primary safeguard. An AI
   review is optional there, isolated, and from any family, so the cheapest
   suitable reviewer is fine. If a project defines its own risk tiers,
   follow them.
   - Every reviewer gets an isolated context: the task contract, the diff
     and the test output, never the author's conversation or rationale.
   - P0/P1 findings need evidence: a failing test, repro steps, or a
     concrete `file:line` + input → wrong output. Otherwise they are
     downgraded, which keeps false-positive churn down.
   - If the other family is unavailable (quota), a same-family isolated
     review may substitute on medium-risk work; note it in the review. On
     high-risk work, wait or escalate to the human.
   - **Basis (2026-09-23):** The most direct data is Greptile's "Model
     Inversion" study (Jul 2026, 1,000 PRs). A cross-family reviewer had
     higher recall on high-severity bugs in both directions: GPT on
     Claude-authored PRs 60.0% vs Opus 53.7%, and Opus on Codex-authored PRs
     62.0% vs GPT 50.5%. It is vendor data and not independently
     replicated. Self-preference papers are older and text-focused. No study
     compares a fresh-context same-model reviewer against a cross-family
     one. Most review products (Anthropic, OpenAI, Cursor, CodeRabbit) use
     their own models and rely on verification filtering instead. Since
     most execution now runs on GPT, mandatory cross-family review on
     routine work would spend scarce Claude quota for unproven gain.

## Choosing the delegate

- **Luna** (Codex CLI) — default lane for basit and orta work: bulk,
  research, codebase exploration, scoped implementation and bug fixing,
  including work over large inputs (API USD 0.10 / 0.50 per 1M tokens — by far
  the cheapest tier). See rule 5.
- **Sonnet** (`sonnet-worker`) — Claude-side lane per rule 5's exceptions:
  work needing Claude-side tools, cross-family review of GPT output on
  high-risk work (rule 9), optional second opinions, and orta fallback when
  GPT is failing. Quota-gated by the snapshot file. Not for CAD geometry
  (Opus models parts itself; see "3D printing and computer use").
- **Sol** (Codex CLI) — precision execution once a complete spec exists:
  hard implementation, migrations, test-writing against a defined contract.
- **Astra** (Codex CLI) — hard reasoning only, per rule 6.
- **Haiku** (`haiku-worker`) — fallback only: basit Claude-side work when
  GPT-side dispatches are failing (quota/outage). Note its 200K context
  limit.

## Routing flow

1. Opus classifies inline: **basit / orta / zor** (rule 1).
2. **basit** → below the inline threshold, Opus does it. Otherwise Luna
   (Haiku if GPT is failing).
3. **orta** → Opus writes a brief/spec and dispatches to Luna (Sol if the
   work needs precise, contract-bound execution). Sonnet only for rule 5's
   exceptions, after reading `~/.claude/rate-limit-status.json`.
4. **zor / mimari-hassas** → Opus handles the judgment part directly (spec,
   architecture, synthesis) and delegates the mechanical portions: Sol for
   precise execution, Luna for exploration, Astra only if the core
   difficulty is reasoning. The review follows rule 9: for high-risk work,
   the reviewer comes from the other family. Opus always owns final
   integration on this tier.

## 3D printing and computer use

This section covers routing for 3D modelling and printing. The workflow itself
(dimensions, CAD code, printability rules, verification, slicing, printing
through Bambu Studio) is in the `3dprint` skill, so load both.

**CAD modelling is not basit work.** Writing the code is easy. Getting the
geometry right (orientation, which face a feature sits on, fit with the real
object) is the hard part, and it is where models differ most.

**Opus models single parts itself. This is a deliberate exception to rule 2.**
A single part is 50–200 lines of OpenSCAD. A spec precise enough for Sol
(every dimension, orientation, which face each feature sits on) is most of
that work already. Opus has to review the renders either way, and each
fix-and-redispatch round costs Opus another spec plus another review. So
delegating a single part usually costs Opus more tokens than writing it,
and Opus also scores highest on CAD. Hobby printing volume is low (a few
parts a day), so Opus quota isn't the bottleneck here the way it is in
coding work.

| Step | Who | Why |
|---|---|---|
| Pin down dimensions, purpose, printer, material | **Opus** inline | Judgment. A wrong mating dimension wastes a whole print. |
| Model a single part, iterate on feedback, review renders | **Opus** inline | See above. |
| Bulk variants of a finished model (sizes, names, sets), pure parameter changes | **Luna** (Sol if the variant logic is fiddly) | Mechanical once the model exists; spec is short. |
| Modelling while Opus quota is high (5h ≥ 70% or 7d ≥ 80% in `~/.claude/rate-limit-status.json`) | **Sol**, with the render loop below; Opus reviews the final sheet only | Preserves Opus quota for judgment. |
| Complex geometry Opus has failed on twice, or reconstruction from photos/multiple views | **Astra**, attaching reference images with `-i` | Rule 6 exception: the difficulty is the spatial reasoning itself. |
| Slicing via CLI, mesh checks, file work | inline (they're one command) or **Luna** in bulk | Mechanical. |
| Anything on screen (Bambu Studio, Bambu Handy, other GUI apps) | **Opus**, top-level session only | See below. |

- **Don't route CAD geometry to Sonnet or Haiku.** On BenchCAD, Sonnet 5
  scored well below every other tier (below Luna).
- **Every CAD dispatch to a GPT tier must include a render loop:** the
  executor runs the mesh check (watertight, extents, number of connected
  bodies), renders the contact sheet with `render_sheet.py`, looks at it
  itself (Codex can view images), fixes errors, and only then reports back
  with the `.scad`, the STL/3MF and the sheet path. A render loop raises
  correctness sharply without a stronger model, so it's cheaper than moving
  up a tier. Attach reference photos with `codex exec -i <image> ...`.
- **Known failure modes to check in review:** GPT models tend to research
  dimensions well but get orientation wrong (the part extruded on its side,
  a rib floating off the base). Claude models tend to get the geometry right
  but guess real-world dimensions instead of looking them up. So check
  orientation and connectivity on GPT output, and check sourced dimensions
  on Claude output (including Opus's own).
- **Image budget: save tokens where it doesn't cost quality.** Details are in
  `3dprint`, step 4. In short: run the numeric checks before
  looking at any image; iterate on a draft sheet (~2.6K tokens); use the
  full-resolution sheet (~4.8K) only for the final check before printing;
  look closer with a targeted close-up instead of enlarging everything; don't
  re-render or re-view unchanged geometry. Never go below what the final
  check needs: the final sheet, plus a close-up of every feature that must
  fit something, is mandatory before a print.
- **Computer use stays on the top-level Opus session.** The `computer-use`
  MCP server runs only in an interactive session (not `claude -p`, and not
  in `codex exec`), and the worker presets don't have it. It also holds one
  lock per machine. Opus is also the strongest tier on OSWorld (rule 6).
  Screenshots are expensive on Opus's quota, so: do everything possible from
  the shell first (`open -a "Bambu Studio" file.3mf`, the Bambu Studio CLI
  for slicing), keep GUI steps to the ones with no CLI, and take few,
  deliberate screenshots. Don't skip the screenshot that confirms the
  settings before Print; that one is the safety check.
- **Physical actions need explicit user confirmation, every time.** Starting
  a print, cancelling one, or changing printer settings: summarise and wait
  for a yes. No delegate may start a print. Never change printer network or
  security settings (LAN-only / Developer Mode) yourself.
- **Basis (2026-09-23), directional only.** BenchCAD (CadQuery, 17.9K
  programs; self-reported, unverified): Opus 5.5 0.730, GPT-5.6 Sol 0.706,
  GPT-5.6 Luna 0.631, Sonnet 5 0.373. gpt-6-sol/luna aren't listed yet;
  they replaced the 5.6 versions, so expect at least similar results.
  GPT-6 Astra: vendor-reported 95.9% on BenchCAD Vision2Code with tools
  (vs Fable 5.1 84.3%, GPT-5.6 Sol 83.3%), not independently re-graded.
  GrandpaCAD (real user prompts): OpenSCAD had 3–4× fewer code errors than
  build123d/CadQuery, and public 3D leaderboards didn't predict real
  printable-model quality. XDA (Jun 2026, Opus 4.8 vs GPT-5.5): the
  opposite failure modes above. Image costs: Claude vision docs (Opus 4.7+
  high-resolution tier: 28×28 px per visual token, long edge ≤ 2576 px,
  ≤ 4784 tokens per image before downscaling). Revisit if Opus quota runs
  out in practice, or when gpt-6 CAD numbers appear.

## Continuity under quota exhaustion

Claude Code doesn't give the agent a tool to check its own rate-limit usage,
but the `statusLine` hook receives `rate_limits.five_hour.used_percentage`
and `rate_limits.seven_day.used_percentage` (Pro/Max only) on every
assistant message. `~/.claude/statusline.sh` is configured as the global
`statusLine` command and writes a snapshot to
`~/.claude/rate-limit-status.json` (`model`, `context_used_percentage`,
`rate_limits.five_hour` / `seven_day.used_percentage` and `resets_at`). Read
that file directly to get current Claude-side quota usage.

Codex CLI has no equivalent: only per-thread token counts, no account-wide
quota, and `/status` is interactive-only. GPT-side quota stays reactive-only.

- **Check the snapshot file before every Sonnet dispatch** (rule 5), as a
  fixed step of routing, not "at milestones".
- **Treat 85%+ on either window as a harder signal** — wrap up the current
  unit of work and checkpoint rather than starting another large one. If the
  file is missing or stale, fall back to continuous checkpointing.
- **Checkpoint continuously regardless.** After each meaningful step, write
  progress (done, left, key decisions) to `.orchestration-checkpoint.md` in
  the project (or its own task-tracking convention).
- **Treat a failed `codex exec` call as GPT's real signal.** On a rate-limit
  or quota error: retry once on a different GPT tier if the task allows it
  (e.g. luna instead of sol — never escalate to Astra for quota reasons). If
  every GPT tier is failing, fall back to Claude-side execution (Sonnet for
  orta, Haiku for basit) and note the substitution in the checkpoint.
- **Stop cleanly when both sides are confirmed exhausted** (Claude near its
  cap per the snapshot or user, and GPT failing on every tier): finish the
  checkpoint, state what's done and what's left, and end the turn.

## Benchmark basis (2026-09-23)

Published numbers this routing is based on (vendor sources, differing effort
levels — treat as directional):

| Model | Notable published results | Context | API $/1M in/out |
|---|---|---|---|
| Opus 5.5 | Terminal-Bench 4.0 66.4%, OSWorld 2.0 81.8% partial, HLE (tools) 67.7% | 1M | 4 / 20 |
| Sonnet 5 | numbers only published as charts | 1M | 2 / 10 |
| Haiku 4.5 | SWE-bench Verified 73.3% | 200K | 1 / 5 |
| gpt-6-sol | none published yet | 1.05M | 2 / 10 |
| gpt-6-luna | none published yet | 1.05M | 0.10 / 0.50 |
| gpt-6-astra | GPQA 96.0%, ARC-AGI-2 95.0%, BrowseComp 91.5%, Terminal-Bench 4.0 57.9%, OSWorld 2.0 72.6% partial | 1.05M | 10 / 50 |

Neither vendor publishes per-model subscription quota multipliers, so API
price is only a rough proxy for quota burn. Re-check when Sol/Luna benchmarks
appear.

## Exceptions

- If the user explicitly names a model for a scoped task, honor it for that
  task only, then return to this policy.
- The user can override any of this per session; absent that, this policy
  stands.

## Future: Max/Fable migration

If Claude Max is purchased later, Fable becomes the orchestrator and Opus
moves down to be a primary executor (absorbing most of what Sol currently
does, since Opus's quota expands under Max while GPT stays on Plus). Rule 1
(triage gate) and rule 6 (spec quality) carry over unchanged; rule 2 shifts
from Opus to Fable; Opus's role in "Choosing the delegate" changes from
orchestrator to "hard/precise execution, given a spec." This is a separate
policy revision, not a patch to this file — write a new version rather than
editing this one in place when that happens.
