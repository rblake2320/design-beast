# Evidence map

Source: `watched/proof-004-ue58-first-game/timeline.json`

| Procedure fact | Source time | Visual evidence | Confidence |
|---|---:|---|---|
| Create `IMC_Asteroids` and `IA_Move` under Content/Input | 12:40–13:00 | `frames/f_000000760000.jpg` | high |
| Set action value type to Axis2D / Vector2D | 13:35 | `frames/f_000000815000.jpg` | high |
| Configure A/D mapping modifiers (Swizzle, Negate) | 15:05 | `frames/f_000000905000.jpg` | high |
| Add EnhancedInputAction and split Action Value X/Y | 17:20 | `frames/f_000001040000.jpg` | high |
| Test the playable level after movement wiring | 20:35 | `frames/f_000001235000.jpg` | medium |
| Disable controller yaw and orient rotation to movement | 21:00–22:00 | source captions + targeted reinspection required | medium |

The captions are authoritative for sequence, while frames are authoritative
for visible labels and modifier state. Asset existence, Blueprint links,
compile success, and runtime movement are not established by this source alone.
