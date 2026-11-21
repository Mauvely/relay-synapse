"""Run in the pinned Synapse image with this repository mounted at /test."""
import json
import unittest
from pathlib import Path

from relay_policy import Policy


class AdmissionTests(unittest.TestCase):
    def test_policy_cases(self):
        fixture = json.loads(Path(__file__).with_name("policy-cases.json").read_text())
        for example in fixture["cases"]:
            with self.subTest(name=example["name"]):
                rules = dict(fixture["organisations"], **example.get("override", {}))
                policy = Policy(dict(fixture, organisations=rules))
                self.assertEqual(policy.pair(example["sender"], example["recipient"]), example["allow"])

    def test_missing_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            Policy({"managed_servers":["a.example"],"members":{"@alex:a.example":"unavailable"},"organisations":{}})


if __name__ == "__main__":
    unittest.main()
