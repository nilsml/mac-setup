# MCP connections and agent permissions

Implemented and activated on the configured Mac: a shared dynamic catalog for
Browse and Rovo, and a separate host-local Logseq connection using native V2
permissions. Readwise is also registered and authorized in the shared catalog.
This file explains the mechanisms and their limitations.
For architecture diagrams, daily use and troubleshooting, start with
[README.md](README.md).

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
exists. Native rules restrict its use to the personal assistant (now named Fokus)
in the tested configuration. See the synthetic runtime verification below.

## Browse

The host's existing Browse executable runs over stdio behind the sbx gateway.
The browser relay remains local to the Mac. No extra host mounts, exposed relay
ports, or copied browser credentials are needed.

The reviewed command is fixed to `~/.local/bin/browse mcp`. `mcp_host.py` reads
only the Browse entry from the host's OpenCode JSON configuration. It forwards
only `OPENCODE_BROWSER_RUNTIME` and a small host environment allowlist.
It refuses arbitrary configured commands, extra environment settings, disabled
Browse, and competing JSONC configuration. It does not print configuration.

Browse is registered globally using the installed runner through
`~/.local/share/opencode-sbx/launcher-current/`. The `oc` shell function uses the
same symlink, so both follow launcher updates.

An existing `browse` registration is never replaced automatically.
Registering a server is not proof that the browser extension is reachable.

Other approved public services, including Rovo, belong in this shared host catalog.
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
connection and three native global denial rules to the sandbox's `opencode.json`.
The file is written with mode 0600, but the upstream gateway startup rewrites it
as 0644 on each start. All agents share the sandbox user, so file mode is not a
boundary in either case. Existing providers, plugins, servers and unrelated rules are preserved.
Legacy Docker-generated flat server entries are normalized to `mcp.servers`.
Conflicting Logseq connections are refused.

The global rules deny `logseq_*`, listing Logseq resources, and reading Logseq
resources. The mounted Fokus agent is the single source for its exceptions:
Logseq tools are allowed, with `ask` for the eight known write/delete operations.
Fokus now inherits ordinary OpenCode tool access instead of a blanket deny.
Its focus is enforced through its mandate and workflow instructions.
No separate access plugin or duplicate agent definition is installed.
Without an agent exception, access
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
sbx mcp add rovo --url 'https://mcp.atlassian.com/v2/mcp' --skip-auth
```

The URL is from Atlassian's official guide. The `?tools=all` variant fails
sbx 0.53.0's resource-identity check because the OAuth metadata names the URL
without its query. Supplying `--resource` did not bypass that check; the canonical
URL registered successfully. `--apply` executes the registration only. Authentication
is intentionally separate: the user runs `sbx mcp auth rovo` in their terminal.
On the configured Mac, authorization, dynamic loading and tool catalog access
have been verified. This does not prove a particular Jira or Confluence operation
works; no company content was read or written for the connection test.
Granted OAuth permissions include writes, so the connection is not read-only.

## Readwise

Readwise uses the existing shared gateway, with no custom proxy or host service:

```sh
sbx mcp add readwise --url https://mcp2.readwise.io/mcp --skip-auth
sbx mcp auth readwise
```

Registration and sbx authentication are complete on the configured Mac.
Dynamic sandboxes can discover and load the service. Old static
sandbox configurations are not migrated. Credentials are managed by sbx on
the host rather than copied into each disposable sandbox.

On 17 November 2026, a dynamic test sandbox successfully discovered and loaded
Readwise and listed 22 upstream tools, including all five expected reading
tools. No library operation was called or personal reading content retrieved.
The test sandbox was stopped afterwards.

This shared route is available to agents with ordinary gateway permissions,
including Fokus. Readwise exposes write, delete and export operations as well
as reads. The Fokus prompt requires relevant, minimal reading by default and
approval before changing external systems. This is a behavioral requirement,
not a gateway-level read-only guarantee.

The Mac's ordinary OpenCode has a separate, already authorized Readwise
connection with global denial rules and five read exceptions for Fokus.
That direct connection's restrictions do not apply to the sbx gateway.

Fokus prefers `berget/moonshotai/Kimi-K3.1-Pro`. A synthetic direct test and
a delegation test confirmed Berget/Kimi usage, including when the parent used
a different model. Switching the main agent in an existing session does not
automatically switch the session's stored model.

## Installed configuration and first-time setup

Current activation state (20 November 2026): `oc`, the Browse registration and
the Logseq LaunchAgent all use the symlink
`~/.local/share/opencode-sbx/launcher-current`, so they follow launcher updates
without re-registration. Older launcher folders are retained because existing
sandboxes were created with their kits. Browse relay and its
extension are connected; dynamic discovery, loading and the Browse `status`
tool succeeded from the v2 test sandbox without reading private tabs.
Rovo is registered at the canonical URL and is authorized.
The installed helper has now been synchronized with those source changes.
Logseq now runs under the approved `com.opencode-sbx.logseq` user LaunchAgent.

Browse lifecycle verification showed that no custom LaunchAgent is needed:
with our Browse LaunchAgent unloaded and the relay stopped, MCP initialization
and `status` did not start the relay, but an ordinary `session_new` call did.
A subsequent MCP `status` succeeded, and the extension was connected. The test
session was deleted without reading private tabs. Our Browse LaunchAgent is
unloaded and its plist removed after approval. Let Browse manage its
own relay instead of using `browse serve` as a permanent service.

The following describes the setup already performed on the configured Mac.
On a new Mac these are explicit host changes, not automatic bootstrap steps:

1. Install the `install-launcher.py:FILES` manifest into a new, empty
   `~/.local/share/opencode-sbx/launcher-vN/` and point the symlink to it:
   `ln -sfn launcher-vN ~/.local/share/opencode-sbx/launcher-current`.
   Existing nonempty installations are not overwritten.
2. `oc` in `~/dotfiles/zshrc` is:

   ```sh
   oc() { python3 "$HOME/.local/share/opencode-sbx/launcher-current/oc.py" "$@"; }
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
   `logseq.py --serve` runs the existing MCP service in the foreground.
   On the configured Mac,
   `~/Library/LaunchAgents/com.opencode-sbx.logseq.plist` starts
   `launcher-current/logseq.py --serve` at login and restarts it when it exits.
   The plist is local setup; it is not
   installed by `install-launcher.py`. Logseq itself and its HTTP API must
   also be running.
