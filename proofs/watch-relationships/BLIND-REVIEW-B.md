# Blind visual review B

Scope: cases06-10 only. Labels frozen before receiving or reading observer results. Only native visual-review JPEGs, their manifests, and source.webm bytes for SHA256 verification were used as case evidence. No recorder, fixture, telemetry, or observer output was read.

Method: scanned every native JPEG for yellow control fill and bottom input-caption color to locate even one-frame episodes, then used view_image to read full-size input frames, adjacent boundaries, changed status frames, and final frames. Scanned the visible status border extent across all frames to locate state transitions, then visually read both sides of each transition. Source hashes were recomputed from source.webm and matched manifests. PTS values come from manifest native-frame timestamps, inclusive first/last visible frames; no fixed-rate duration padding. Bounds are visually measured outer control rectangles (inclusive pixel extent). Temporal pairs are order-compatible possibilities only. Every case requires causal abstention because displayed sequence alone does not exclude alternatives.

The single-frame input in case08 and both separate inputs in cases06/09 were retained explicitly. Key S in case07 has no pointer-based attribution. Case10 has a result but no visible input. No model observer or provider inference was run by this reviewer.

Inspected full-size frames (hashes independently recomputed and checked against manifest):

| Case | Frame | PTS ms | SHA256 |
|---|---|---:|---|
| case-06 | f-0024.jpg | 920 | dee0d08b338b268e2d01e72617606087198e631709bed4cda975568a49d1274c |
| case-06 | f-0025.jpg | 960 | 24f8e1d02bff19f707f296bba883fe8e35cb4428a1da65f08c2a3f22c679bb02 |
| case-06 | f-0033.jpg | 1280 | 3bd4cc8d0868db9b4aa66b04cb9ce6b12d6a672ac8957abc180d15351241f0cd |
| case-06 | f-0034.jpg | 1320 | fd060a854ea848730e193ff65a018bc49ba5f5208008483f0a1d9471410d8321 |
| case-06 | f-0050.jpg | 1960 | cdef177b1cee83a0f21e03ea0fc412f7548a3d88529814b2db4992c5e5ca286a |
| case-06 | f-0051.jpg | 2000 | 03889ca014a412dd39f431c30d00d8e9c3d4ef8fe09946fecbc869cf1e4c142d |
| case-06 | f-0059.jpg | 2320 | ca32470cb39ef2f5604818d2d3f3ef7c199fedd3d1e73016fcc3e43fd8bfabb2 |
| case-06 | f-0060.jpg | 2360 | 008d175d8c05bbd6e23e160e6c20cfe9b6f36f31008bfcf80f9e197f54b93e47 |
| case-06 | f-0065.jpg | 2560 | 062c98122cd10775833df4b6627bcb64a2ad6e67d2c357ab3a1855e3c0ef41e8 |
| case-06 | f-0066.jpg | 2600 | 64dc20dad2d90ebc0f8f608ad905f4b190ad8e4ccd49b78117372a9f4b7b2f5d |
| case-06 | f-0111.jpg | 4400 | 024461942c25d5a35605f4ca100a8ee8da29fd82249cb2fcb6bac6cdb1964495 |
| case-07 | f-0030.jpg | 1160 | 4e25f06c1b3c4d5c410971c829845e6e81548857075667a5b664cf3f7cec65a8 |
| case-07 | f-0031.jpg | 1200 | 95fdd43e7f98190047c36117279014a73e63fd814d280c5f45ef5c8e0ff566ea |
| case-07 | f-0039.jpg | 1520 | 1b10b3adede394e39140683f15e6e345da37cbc870454d79abcd0bcece10329f |
| case-07 | f-0040.jpg | 1560 | 881c34b1d4ad09b44b71427e9ae8408f4bfde508fcd87cc37a8de19bb4d74d5b |
| case-07 | f-0046.jpg | 1800 | 25ac376bb2586e0e753580c47052231324ee17065c273eb28bfa7abac9371fd4 |
| case-07 | f-0047.jpg | 1840 | 639eaa5b67bd90c960582de406c23dac2fd3338c47dcabf7d735f9e9e7b9c96b |
| case-07 | f-0065.jpg | 2560 | 41c220cbb88d2d510327b0bb1505fcdc9f335c85a9e6eca08f244516bc2f23c6 |
| case-07 | f-0110.jpg | 4360 | b49befa645a564a6d058bbbba42712d3f78c9913dde5ed3e781c6f0f459d7fa2 |
| case-08 | f-0034.jpg | 1320 | 5488624b034a46de65936dfb0ca365a8e74939d14a308f5c3bf420b4c3a4f9e3 |
| case-08 | f-0035.jpg | 1360 | d95fad59440753a64f7aeb1af159c17980728a296ccc1722665e4a9647d3b2fb |
| case-08 | f-0036.jpg | 1400 | 9ff89a3d7c49b96f49a72a32efe50d184f6b253f4cefbdfb294eefda84b8c609 |
| case-08 | f-0042.jpg | 1640 | 5525b6f11b790ae36403f93677e2a04e79ac377477029205496354fd71dedcef |
| case-08 | f-0043.jpg | 1680 | 648754b7defbf25c4f90cbd18829ad99077c969c7c7dae2448ed11b49de4aa87 |
| case-08 | f-0065.jpg | 2560 | 85893db11bb350a2d20cd5e3ce5eb9c30c30e94b92d635ddce1e1839f11ec8c7 |
| case-08 | f-0111.jpg | 4400 | 831e79ca2a9c6cc960221ec62624e39e1c5824b95941418cc99fb3241ff2930e |
| case-09 | f-0025.jpg | 960 | b237c17ff975602ed6644f34892f6f253c9c72d901dc62d18e82eb54ce74811d |
| case-09 | f-0033.jpg | 1280 | 28726a3314d8d5895d91cda4375707921e77d07fe2d00cf0aaa3df39053c0527 |
| case-09 | f-0034.jpg | 1320 | 4350c8fc98db39d7f5a572a8bf544a97e871b8dbb2312b3c1a3c5e6d10c0a653 |
| case-09 | f-0047.jpg | 1840 | 20c3d2b41af6c070a7587e1ff66a0dee1e35d248d0fa56c34a0e32b05a5205ea |
| case-09 | f-0048.jpg | 1880 | f48860ff6fcbaf40a2e5fe18d3710134c0a01258efa1a8072474322c1fddaf32 |
| case-09 | f-0056.jpg | 2200 | 2ef7eb2272f44642975897b6f7460b0cd1aeaf89ab105183b2471632f96bef82 |
| case-09 | f-0057.jpg | 2240 | 9544f6fd221f815caf9484a0477881103795c4205a677a3f6cb283e6159cbe82 |
| case-09 | f-0085.jpg | 3360 | 3dfabd94d7fb23464b791491fbd1740fcca05426ad97361c8703d2505f869321 |
| case-09 | f-0089.jpg | 3520 | 3dfabd94d7fb23464b791491fbd1740fcca05426ad97361c8703d2505f869321 |
| case-09 | f-0090.jpg | 3560 | 66a78599570d02fba226901686fd365486f45f6ab8cbbf350cffce5401879262 |
| case-09 | f-0112.jpg | 4440 | 435283f6ea84f137d96170c484b14e8b10560a9ea83f876f7b86789ecffc6933 |
| case-10 | f-0040.jpg | 1560 | 7fed8797c98de9cd93c2b8b0ca91d33f98929d68e1f53490e2b2f0f364f2bac2 |
| case-10 | f-0041.jpg | 1600 | 7ddb03ff92bfb603e21c9e7a6d0474bb0f58d5cf98089625055d20f45cec604f |
| case-10 | f-0080.jpg | 3160 | ddd25c8d9262ba160658eceb3fa42cc5d32d556a3ae843c2df438d08094bcb4d |
| case-10 | f-0110.jpg | 4360 | 3c38d13032d5bd1521c7798b7491303dc39218f7a48326ed6d83662048c6fb85 |
