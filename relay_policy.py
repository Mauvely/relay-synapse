"""Mauvely room and device admission for pinned Synapse. SPDX-License-Identifier: AGPL-3.0-or-later"""
import json
from pathlib import Path

from synapse.api.errors import Codes, SynapseError
from synapse.module_api import NOT_SPAM


def deny():
    raise SynapseError(403, "The organisation's messaging policy prevents this conversation", Codes.FORBIDDEN)


class Policy:
    def __init__(self, data):
        self.members = data["members"]
        self.orgs = data["organisations"]
        self.hosts = set(data["managed_servers"])
        for user, org in self.members.items():
            if self.server(user) not in self.hosts or org not in self.orgs:
                raise ValueError("Unknown managed user domain or organisation")
        for org in self.orgs.values():
            if org["policy"] not in ("open", "closed", "allowlist"):
                raise ValueError("Unknown policy")
            if not set(org.get("allow", [])) <= self.orgs.keys():
                raise ValueError("Unknown partner organisation")

    @staticmethod
    def server(user):
        return user.partition(":")[2]

    def restricted(self, user):
        org = self.members.get(user)
        return org is not None and self.orgs[org]["policy"] != "open"

    def accepts(self, recipient, sender):
        org = self.members.get(recipient)
        if not self.restricted(recipient):
            return True
        partner = self.members.get(sender)
        return org == partner or (self.orgs[org]["policy"] == "allowlist" and partner in self.orgs[org].get("allow", []))

    def pair(self, a, b):
        return self.accepts(a, b) and self.accepts(b, a)

    def room(self, users, state):
        users = set(users)
        if not any(self.restricted(u) for u in users):
            return True
        create = state.get(("m.room.create", ""))
        if not create or self.server(create.sender) not in self.hosts:
            return False
        rules = state.get(("m.room.join_rules", ""))
        history = state.get(("m.room.history_visibility", ""))
        return bool(rules and rules.content.get("join_rule") == "invite"
                    and history and history.content.get("history_visibility") == "joined"
                    and all(self.server(u) in self.hosts for u in users)
                    and all(self.pair(a, b) for a in users for b in users))


def read_policy(path):
    # Atomic replacement of the JSON file takes effect for the very next operation.
    # Missing or malformed policy stops the operation before delivery.
    return Policy(json.loads(Path(path).read_text()))


def device_allowed(sender, recipients):
    policy = read_policy("/config/policy.json")
    return all(policy.pair(sender, target) for target in recipients)


class RelayPolicy:
    def __init__(self, config, api):
        self.api = api
        api.register_spam_checker_callbacks(user_may_invite=self.invite, user_may_join_room=self.join,
                                            user_may_send_3pid_invite=self.third_party_invite)
        api.register_third_party_rules_callbacks(on_create_room=self.create, check_event_allowed=self.event)

    @staticmethod
    def parse_config(config):
        return config

    @staticmethod
    def membership(state):
        return {key for (kind, key), event in state.items() if kind == "m.room.member"
                and event.content.get("membership") in ("join", "invite")}

    async def create(self, requester, config, is_admin):
        policy = read_policy("/config/policy.json")
        users = {requester.user.to_string(), *config.get("invite", [])}
        if not any(policy.restricted(u) for u in users):
            return
        if config.get("invite_3pid") or not all(policy.pair(a, b) for a in users for b in users):
            deny()
        config["visibility"] = "private"
        config["preset"] = "private_chat"
        kinds = {"m.room.join_rules", "m.room.history_visibility"}
        config["initial_state"] = [e for e in config.get("initial_state", [])
                                   if (e.get("type") not in kinds or e.get("state_key", "") != "")] + [
            {"type": "m.room.join_rules", "state_key": "", "content": {"join_rule": "invite"}},
            {"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}}]

    async def invite(self, inviter, invitee, room_id):
        policy = read_policy("/config/policy.json")
        if not policy.pair(inviter, invitee):
            return Codes.FORBIDDEN
        state = await self.api.get_room_state(room_id)
        if not state:
            # A federated invitation can arrive before this server has room state.
            return Codes.FORBIDDEN if policy.restricted(invitee) else NOT_SPAM
        return NOT_SPAM if policy.room(self.membership(state) | {inviter, invitee}, state) else Codes.FORBIDDEN

    async def join(self, user, room_id, invited):
        state = await self.api.get_room_state(room_id)
        policy = read_policy("/config/policy.json")
        return NOT_SPAM if policy.room(self.membership(state) | {user}, state) else Codes.FORBIDDEN

    async def third_party_invite(self, inviter, medium, address, room_id):
        state = await self.api.get_room_state(room_id)
        policy = read_policy("/config/policy.json")
        return Codes.FORBIDDEN if any(policy.restricted(u) for u in self.membership(state) | {inviter}) else NOT_SPAM

    async def event(self, event, state):
        policy = read_policy("/config/policy.json")
        users = self.membership(state) | {event.sender}
        if event.type == "m.room.member":
            membership = event.content.get("membership")
            if membership in ("leave", "ban"):
                return True, None
            users.add(event.state_key)
        if not any(policy.restricted(u) for u in users):
            return True, None
        if event.type == "m.room.create":
            return policy.server(event.sender) in policy.hosts, None
        create = state.get(("m.room.create", ""))
        # The creator joins before Synapse inserts the preset's initial state.
        if create and users == {create.sender} and policy.server(create.sender) in policy.hosts:
            if event.type in ("m.room.member", "m.room.power_levels", "m.room.guest_access"):
                return True, None
        if event.type in ("m.room.join_rules", "m.room.history_visibility"):
            key, required = ("join_rule", "invite") if event.type == "m.room.join_rules" else ("history_visibility", "joined")
            return event.content.get(key) == required and all(policy.pair(a, b) for a in users for b in users), None
        return policy.room(users, state), None
