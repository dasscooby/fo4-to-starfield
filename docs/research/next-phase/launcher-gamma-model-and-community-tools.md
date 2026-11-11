# Next phase: the GAMMA-style launcher, legal norms, and community tools to reuse

Written 2026-10-19 by Claude-cloud (the community-reporting thread) for the next-phase report. Cloud research only, with no PC jobs.
Builds on /mnt/project-files/plans/core-launcher/core-launcher-plan-2026-10-17.md (L1 to L5) and does not repeat it.
Labels: **verified** (read in a source or file, linked), **supported hypothesis**, **unresolved**.

## 1. How the precedents actually work

| Project | What ships | What the player supplies | How it builds | Lesson for us |
|---|---|---|---|---|
| STALKER GAMMA | Its own small files on GitHub plus a heavy client from Discord. Third-party add-ons are downloaded from ModDB/GitHub at install time. It "redistributes little to no copyrighted content" (verified, [GitHub README](https://github.com/oleh5230/Stalker_GAMMA)) | Anomaly (free) | The installer fetches each add-on from its original page into a Mod Organizer 2 instance; the pack updates often from the repo (verified, same) | Ship only our code and manifests, and fetch other authors' work from where they host it. Every add-on keeps a link back to its source page |
| Wabbajack | A `.wabbajack` modlist: instructions, hashes, and only the bytes that cannot be sourced elsewhere. Code is GPLv3; modlists are CC BY-NC-SA 4.0 (verified, [LICENSE](https://github.com/wabbajack-tools/wabbajack)) | Their own game, plus downloads from Nexus and other hosts | Every output file is matched by hash to a source: a download, or a file from the player's own game folder. A "Stock Game" copy keeps the real game folder clean, at about 12 GB extra for Skyrim SE (verified, [wiki](https://wiki.wabbajack.org/modlist_author_documentation/Keeping%20the%20Game%20Folder%20clean.html)) | Hash-identify the player's Fallout 4 and DLC before building, and refuse unknown versions. Keep the Starfield folder clean, but a full Stock Game copy is too costly on a nearly full D: |
| Tale of Two Wastelands (TTW) | `TTW Install.exe`; no Fallout 3 content | Legal Fallout 3 and New Vegas installs; the installer finds both paths | Builds a roughly 17 GB MO2 mod folder from the player's own files. Audio re-encoding alone takes about 40 minutes on a Ryzen 5 5600X (verified, [The Best of Times guide](https://thebestoftimes.moddinglinked.com/ttw.html)) | **The closest precedent to ours**: game A's content rebuilt on the player's PC into game B's engine. Expect long, CPU-heavy build steps and a large output, and show progress and the remaining disk need up front |
| Skywind / Skyblivion | Assets remade from scratch, free forever | Legal copies of both games (verified, [Skywind FAQ](https://tesrskywind.com/faq/); [Techdirt on Skyblivion](https://www.techdirt.com/2025/01/03/will-bethesdas-tradition-of-supporting-fan-game-mods-continue-under-microsofts-ownership)) | Normal mod install | Bethesda has tolerated these, but the article frames that as a pattern, not a promise (verified, Techdirt). Nothing published shows a formal permission |
| Fallout London | Its own assets | Fallout 4 | Released through GOG; Bethesda later hired some of its modders (verified, Techdirt) | A large total conversion can ship free and stay up |

## 2. Legal and hosting norms (what applies to us)

- **Nexus forbids uploading another Bethesda game's assets** unless you have permission. A moderator stated it plainly: "Using assets from other Bethesda games is not allowed unless you have permission" (verified, [Nexus forum](https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games)). So no converted mesh, texture, sound or plugin may ever be uploaded, by us or by mods built on the core. This matches the plan's "no redistribution" rule.
- **A tool that converts the player's own copy on their own PC is the TTW model.** TTW has been distributed this way for years (supported hypothesis: we found no published takedown, and no formal Bethesda permission either). Hosting our launcher on Nexus as a utility is likely fine because it contains no assets (supported hypothesis). Whether Nexus moderators accept a tool whose purpose is a cross-game port is **unresolved**; ask Nexus staff before the first upload. GitHub releases plus our own page are the fallback, as TTW uses its own site.
- **Keep it free.** Every precedent is free, and paid access is the clearest way to lose Bethesda's tolerance (supported hypothesis drawn from the precedents: Skywind "will never charge", Daggerfall Unity is free per Techdirt). Avoid paywalled builds and early-access tiers. Donations for hosting only, as Skywind does.
- **Licences of the tools we would ship.** The repo is MIT (verified, `LICENSE`). Our C# writer links **Mutagen, which is GPL-3.0-only** (verified: NuGet licenseExpression for Mutagen.Bethesda.Fallout4 2.8.1-prerelease002). Shipping a compiled `Fo4Export`/writer binary therefore makes that binary a GPL-3 distribution: the source must be offered (it is public already) and the binary's notice must say GPL-3. MIT code can be combined into it. The Python side is unaffected. MO2 is GPLv3 (verified, its LICENSE). This needs a one-line entry in docs/ai/decisions.md before the first release, not a rewrite.
- **Mods built on the core** follow the same rule: ship original content plus FormID references and manifests, never converted assets (plan section 2). Deterministic FormIDs across PCs (plan task L4) are what make that possible. That determinism is still unverified across two machines.

## 3. What the launcher should copy from these tools

1. **Source verification first.** Hash the player's Fallout4.esm, DLC masters and BA2s against a published table (Wabbajack and TTW both refuse sources they cannot match). An unknown version gets a clear refusal, not a broken build. The owner's clean depot (1.10.163) is the first table entry. Next-gen and other versions follow once their hashes are known (unresolved which ones players have).
2. **All DLC assumed, checked loudly.** Per project rule the port assumes every DLC. The launcher lists what is missing by name (Automatron, Wasteland Workshop, Far Harbor, Contraptions, Vault-Tec, Nuka-World) before building, rather than building a partial world.
3. **Disk and time budget before starting.** Like TTW's 17 GB and 40-minute audio step, show the estimate and refuse when the target drive cannot hold output plus scratch. Let the player choose the output drive; this matters now because the owner's D: is nearly full. Measuring our real output size and build time per stage is a task (unresolved today).
4. **Resumable stages with checkpoints.** The converter already checkpoints (docs/RESUMING-BUILDS.md). Expose that as "resume build" after a crash or power cut, the way Wabbajack resumes downloads.
5. **Clean game folder, cheap profile.** Do not copy all of Starfield (Stock Game costs too much space). Install into a managed folder or MO2 instance, record every change in the leader ledger, and restore byte-identically (plan L1/L5).
6. **Add-ons by manifest, fetched from their hosts.** GAMMA-style: third-party mods built on the core are fetched from their own pages and linked back. Our manifest (plan L2) carries the source URL and hash.

## 4. Community tools worth reusing (with licence)

| Tool | Use for us | Licence / status |
|---|---|---|
| Mutagen (C#) | Already our FO4 reader and Starfield writer (`dotnet/*.csproj`, 0.55.0-alpha.67) | GPL-3.0-only (verified). Note our pin is an alpha; NuGet now lists 2.8.x prereleases, so updating is its own task |
| Spriggit (Mutagen-based) | Plugins to text for diffable, reviewable records; also helps prove determinism (L4) | supported hypothesis; licence not checked |
| Synthesis (Mutagen patcher runner) | Model for "patchers run on the player's PC against their load order", the same shape as our build | supported hypothesis; licence not checked |
| Mod Organizer 2 | Optional host for the built output (GAMMA, TTW and Wabbajack all target it); virtual file system keeps Data clean | GPLv3 (verified). Starfield support is a supported hypothesis; needs a test on the PC |
| xEdit / SF1Edit | Manual inspection of built plugins; QA by humans | Licence not checked (the GitHub API was not reachable from this session) |
| Archive2 (Bethesda, ships with the Creation Kit) and BSArch | Packing our built loose files into BA2 for load speed | Archive2 is Bethesda's own CK tool, so the player must have it installed rather than us shipping it (supported hypothesis); BSArch's licence not checked |
| NifSkope (Starfield-capable fork), PyNifly | Mesh inspection and debugging of converted `.mesh`/`.nif` | Licences not checked |
| SFSE and Address Library | Only if measured behaviour needs native code (plan route D) | Player installs them; we never bundle them |

## 5. Open questions for the morning talk

1. Hosting: ask Nexus staff whether a no-assets cross-game conversion tool is acceptable, or plan GitHub releases plus our own page from the start? (Recommend: GitHub first, and ask Nexus in parallel.)
2. MO2 or our own install folder as the default target? (Recommend: our own folder plus the ledger for v0, which matches the plan's L3 and avoids a dependency. MO2 export comes later.)
3. Which Fallout 4 versions to accept at first: only 1.10.163 (the owner's depot), or next-gen too? (Recommend: 1.10.163 only for v0, refuse others with a clear message.)
4. Record the GPL-3 note for shipped C# binaries in decisions.md now.

## Sources
- [Stalker_GAMMA README](https://github.com/oleh5230/Stalker_GAMMA)
- [Wabbajack wiki: Keeping the Game Folder clean](https://wiki.wabbajack.org/modlist_author_documentation/Keeping%20the%20Game%20Folder%20clean.html) and [licence](https://github.com/wabbajack-tools/wabbajack)
- [The Best of Times: TTW install](https://thebestoftimes.moddinglinked.com/ttw.html)
- [Skywind FAQ](https://tesrskywind.com/faq/)
- [Techdirt, 2025-01-03, Bethesda and fan remakes](https://www.techdirt.com/2025/01/03/will-bethesdas-tradition-of-supporting-fan-game-mods-continue-under-microsofts-ownership)
- [Nexus forum: content from other Bethesda games](https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games)
- NuGet registration for Mutagen.Bethesda.Fallout4 (licenseExpression GPL-3.0-only), read 2026-10-19
