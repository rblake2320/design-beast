# Source-time evidence map

Source: https://www.youtube.com/watch?v=Zd7Qv4SdRxU  
Title: *Unity 7 Roadmap: Everything Coming Next!*  
Channel: SpeedTutor  
Selected range: 00:00:00.000–00:33:07.517  
Video SHA-256: `c21ec769a2f4ee44c04fb958d06e637c40f0a51b9146f514d10a5c118e0255b6`  
Bundle fingerprint: `f62a2b14ff12dc4f582307c109a86e44e2ffd975b1849c6aad34c2abf7ea7b19`

## Visual observations

| Source time | Frame and SHA-256 | Pixel observation | Transcript comparison |
|---|---|---|---|
| 00:15:55.000 | `frames/f_000000955000.jpg` — `77fa84007f906637b887820d2c705bbf318ac3f2ec1731cf11d07a65ba41f580` | Slide title reads `Agentic Authoring`; the on-screen interface visibly includes a model selector and project/file panes. | Narration discusses orchestration and token usage. The visible interface layout and controls are not encoded in the transcript. |
| 00:17:03.667 | `frames/f_000001023667.jpg` — `943760335599f7e8ca42a176109e1e966854298a1e15abdf346a4ad8ccc7f7e1` | A central `Unity pipeline` is joined by bidirectional arrows to six labeled nodes: `Agent`, `Player`, `CLI`, `Browser`, `Editor`, and `Custom`. The left side lists a single API, web dashboard/deep links, pluggable source control/compute, and CLI as a first-class automation entry point. | The 00:16:53.920–00:17:24.480 narration states the API/dashboard/CLI capabilities, but does not enumerate or spatially encode the six-node topology. This is the strongest visual-only fact. |
| 00:17:25.000 | `frames/f_000001045000.jpg` — `fd311994f9411307cf3107afa6a338057658d856efe0e4cea1cbbad59418b597` | Slide labels the broader `Unity pipeline` as `Closed Beta` and separately lists CLI properties: fast arbitrary code, bring your own agent, custom commands, and Editor/runtime access. | Narration substantially corroborates the bullets, but the slide does not expose the installation boundary. Current Unity documentation resolves it: the standalone CLI is public and experimental, while Editor/Player control, custom commands, live evaluation, and Editor-facing MCP operations require the separately installed `com.unity.pipeline` package. Unity's cloud Production Pipeline is a third, closed-beta scope. |
| 00:24:25.000 | `frames/f_000001465000.jpg` — `ff92ba47d327fa8bf1960f7d805bd9707f2f9262503ea617713808fb94b269f0` | Content-directories slide visibly lists smaller incremental builds, lower memory, asynchronous multithreaded loading, granular processing, and an opt-in path for existing Addressables projects. | This was inspected as roadmap context but was not compiled into a Beast capability. |

Frame paths are relative to the local retained Watch bundle
`watched/unity7-roadmap-Zd7Qv4SdRxU/`. Raw video and frames are not published in
git; their hashes and the evidence bundle fingerprint bind this report to the
local source evidence.

## Reinspection record

The adaptive pass placed a scene-change sample exactly at 00:17:03.667 and a
periodic sample at 00:17:25.000. Both were opened at original resolution and
read directly. No dense seek was required because the relevant content was a
stable slide rather than a transient click or ambiguous motion. If a later
procedure depends on a transient UI action in this source, it must run a dense
seek around that action rather than inherit this inspection.

## Transcript-absence method

The transcript was searched for the capability text (`single API`, `dashboard`,
`deep links`, `pluggable`, `domain reload`, `custom commands`, `MCP mode`) and
the matching interval was read in full. This established that the narration
does contain most capability claims. The published visual-only claim is
therefore intentionally narrow: the exact six participants and their
hub-and-spoke relationship are recoverable from the pixels, not from the words.
