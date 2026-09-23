# opus-orchestration-3dprint

A [Claude Code](https://claude.com/claude-code) skill set for running a **Claude Pro + ChatGPT Plus** stack cost-effectively (Opus orchestrates, cheaper models do the work), **extended for 3D printing**: designing printable models as code, checking them, slicing, and sending them to a Bambu Lab printer through Bambu Studio with Claude's computer use.

This is a 3D-printing variant of [opus-orchestration](https://github.com/alisencerefeturk/opus-orchestration). Install one or the other, not both: they use the same skill name.

> **Claude Code only.** This needs Claude Code as the host. It won't work if you load it in Codex, Antigravity, or other agents. See [Compatibility](#compatibility).

| Tier | Where it runs | Role |
|---|---|---|
| **Opus** | main Claude Code session | Classifies tasks, writes specs, synthesizes results, models 3D parts, drives the screen. The only dispatcher. |
| **Luna** (`gpt-6-luna`) | Codex CLI | Default executor for simple and medium work: bulk, research, exploration, scoped implementation. |
| **Sol** (`gpt-6-sol`) | Codex CLI | Precision execution against a complete spec. |
| **Astra** (`gpt-6-astra`) | Codex CLI | Hard reasoning only. It burns quota fastest. |
| **Sonnet** | `sonnet-worker` preset | Claude-side tools, second-opinion review, fallback when GPT fails. |
| **Haiku** | `haiku-worker` preset | Fallback only, for simple work when GPT is unavailable. |

Key ideas:

- **Delegation is one level deep.** Only Opus dispatches work, so every call is auditable.
- **Claude quota is read live.** `statusline.sh` writes it to `~/.claude/rate-limit-status.json` on every message, and Sonnet use is gated on it.
- **Review family follows risk.** High-risk changes are reviewed by the other model family; routine work relies on tests and CI (rule 9, backed by Greptile's 2026 cross-family data).
- **Routing follows data.** It is based on published benchmarks and a small Luna-vs-Sonnet head-to-head (see "Benchmark basis" and rule 5 in `SKILL.md`).

## 3D printing

The `3dprint` skill covers the whole pipeline. Type **`/3dprint`** on its own and Claude starts by asking what you want to make, or add the task right away (e.g. `/3dprint a wall hook for a 12 mm towel rail, PETG`) to skip that question. Describing a print job without the command works too; Claude loads the skill automatically. It loads the routing policy by itself, so `/3dprint` is the only command you need.

1. **Intake:** Claude asks what the job is (new part, decorative, enclosure, existing file, failed print). It asks about your printer once (model, nozzle, AMS slots, filaments), saves that to `~/.claude/3d-printer-profile.md`, and on later jobs only asks "for this printer?". Then it asks the project questions for that kind of job (measurements of what the part must fit, mounting, environment, colours…), skipping anything you already said. It writes a short `brief.md` for you to confirm before any modelling starts.
2. **Model as parametric code:** OpenSCAD by default (models make 3–4× fewer code errors in it than in build123d/CadQuery), build123d only when needed.
3. **Design for FDM:** wall thickness, overhangs, hole clearances, orientation for strength, first-layer details.
4. **Verify before printing:** mesh check (watertight, size, no floating pieces) and rendered previews from several angles, compared against the real object.
5. **Slice** with the Bambu Studio CLI where possible, or open the file in Bambu Studio.
6. **Print** through the Bambu Studio GUI with computer use. Claude **always asks you to confirm** (printer, plate, filament, time, grams) before it presses Print, and never changes printer network or security settings.

Model routing for 3D work (section "3D printing and computer use" in `SKILL.md`): **Opus models single parts itself**, because a spec precise enough to delegate is most of the work already and Opus scores highest on CAD. Luna/Sol make bulk variants, Sol takes over modelling when Opus quota runs high, and Astra is reserved for geometry Opus fails on. Sonnet isn't used for CAD (it scored far lower on BenchCAD), and computer use runs only in the main Opus session. The benchmark data behind this is cited in the skill.

**Image budget:** `render_sheet.py` renders four labelled views into one PNG, sized to Claude's full-resolution limit. The flow is numeric mesh checks first, a draft sheet (~2.6K tokens) while iterating, and close-ups only where a detail needs them. A full-resolution sheet (~4.8K tokens) plus close-ups of every fitting feature are mandatory before a print, so quality isn't traded for tokens.

The tier labels in the skill are Turkish: **basit** = simple, **orta** = medium, **zor** = hard.

## Contents

```
skills/opus-orchestration/SKILL.md   the routing policy (loaded as a Claude Code skill)
skills/3dprint/SKILL.md              3D modelling → verification → slicing → printing workflow
skills/3dprint/render_sheet.py       labelled 4-view preview sheet, sized for Claude's vision limits
agents/sonnet-worker.md              Sonnet preset
agents/haiku-worker.md               Haiku fallback preset
statusline/statusline.sh             statusLine hook that snapshots quota usage
install.sh                           symlinks everything into ~/.claude
```

## Install

Requirements: Claude Code on a Pro or Max plan (Pro/Max accounts are the only ones that expose `rate_limits`, and computer use needs Pro/Max too), [Codex CLI](https://github.com/openai/codex) signed in with ChatGPT, and Python 3.

For 3D printing, also:

- **macOS** (computer use in the Claude Code CLI is macOS-only);
- [OpenSCAD](https://openscad.org) (`brew install --cask openscad`);
- [Bambu Studio](https://bambulab.com/en/download/studio), signed in and connected to your printer;
- `trimesh`, `scipy` and `pillow` for mesh checks and preview sheets (`pip3 install trimesh scipy pillow`);
- computer use enabled once: in Claude Code run `/mcp`, select `computer-use`, choose **Enable**, then grant Accessibility and Screen Recording when macOS asks.

### Option A: let Claude Code install it (easiest)

Paste this into a Claude Code session:

````text
Install the opus-orchestration-3dprint skills from https://github.com/alisencerefeturk/opus-orchestration-3dprint for me:

1. Clone the repo to ~/opus-orchestration-3dprint. If that folder already exists and is this repo, run `git pull` in it instead.
2. Run ./install.sh from the repo. It symlinks the two skills, the agent presets, and statusline.sh into ~/.claude and backs up any existing files first.
3. Add "statusLine": {"type": "command", "command": "~/.claude/statusline.sh"} to ~/.claude/settings.json. Merge it and keep every other setting as is. If a different statusLine is already configured, show it to me and ask before replacing it.
4. Check the prerequisites and report each one: `python3 --version`, `codex --version`, whether Codex is logged in (`codex login status`), whether OpenSCAD is installed (`openscad --version` or /Applications/OpenSCAD.app), whether Bambu Studio is in /Applications, and whether `python3 -c "import trimesh, scipy, PIL"` works. If something is missing, tell me how to fix it, but don't install it yourself.
5. Remind me to enable computer use once via `/mcp` → computer-use → Enable (it asks for Accessibility and Screen Recording permissions).
6. Tell me to restart Claude Code, then summarize what was installed and anything I still need to do by hand.
````

### Option B: manual

```bash
git clone https://github.com/alisencerefeturk/opus-orchestration-3dprint.git
cd opus-orchestration-3dprint
./install.sh
```

`install.sh` symlinks the files into `~/.claude`, moving any existing files to `~/.claude/backups/opus-orchestration-<timestamp>/` first. Because they are symlinks, edits from either side show up in `git diff`.

Then enable the status line in `~/.claude/settings.json`:

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh" }
```

## Compatibility

| Host | Works? | Why |
|---|---|---|
| **Claude Code** (CLI, desktop, IDE extensions) | ✅ | This is what it was built for. |
| **OpenAI Codex CLI / ChatGPT** | ❌ | In this setup Codex is a worker that Claude Code calls, not the host. |
| **Google Antigravity, Cursor, other agents** | ❌ | They have no equivalent of the Claude Code features listed below. |

The policy relies on four Claude Code features:

- the `Agent` tool and `~/.claude/agents/` presets, for dispatching `sonnet-worker` and `haiku-worker`;
- the `statusLine` hook, which provides `rate_limits` for live quota checks;
- Opus running as the top-level session model;
- Claude Code's skill loader.

Another agent might be able to read `SKILL.md` as plain text, but it can't apply the routing. The general ideas carry over to other stacks: a scarce orchestrator, cheap default workers, one-level delegation, and routing gated on quota. The implementation doesn't.

## Adapting it

No ChatGPT Plus / Codex? The policy falls back to Claude-side execution when GPT dispatches fail (see "Continuity" in `SKILL.md`). For CAD, that means Opus models directly rather than Sonnet.

Model IDs, quota thresholds (60% / 70% / 85%), and benchmark numbers reflect one account as of September 2026. Check `codex` → `/model` for the IDs available to you, and tune the thresholds to your own usage.

## License

MIT — see [LICENSE](LICENSE).