4. Register Browse with `python3 ~/.local/share/opencode-sbx/launcher-current/mcp.py
   browse --apply`. The plan keeps the `launcher-current` path. Registration
   refuses to replace an existing entry; remove it first with
   `sbx mcp rm --force browse`.
5. Register Rovo as shown above, then let the user authenticate.

## Verification

- The initial Browse transport probe listed tools but failed `status` with no
  running relay. Later lifecycle and navigation tests below supersede that result.
- The initial separate Logseq transport test used a temporary read-only host process:
  initialization, nine read tools and a synthetic missing-page lookup succeeded
  from that sandbox. No write tools were exposed; the process was stopped.
- 154 Python tests passed at the last code change, including native denial configuration, atomic connection publication,
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
  The later launcher test below covers the real host route separately.
- End-to-end launcher test, 16 November 2026: the 24-file installation from
  commit `8decc04` in `~/.local/share/opencode-sbx/launcher-mcp-v2/` created a
  new sandbox through `start.py --content --setup-only`. Content layers, model
  keys, the cleared inline override and the Logseq connection were configured.
  Both `logseq` (host HTTP route, foreground `logseq.py --serve`) and the gateway
  reported connected. The Logseq agent read a synthetic missing page through
  Code Mode against the real graph; Main's equivalent call was unknown/denied.
  No writes were attempted against the real graph. The sandbox and host
  service were stopped afterwards.
- Browse navigation to NRK succeeded through the gateway and an actual OpenCode
  agent call. Two natural-language requests with Claude Sonnet 5 also succeeded
  in a new sandbox after adding a kit instruction about the two `execute` layers.
  One attempt first guessed incorrect tool names before recovering; instructions
  reduce model mistakes but do not eliminate them.
- Those Browse tests used the API exposed on 16 November 2026. Newer releases
  expose tab-oriented tools such as `navigate` and `snapshot`; consult the actual
  catalog rather than assuming the old `execute` API exists.
- Rovo authentication and gateway discovery/loading/catalog access succeeded.
  No Jira or Confluence operation against company content was tested.
- Do not write to the real graph for a permission test.

References:

- <https://docs.docker.com/ai/sandboxes/mcp-gateway/>
- <https://opencode.ai/docs/mcp-servers>
- <https://opencode.ai/docs/permissions>
- <https://opencode.ai/docs/agents>
- <https://readwise.io/mcp>
- <https://support.atlassian.com/atlassian-ai-gateway/docs/get-started-with-the-atlassian-remote-mcp-server/>
