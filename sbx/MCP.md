# MCP activation

Implemented: shared dynamic catalog, Browse registration, Rovo registration
plan, and a separate host-local Logseq connection using native V2 permissions.
This is not yet a fully activated deployment. See verification and activation below.

## Shared catalog is the default

Register each approved service once on the Mac with `sbx mcp add`.
New sandboxes created by this launcher use sbx's dynamic gateway mode.
Every dynamic sandbox can discover the shared registered catalog and load
services on demand. Registration makes a service available; it does not
preload every tool into every agent's context or prove a successful connection.

New sandbox creation explicitly sets `OPENCODE_CONFIG_CONTENT={}`. The pinned
upstream kit otherwise injects legacy `{"permission":{"*":"allow"}}`, which
overrides native global denials for built-in agents. Removing that inline
override is required for the native permission setup. Existing sandbox environments
are not changed.

Existing sandboxes retain their current mode and configuration. This launcher
provides no migration, retrofitting or compatibility activation for them.
The test delivery is a newly created disposable sandbox.

Service availability is sandbox-wide. Agent-specific authorization is a separate
layer. Logseq must never be registered in this shared gateway. Its separate
connection is automatically included in new sandboxes when private host setup
exists. Native rules restrict its use to the Logseq agent in the tested
configuration. See the synthetic runtime verification below.

## Browse

The host's existing Browse executable runs over stdio behind the sbx gateway.
The browser relay remains local to the Mac. No extra host mounts, exposed relay
ports, or copied browser credentials are needed.

The reviewed command is fixed to `~/.local/bin/browse mcp`. `mcp_host.py` reads
only the Browse entry from the host's OpenCode JSON configuration. It forwards
only `OPENCODE_BROWSER_RUNTIME` and a small host environment allowlist.
It refuses arbitrary configured commands, extra environment settings, disabled
Browse, and competing JSONC configuration. It does not print configuration.

Registration has been applied globally using the installed Browse runner under
`~/.local/share/opencode-sbx/launcher-mcp/`. That installation has the earlier
22-file manifest; later Logseq and native permission changes are not installed there.
The original `oc` function still uses the original launcher.

An existing `browse` registration is never replaced automatically.
Registering a server is not proof that the browser extension is reachable.

Future approved services, including Rovo, belong in this shared host catalog.
Use sbx's existing registration and discovery mechanisms instead of building
a second per-project service registry.

## Logseq boundary

An actual gateway probe showed unprefixed upstream tools (`status`, `execute`),
alongside generic `mcp-exec` and `code-mode`. Prefix-based service authorization
behind this gateway is not a sufficient boundary.

Instead, `logseq.py` starts the already installed `mcp-logseq` HTTP transport
on Mac loopback only. It uses the existing host Logseq API settings internally.
A separate random MCP bearer token authenticates the sandbox connection through
the host forward proxy to `http://host.docker.internal:12320/mcp/`.
The trailing slash avoids the installed server's POST redirect.

Private host state, created only on explicit activation:

- `~/.config/opencode-sbx/logseq.json`: local endpoint and token-file path.
- `~/.local/state/opencode-sbx/logseq-token`: generated MCP token, mode 0600.

New sandboxes receive only the MCP connection through stdin, never the Logseq
API token. `mcp_runtime.py` atomically adds the named `mcp.servers.logseq`
connection and three native global denial rules to private `opencode.json`
(mode 0600). Existing providers, plugins, servers and unrelated rules are preserved.
Legacy Docker-generated flat server entries are normalized to `mcp.servers`.
Conflicting Logseq connections are refused.

The global rules deny `logseq_*`, listing Logseq resources, and reading Logseq
resources. The mounted Logseq agent is the single source for its exceptions:
default deny, the two Logseq skills, execute/question, Logseq tools and `ask`
for the eight known write/delete operations. No separate access plugin or
duplicate agent definition is installed. Without an agent exception, access
remains denied.

V2 documents that agent rules follow global rules and nested Code Mode calls
enforce tool permissions. These paths have been tested against a synthetic server.
New agent definitions still require review because their own rules can override
global denials. The existing agent
allows `logseq_*` broadly, so newly added upstream tools require review.
Native `ask` supports durable "Allow always" approvals. This implementation
cannot promise a fresh permission dialog for every write. The agent's instruction
to show each change and wait for approval remains a behavioral requirement.
Public gateway tools remain available to other agents.

