# Updating an installed chimera

Plugin updates pass through three layers that do NOT sync automatically —
skipping a step can leave a stale version serving for weeks. Run all
steps, in order.

## The three layers

```
GitHub repo  →  marketplace mirror  →  install cache  →  live session
   (push)        (marketplace update)   (plugin update)    (restart)
```

## Procedure

1. **Push** the new version to GitHub (`main` branch), with
   `.claude-plugin/plugin.json` version bumped.
2. **Refresh the marketplace mirror:**
   ```
   /plugin marketplace update chimera
   ```
3. **Update the installed plugin** (rebuilds the install cache):
   ```
   /plugin update chimera@chimera
   ```
   If that fails or seems stale: `/plugin uninstall chimera@chimera` then
   `/plugin install chimera@chimera`.
4. **Restart the session.** Hooks and the injected bootstrap load at
   SessionStart only — a live session keeps running the old version.
5. **Verify:** the version shown by `/plugin` for chimera matches
   `plugin.json`, and a fresh session's context contains the
   `CHIMERA_BOOTSTRAP` block (visible via the SessionStart hook output).

## Local development installs

For testing unreleased changes, add the local repo as a marketplace:
`/plugin marketplace add ~/dev/chimera` — then install from it. Remember
the same cache/restart rules apply.
