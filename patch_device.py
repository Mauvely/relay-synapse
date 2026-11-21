"""Wire two device delivery paths unavailable through Synapse's public module API."""
from pathlib import Path
import synapse.handlers.devicemessage as handler

path = Path(handler.__file__)
text = path.read_text()
for anchor, check in [
    ('        message_type = content["type"]', '''        from relay_policy import device_allowed
        if not device_allowed(sender_user_id, content["messages"]):
            return
'''),
    ('        set_tag(SynapseTags.TO_DEVICE_TYPE, message_type)', '''        from relay_policy import device_allowed, deny
        if not device_allowed(sender_user_id, messages):
            deny()
''')
]:
    if text.count(anchor) != 1:
        raise RuntimeError("Synapse device-message hook changed")
    text = text.replace(anchor, check + anchor)
path.write_text(text)
