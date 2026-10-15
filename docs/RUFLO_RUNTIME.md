# Reproducible optional Ruflo runtime

Forge connects to Ruflo 3.56.9 through its actual MCP service. Pinning that CLI alone is insufficient: transitive dependencies can change, along with available tools and behavior. The reviewed manifests in `integrations/ruflo/` now lock the resolved dependency tree and npm integrity hashes. CI uses `npm ci`, not a fresh floating install.

This is still separately installed software, not bundled application code or a promise that every optional upstream backend works. Installing downloads packages and may run their installation scripts. Read the manifests before running the commands. No provider account is needed for the local acceptance workflows.

## Linux / WSL

From the Forge source directory, choose a trusted runtime directory **outside the project agents will edit**:

```sh
runtime="$HOME/.local/share/agent-forge-ruflo"
mkdir -p "$runtime"
cp integrations/ruflo/package.json integrations/ruflo/package-lock.json "$runtime/"
npm ci --prefix "$runtime" --no-audit --no-fund
export FORGE_RUFLO_BIN="$runtime/node_modules/.bin/ruflo"
```

Start Forge from that environment. Broad tools also require explicitly approved read-only runtime grants in Setup; the entire runtime prefix may be needed for sibling dependencies. Do not grant the whole home folder or put credentials in a granted runtime. Network remains separately permission-gated.

## Native Windows

The equivalent separately approved installation uses PowerShell:

```powershell
$runtime = Join-Path $env:LOCALAPPDATA 'AgentForgeRuflo'
New-Item -ItemType Directory -Force $runtime | Out-Null
Copy-Item integrations/ruflo/package.json,integrations/ruflo/package-lock.json $runtime
npm ci --prefix $runtime --no-audit --no-fund
$env:FORGE_RUFLO_BIN = Join-Path $runtime 'node_modules/.bin/ruflo.cmd'
```

This installation does **not** make Windows filesystem enforcement release-ready. Broad gateway launches remain fail-closed until native acceptance permits them. Standard terminal support is a separate feature.

## Scope

The lockfile stabilizes versions and verifies downloaded package hashes; it is not a security audit or an implementation of missing upstream services. Approved updates require a new lockfile and real integration tests. Unsupported/error responses must remain failures, not be converted into successful tool execution. Forge SQLite and explicit dispatch/review policy remain authoritative even when upstream workflow/task/swarm tools are used in their own namespace.

The upstream lock includes bundled children covered by their parent package hash and three unavailable optional musl/GNU platform placeholders. Those placeholders are not working backends or cross-platform acceptance. The tested Linux x64 runtime uses resolved artifacts; native Windows runtime/backend combinations need their own tests.
