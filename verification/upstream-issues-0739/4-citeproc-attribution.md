# The `.mcpb` bundles and the container redistribute `citeproc`, which is CPAL/AGPL and asks for an attribution notice Zoteus does not ship

Read on `main` at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release commit). Nothing was executed; the licence texts below were fetched from the citeproc-js repository and the published npm tarball on 2026-09-08.

### What is shipped

`citeproc` 2.4.63 is the only production dependency in the tree that is not permissively licensed. The lockfile records it as `"license": "CPAL-1.0 OR AGPL-1.0"` ([package-lock.json:2107-2112](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/package-lock.json#L2107-L2112)), and the package's own `LICENSE` offers the choice: "This program is free software: you can redistribute it and/or modify it under EITHER the terms of the Common Public Attribution License (CPAL) ... OR the terms of the GNU Affero General Public License (AGPL)".

Two artefacts redistribute it. The `.mcpb` staging step copies `package.json` and `package-lock.json` into the staging directory and runs `npm ci --omit=dev` there ([scripts/mcpb-bundle.ts:250-257](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/scripts/mcpb-bundle.ts#L250-L257)) before packing the whole tree ([:277](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/scripts/mcpb-bundle.ts#L277)), so every bundle carries `node_modules/citeproc`. The container does the same through `npm ci --omit=dev --ignore-scripts` in the `deps` stage and the `node_modules` copy into `runtime` ([Dockerfile:16](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/Dockerfile#L16), [:21](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/Dockerfile#L21)). The npm package does not vendor it: `files` is `["dist", "README.md", "LICENSE"]` ([package.json:28-32](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/package.json#L28-L32)), so `npm i @oscardvs/zoteus` resolves citeproc from the registry rather than shipping it. The obligation attaches to the bundles and the image.

### What the licence asks for

Exhibit B of citeproc-js's CPAL names three things: the copyright notice "(c) Frank Bennett", the attribution phrase "citeproc-js implements the Citation Style Language", and the attribution URL `https://citationstyles.org/`. Section 14(a) asks that they be displayed when an executable launches or a session begins, on the graphic user interface if there is one.

Under the CPAL branch the copyleft is file-scoped, in the MPL-1.1 lineage, so an MIT larger work is fine and citeproc's own files stay CPAL. Nothing about Zoteus's own source is affected. What is missing is the notice, which is the one thing the CPAL adds over the MPL. Under the AGPL branch the whole distributed program would be AGPL, which is not what `package.json`, `mcpb/manifest.json` and `plugin.json` say, so it is also worth stating in writing that Zoteus takes the CPAL option.

### What is there today

`README.md:49` and `:115` credit citeproc-js and link to citationstyles.org, which is a good start and is more than most projects do. There is no copyright notice, no statement of which licence option is taken, and no notices file inside the redistributed artefacts. Grepping the repository for "Frank Bennett", "CPAL" or "Third party" returns nothing.

### Smallest fix shape

Add `THIRD_PARTY_NOTICES.md` at the repository root carrying the three Exhibit B lines and one sentence saying citeproc-js is used under the Common Public Attribution License 1.0, add it to `files` in `package.json` and to the staged bundle in `mcpb-bundle.ts`, and have the server print the attribution phrase once at startup, or return it from `zotero_whoami`. An MCP server's only user interface is its text, so that is the nearest thing to the splash screen Section 14 describes.

### Acceptance criteria

- `THIRD_PARTY_NOTICES.md` exists, names the copyright holder, the attribution phrase, the attribution URL, and the licence option Zoteus takes.
- It is present inside a packed `.mcpb` and inside the container image, not only in the git tree.
- The attribution phrase is displayed once per session by the running server.

### What I did not check

I am not a lawyer and this is not legal advice; it is a reading of Exhibit B against what the artefacts contain. I did not pull the published container image to confirm `node_modules/citeproc` is in it, and inferred that from the Dockerfile. One `docker run --rm ghcr.io/oscardvs/zoteus ls node_modules/citeproc` settles it.
