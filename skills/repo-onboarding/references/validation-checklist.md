# Validation Checklist

## Coverage

- Every important owned directory has a home.
- The root file names the top-level layout correctly.
- Child files exist only where local rules genuinely differ.
- Generated and vendor directories are not treated as authored code.
- The repo's real instruction convention is preserved, not replaced.

## Consistency

- Parent and child docs do not conflict.
- Commands in docs match the real task or build entrypoints.
- Paths in docs exist.
- Naming matches the repo's established convention.
- Any cross-reference between files resolves to an existing path.

## Completeness

- Each major domain has at least one agent pass.
- Shared modules are described once, not repeated everywhere.
- Cross-domain links are called out where they matter.
- Open questions and assumptions are listed explicitly.
- The final tree has at least one verifier pass.

## Final Pass

Before finishing, do one more scan of:

- root docs
- top-level domains
- large nested packages
- any folder with special build or test behavior

If the scan finds an important folder without guidance, rerun the narrowest agent needed to cover it.
If the scan finds no change in behavior below a level, collapse that level back into its parent.
