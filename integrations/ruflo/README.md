# Optional locked Ruflo runtime

This directory contains package manifests only, not vendored code, model weights or user state. `package-lock.json` pins the complete resolved npm dependency tree and integrity hashes. A CLI-only `ruflo@3.56.9` pin does not pin its transitive dependencies.

Copy both JSON files to a trusted runtime folder outside the writable project, then run `npm ci --prefix THAT_FOLDER --no-audit --no-fund`. Installation downloads packages and may run their native installation scripts; review the dependency tree first. See `docs/RUFLO_RUNTIME.md` in the Forge source for Linux/Windows commands and explicit read-only runtime grants. Do not place provider keys in npm manifests/configuration.
