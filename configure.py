"""Create private local configuration for the Compose deployment."""
import argparse
import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument("server_name")
args = parser.parse_args()
server = args.server_name
if not re.fullmatch(r"[a-z0-9.-]+", server) or urlsplit("https://" + server).hostname != server:
    parser.error("Use a lowercase DNS hostname")
path = Path("config")
path.mkdir(mode=0o700, exist_ok=False)
password = secrets.token_urlsafe(40)
def save(name, value):
    file = path / name
    file.write_text(value)
    file.chmod(0o600)
save("postgres.env", f"POSTGRES_USER=synapse\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=synapse\nPOSTGRES_INITDB_ARGS=--encoding=UTF8 --locale=C\n")
save("homeserver.yaml", json.dumps({
    "server_name": server, "public_baseurl": f"https://{server}/", "report_stats": False,
    "listeners": [{"port": 8008, "type": "http", "tls": False, "bind_addresses":["0.0.0.0"], "x_forwarded":False,
                   "resources":[{"names":["client","federation"]}]}],
    "enable_registration": False, "macaroon_secret_key": secrets.token_urlsafe(48),
    "registration_shared_secret":secrets.token_urlsafe(48), "signing_key_path": "/data/server.signing.key",
    "media_store_path":"/data/media_store",
    "database":{"name":"psycopg2","args":{"user":"synapse","password":password,"database":"synapse","host":"postgres"}},
    "modules":[{"module":"relay_policy.RelayPolicy","config":{}}],
},indent=2)+"\n")
save("policy.json", json.dumps({"managed_servers":[server],"members":{},"organisations":{}},indent=2)+"\n")
