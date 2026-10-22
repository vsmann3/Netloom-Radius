# Canonical repository proposal: CAF interfaces and activation authorization

Draft contract review only. No runtime code, deployment, live endpoints or release
approval are introduced. Peer owner reviews/merges explicitly; no peer working
tree was edited. Existing canonical v1 schemas elsewhere in this repo are unchanged.

Source CAF commit: `36a574765bf4598e771f15e0daad3b5392d8918f` ([CAF PR #6](https://github.com/vsmann3/caf-portal/pull/6)).
Responds to RADIUS reviews `c57ac35` and `4a103dc`.

Read `ROUND3-AUTHORIZATION.md`, then `ROUND2-RESPONSE.md`. Three proposed schema
resources and their synthetic fixtures are bundled here. Existing canonical
approval/provisioning resources are copied unchanged under `reference/` solely
for offline registry resolution; their source/hash metadata is retained.
Proposal `$id` values are not a claim of frozen canonical versions.

CAF validation at the source commit: 9 baseline + 16 round-two + 13 authorization
offline tests = **38 passed**, plus staged whitespace checks. Repeat from an
isolated CAF checkout of the exact source commit using test-only jsonschema 4.25.1:

```
python scripts/test-radius-contract.py
python scripts/test-radius-round2-contract.py
python scripts/test-radius-authorization-contract.py
```

These tests are fixture/single-process protocol models, not real transaction,
cross-version race, HMAC rotation, authentication or distributed fencing tests.
The directory schema preserves accepted definitions while excluding superseded
singular customer-review definitions from the initial CAF proposal.

Logical CAF authorization commit is the proposed authority point. The later
withdrawal case needs an owner product decision; strict wall-clock cross-DB fencing
is not claimed. Pending later KYC continuation remains separately undecided.
Retention proposals: 15-minute hold, 24-hour snapshot, 30-day feed, 24-hour absolute
credential-ciphertext window with earlier purge on durable acceptance.

The owner instructed both developers to report after this coordination task and
wait for further go-ahead. This draft is published for that report; it does not
request automatic implementation, another review iteration or production work.