This is an OpenCode agent/tool boundary. Other agents with arbitrary shell,
filesystem and network access share the sandbox user and could bypass it by
reading the MCP transport token. It is not an OS-level boundary against hostile
agents or malicious plugins. Stronger isolation would require a separate user,
process authority or sandbox and is outside this implementation.

## Rovo

`python3 sbx/mcp.py rovo` prints the shared registration plan:

```sh
sbx mcp add rovo --url 'https://mcp.atlassian.com/v2/mcp?tools=all' --skip-auth
```

The URL is from Atlassian's official guide; the flat tool list is recommended
there for gateways. `--apply` executes the registration only. Authentication
is intentionally separate: the user runs `sbx mcp auth rovo` in their terminal.
Until verified, report it as awaiting authentication, not connected.

## Remaining activation draft

These external changes require approval of paths and content before execution:

1. Install the current 24-file `install-launcher.py:FILES` manifest into a new,
   empty `~/.local/share/opencode-sbx/launcher-mcp-v2/`. Contents are exact copies
   of those repository files. Keep both existing installations.
2. Change only `oc` in `~/dotfiles/zshrc` to:

   ```sh
   oc() { python3 "$HOME/.local/share/opencode-sbx/launcher-mcp-v2/oc.py" "$@"; }
   ```

3. Run the installed `logseq.py` without flags to preview private state, then
   `--apply` to initialize it. The connection JSON is:

   ```json
   {
     "url": "http://host.docker.internal:12320/mcp/",
     "tokenFile": "<absolute HOME>/.local/state/opencode-sbx/logseq-token"
   }
   ```

   The token file contains a new random secret, not the Logseq API token.
   `logseq.py --serve` runs the service in the foreground. No launchd service is
   installed by this implementation; persistent background startup remains
   a separate explicit setup step.
4. Register Rovo as shown above, then let the user authenticate.

Browse is already registered and must not be overwritten. The installed runner
can remain at its current stable path.

## Verification

- Browse is registered and loaded into one existing project sandbox for a transport
  test. Its tools are listed successfully. `status` returns a tool error because
  the host browser relay is not running. Browser operation remains unverified.
- Separate Logseq transport was tested with a temporary read-only host process:
  initialization, nine read tools and a synthetic missing-page lookup succeeded
  from that sandbox. No write tools were exposed; the process was stopped.
- 153 Python tests pass, including native denial configuration, atomic connection publication,
  unrelated configuration preservation, conflicts, private mode and idempotence.
- The earlier custom guard and its synthetic Node tests have been removed.
- Fresh sandbox runtime test, 16 November 2026, found that the upstream kit's
  inline legacy allow-all override bypassed global denials. A second fresh
  sandbox with the override cleared passed 30 checks against OpenCode's actual
  permission engine, then the same 30 checks again after stop/start.
- The matrix covers Main, Build, Plan, General, Explore and the hidden maintenance
  agents; Logseq MCP resources; Logseq read/write, skills and Code Mode; denial
  of shell, file, network and subagent access for the Logseq agent.
- Eight real-model rounds with `openai/gpt-6.1-terra#none` verified direct and
  Code Mode reads, Main's denied Code Mode access, actual loading of both Logseq
  skills, and pending/rejected writes through direct tools and Code Mode.
  The synthetic server recorded exactly three reads and zero writes.
- Two new sessions used Main by default in actual model execution, one after
  restart. Logseq reading and content configuration checks also survived restart.
- A synthetic saved "always" write approval changed the Logseq agent's evaluated
  result from ask to allow, while Main and Build remained denied. The saved
  approval was removed afterwards.
- Both newly created test sandboxes were stopped and retained. No existing
  sandbox was modified. The host launcher, shell configuration, MCP registrations,
  real graph and permanent host Logseq configuration were unchanged.
- The permission test substituted a synthetic stdio server for the private HTTP
  endpoint inside the test sandbox. This verifies the native OpenCode boundary,
  not the complete production launcher, host HTTP transport or service lifecycle.
  Those still require approved activation and end-to-end verification.
- Do not write to the real graph for a permission test.

References:

- <https://docs.docker.com/ai/sandboxes/mcp-gateway/>
- <https://opencode.ai/docs/mcp-servers>
- <https://opencode.ai/docs/permissions>
- <https://opencode.ai/docs/agents>
- <https://support.atlassian.com/atlassian-ai-gateway/docs/get-started-with-the-atlassian-remote-mcp-server/>
