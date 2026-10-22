# Local Radius and CAF developer coordination

The owner authorized direct communication between the existing Codex sessions.
This machine's Codex CLI 0.163.0 provides `codex queue --thread <UUID> --message
<text>` and `codex agents`. GitHub identity alone does not connect sessions.

The first message was successfully queued to the CAF workspace session on
2026-10-22. Peer acknowledgement is still required; queue success confirms
acceptance by Codex, not that the peer has read or acted on the message.

Local session IDs belong in ignored `.tools/codex-peer.json`, for example:

```json
{"thread_id":"<verified CAF session UUID>","workspace":"E:\\OpenCode\\caf-portal"}
```

Send a milestone or interface proposal from PowerShell:

```powershell
./scripts/notify-caf-agent.ps1 -Message 'Radius: commit <SHA>; interface impact: ...; validation: ...; request: ...'
```

Use `-Thread <UUID>` to override the local peer. If a session is replaced, verify
its identity and update the local file. Queue exact session UUIDs: the displayed
session title did not resolve as an active session name during setup.

Each developer should persist equivalent notification instructions in its own
workspace. Agents send updates as part of their work; no background file watcher,
Git hook or always-running autonomous development loop is installed. A closed or
unavailable session may require resuming by the owner. Never claim receipt without
a reply, or automatically start a duplicate developer to get around a delivery issue.

Keep the shared handoff, schemas and GitHub PRs as durable design records. Send
changes, relevant test results and blockers directly; reserve the owner's input
for product decisions and actions requiring their actual access. Keep production
changes within the authorization and release process of each repository.
