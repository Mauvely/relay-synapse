# Relay on Synapse

An experimental AGPL-3.0-or-later distribution of upstream Synapse with PostgreSQL and organisation messaging policy. Run `python3 configure.py matrix.example.org` once, then `RELAY_UID=$(id -u) RELAY_GID=$(id -g) docker compose up --build -d`. Terminate TLS at your reverse proxy, forward Matrix requests to loopback port 8008, and configure both Matrix discovery documents when using a delegated name. Back up the private config, PostgreSQL volume and signing-key/media volume together.

Edit `config/policy.json` by atomic replacement. The file maps full Matrix user IDs to stable organisation IDs. Each organisation has a policy of `open`, `closed` or `allowlist`; `allow` contains stable partner organisation IDs. List only servers operated under the same admission policy in `managed_servers`. Accounts absent from the mapping are individuals. Registration is closed. Use Synapse's register_new_matrix_user command inside the container for provisioning.

The pinned base image runs Synapse's normal room and event checks. A small build-time patch adds policy checks on inbound and outbound direct-to-device messages. Cross-server restricted admission and policy changes in occupied federated rooms require interoperability verification before using this distribution for enterprise isolation.

The shared admission fixtures are in `policy-cases.json`. To run them from a checkout after building the image, use `docker compose run --rm --no-deps -v "$PWD:/test:ro" --entrypoint python synapse /test/test_policy.py`. The fixture suite uses synthetic Matrix IDs and stable organisation IDs.

A federated invite can arrive before the receiving homeserver has full room state. This distribution currently refuses such an invite for a restricted user. Multi-server restricted rooms need a trusted room-state admission protocol before release. A local policy tightening takes effect on the subsequent gated operation; recipients retain events and keys already delivered.
