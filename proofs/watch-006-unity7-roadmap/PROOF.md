# Beast Watch proof 006 — Unity 7 roadmap and Unity CLI discovery

## Result

Beast Watch ingested the 33:08 SpeedTutor video *Unity 7 Roadmap:
Everything Coming Next!* into 260 source-timestamped 1920x1080 frames and
1,705 caption segments. The adaptive pass retained 124 scene-change samples;
58 frames were marked near-duplicates. The evidence bundle fingerprint is
`f62a2b14ff12dc4f582307c109a86e44e2ffd975b1849c6aad34c2abf7ea7b19`.

This run qualifies as video observation, not transcript summarization. At
00:17:03.667, the pixels show a hub-and-spoke architecture that connects a
central **Unity pipeline** to six labeled participants: **Agent, Player, CLI,
Browser, Editor, and Custom**. The nearby narration describes the API,
dashboard, CLI, and app ecosystem, but it does not encode that six-node spatial
topology. The exact frame is bound in `evidence-map.md` by source time and
SHA-256.

The video also exposed a current, useful opportunity for Beast: Unity now has
an official two-part, terminal-native control stack designed for automation and
agents. Unity's current documentation independently confirms that:

- the standalone Unity CLI binary is experimental and manages Editors, modules,
  projects, authentication, and automation with structured output and defined
  exit behavior;
- Editor or development-Player control is **not supplied by that binary alone**:
  the project must separately install and configure the experimental
  `com.unity.pipeline` package;
- with that package connected, CLI commands can discover/execute built-in or
  custom `[CliCommand]` operations and `unity command eval` can execute live C#
  without a project recompile or domain reload; and
- the CLI includes an MCP mode, but MCP-based Editor/Player operations still
  depend on the separately installed Pipeline package. Unity recommends direct
  CLI use as the more robust, extensible, terminal-native path while retaining
  MCP mode for compatible clients.

The public local CLI/Pipeline package and Unity's separate cloud Production
Pipeline are not the same availability claim. The cloud services remain a
closed beta and are not supported for production use during that beta.

## Evidence boundary

### Supported by this proof

- **observed:** Beast inspected real video pixels and retained a visual-only
  architecture fact with a transcript-absence check;
- **observed:** the video presents the combined Unity CLI + Pipeline package as
  an agent-facing Editor/runtime automation surface;
- **verified from current primary sources (2026-08-04):** Unity publicly
  documents the experimental standalone CLI and separately installed Pipeline
  package. Base CLI automation has structured output; Editor/Player control,
  custom commands, live C# evaluation, and the Editor-facing MCP tools require
  the Pipeline package;
- **observed locally:** no `unity` executable was found on `PATH`, and no Unity
  installation was found in the standard Windows locations checked.

### Not supported by this proof

- Unity, Unity Hub, Unity CLI, or the Pipeline package is installed here;
- Codex has controlled a Unity Editor or Player;
- CLI is faster, more reliable, or more capable than MCP on this machine;
- this machine has access to Unity's cloud Production Pipeline closed beta;
- Unity 7 has shipped (Unity currently says early 2027);
- a reusable Unity skill has been compiled or executed; or
- any Unity capability should be promoted into `beast/capabilities.json`.

This source is also **burned for held-out benchmark selection**: the fleet has
discussed it and inspected its evidence. It may be used for development and
pilot work, never represented as unseen evaluation material.

## Smallest next experiment

Do not install an Editor or authenticate as part of this proof. With an explicit
user decision to add the tool, first install only Unity's official standalone
CLI—without the separate Pipeline package—and retain receipts for:

1. binary provenance, version, checksum/signature, and install location;
2. `unity --version`, `unity doctor`, and `unity mcp --help` (command-surface
   discovery only, not proof of Editor control);
3. supported machine-readable formats and exit-code behavior; and
4. clean removal or restoration instructions.

A later, separately approved experiment can install a disposable supported
Unity Editor/project and separately add/configure `com.unity.pipeline`. Only
then can it compare direct CLI commands and the CLI's MCP mode over the same
Pipeline connection on the same scene mutation, test, screenshot, timing, and
recovery gates. A performance claim requires repeated measurements; a
successful mutation alone does not establish superiority.

## Current primary sources

- Unity CLI documentation: https://docs.unity.com/en-us/unity-cli
- Unity CLI release notes: https://docs.unity.com/en-us/unity-cli/release-notes
- Unity CLI technical overview: https://unity.com/blog/meet-the-unity-cli
- Unity CLI/MCP announcement and Unity staff clarifications:
  https://discussions.unity.com/t/announcing-the-unity-cli-a-new-way-to-connect-your-tools-and-agents/1731104
- Unity Production Pipeline availability:
  https://unity.com/features/unity-production-pipeline
- Unity 7 release status: https://unity.com/releases/unity-7
