# Blind visual review A

Independent labels for cases 01-05, frozen before observer evaluation. Only native visual-review JPEGs, their PTS manifests, and source.webm bytes (SHA-256) were used. No recorder, fixture, private telemetry, observer output, or scenario description was read.

Method: scanned every native JPEG using pixel thresholds for yellow pressed-control and bottom input-indicator regions. Scanned consecutive status-region pixel differences to locate changes. Then visually inspected full native frames at each input onset/last-down/release, result onset and immediately preceding frame, and final frame. PTS came from manifest probe frame entries, not wall-clock or presumed frame rate. Source hashes were independently recomputed. No real-time video playback was performed; visual inspection used its native extracted frames.

Visible button white-border bounds are inclusive pixel extents encoded as x,y,width,height. Pointer centers are approximate visible magenta-dot centers. All event/result intervals are first/last visible native PTS inclusive, with 40 ms observation granularity. Results persisting to final frame are right-censored by clip end. Temporal pairs use zero-based indices and result onset ordering, not persistence overlap. All causal labels abstain because visual sequence cannot exclude unseen alternatives. Case 05 specifically has a result before its input. Case 04's control identity is Inspect despite later Saved status.

## Inspected frame receipts

| Case | Native frame | PTS ms | SHA-256 |
|---|---|---:|---|
| case-01 | f-0027.jpg | 1040 | b7d07c2f4641904e11b2e207f59dbe7d04e479554a3ad0efd49506a31df0ead1 |
| case-01 | f-0028.jpg | 1080 | 8eefed5f219ce3f4fa867ee8f2bd7849550eb151df85c052c04955ef4281eaf0 |
| case-01 | f-0036.jpg | 1400 | 2b005bc0a5f7a62a090e66c5df2083fba9113cd3776aae96e307b901de44f074 |
| case-01 | f-0037.jpg | 1440 | 1fe261f7b01a81ff31d1bc782209e402568715eb3a96a094d52d346c5693d077 |
| case-01 | f-0042.jpg | 1640 | cbaec8a8555ce2ecb2e668059bf6b6777eebe07db18df47516abc155827723bb |
| case-01 | f-0043.jpg | 1680 | 55e243b3988192f6ac25c0ee84e5d336aa19ce5dde53c262b537717b49f83fb7 |
| case-01 | f-0106.jpg | 4200 | 8c4d38fc3e4cfb88b013014bbf436788e68fbbd81e1436fc4bb5e850a0716d1e |
| case-02 | f-0031.jpg | 1200 | 698df8c05df18c545609fa0794ba1ebeac4d85bf99fe88b39a6d197b22254fd6 |
| case-02 | f-0032.jpg | 1240 | 46826b360529a1a962e6f25ff6971433470316e239451db7f6e04ae73f3778d0 |
| case-02 | f-0040.jpg | 1560 | 715122949656ea6df41e43bfb8f68ee1872884733da49d9fc305cf716319c619 |
| case-02 | f-0041.jpg | 1600 | 1d596f9a2d737c466508c4676de691e47e80c6522a97e0eef2dc5ed4e317ac3f |
| case-02 | f-0047.jpg | 1840 | 9a959cd6d27be81d8645945e37a102713b229f10027da1862ded53adb50850d5 |
| case-02 | f-0048.jpg | 1880 | b747a3419206407199e65e80ebc532477e8240de3e61a7fad865e2aabd880985 |
| case-02 | f-0111.jpg | 4400 | 4a5e7551433d858e352da5db2bab59bac6d08cc5c44866f7bf96fc1edd464627 |
| case-03 | f-0031.jpg | 1200 | 402c558290ca263e5bf96bc7ec561899c8bfeb046fff74e70023d63a2395a77b |
| case-03 | f-0032.jpg | 1240 | 7d261b4e16433d5cc010fed0b08077ce1547834ca81aef5784336d8bb418376a |
| case-03 | f-0040.jpg | 1560 | 8141cd66f658797b58b7c3a4a5990e45e698f403149b0e7e80f292843fad4b20 |
| case-03 | f-0041.jpg | 1600 | bb63523958988dbbff6c9b4ee7d4078e663f712b6399b063777cda6e0139ff04 |
| case-03 | f-0046.jpg | 1800 | 601a5cd2fc8d7fa9198e1d310b40f23977bfb8cb3663c6e0d97ce9d4be4b5c12 |
| case-03 | f-0047.jpg | 1840 | 78af2c5ef9422183a26f5fcc572f95b6708049a545b16adff8b48b121f74c7b2 |
| case-03 | f-0109.jpg | 4320 | d22f550fdaadd12585b94aad61bc917c182b1feb8a340b8f965e6272a4a11e29 |
| case-04 | f-0031.jpg | 1200 | 4942483b2aa421868835f338066d0847e553e52a7226a3db7d2ee18a480a3acc |
| case-04 | f-0032.jpg | 1240 | 2e438fefc55c5df6fe8f7ec40800bcf0606b6073a7393745a871a03331819479 |
| case-04 | f-0040.jpg | 1560 | 09e5cb99677a87107e86857e3282175ce14f3eaf35814dbe2bc3e4ddee339981 |
| case-04 | f-0041.jpg | 1600 | 5cf36b743adf377ff539c558f8e02e0efa5b20e3024f600d1320a886fa727319 |
| case-04 | f-0053.jpg | 2080 | a90906a17cf2de451ceb2bd3375cd24381cc0c64c7a42e41a5a9a31e05007164 |
| case-04 | f-0054.jpg | 2120 | eeb47662a27f31174efe36d6d60229fe3b638418390174b2b157d51b277c0733 |
| case-04 | f-0110.jpg | 4360 | 4a1c645907dbc78e53f77d3a07aeaadf739bc4a5dc8106d9c6b8133ea91f9e9e |
| case-05 | f-0020.jpg | 760 | adb6c74e58aaf2bda6f3660411afc1b1061cfd723c41d9fd2f9a639109c2f9ec |
| case-05 | f-0021.jpg | 800 | 73091364cf0a5b5a2c733bf10bd1a3976dc3cc0a0d0ce4d735ef2121f02ff0bd |
| case-05 | f-0046.jpg | 1800 | e31722ad74a82fef9388246f53589c899a8cb209dbcf125684abe30cd4a04746 |
| case-05 | f-0047.jpg | 1840 | c4f3f8f7e4d6237f9fadca1a5a30dcf3dd81bb629bd8c064083acfcd5dd18e8a |
| case-05 | f-0055.jpg | 2160 | 3921b7eaa60939ea92a271b062d9b331e2971f8100a94c6c187c7c4edf7b335f |
| case-05 | f-0056.jpg | 2200 | 4065bd0688c62f320d0614960ecb190cabd91085b4bd87a14e3fd3a1841e0bd3 |
| case-05 | f-0110.jpg | 4360 | bf6ac53585d883873415b8114a5bd9ab4f06a2c5d5e4b6f80c44f0d3f47ace1b |

