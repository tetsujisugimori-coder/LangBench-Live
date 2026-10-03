# Windows measurement provenance validation

Count=1 validates provenance, archive, manifest v2, and fail-closed comparator behavior. Controls are synthetic comparator inputs and do not establish observed order coverage, optimization, or performance. archive.json preserves hashes for excluded raw result files; the bundle itself can re-run manifest validation and controls. The artifact ZIP digest is separate from the SHA-256 values of expanded files.
