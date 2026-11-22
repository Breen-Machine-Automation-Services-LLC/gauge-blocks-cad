"""Privacy scan: no saved drawing may carry the machine login name or a real person's name.

The scan is byte level. A name can be stored as single-byte text (DXF, DWG 2000 summary information) or as UTF-16LE
text (DWG 2007 and later summary information), so both encodings are searched, case-insensitively. DWG 2004 and later
compress some header sections, so this scan has limited power on those sections; programs/CAPABILITIES.md records the
power test that shows which output formats expose an unneutralized name to this scan.
"""
from pathlib import Path
import pwd, os, socket

# Fixed tokens: the login name, the Windows account of the legacy install, and the full name for the login.
from programs.settings import SETTINGS
TOKENS = SETTINGS.get('privacy_tokens', [])


class PrivacyError(RuntimeError):
    pass


def tokens():
    found = list(TOKENS)
    found.append(pwd.getpwuid(os.getuid()).pw_name.lower())
    try:
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(',')[0].strip()
        if gecos and gecos.lower() not in found:
            found.append(gecos.lower())
    except KeyError:
        pass
    host = socket.gethostname().strip().lower()   # BricsCAD's lock file names the host, which here carries a first name
    if host and host not in found:
        found.append(host)
    return found


def scan_bytes(data):
    """Return the list of (token, encoding) hits in a byte string."""
    low = data.lower()
    hits = []
    for t in tokens():
        for enc in ('ascii', 'utf-16-le'):
            needle = t.encode(enc)
            if needle in low:
                hits.append((t, enc))
    return hits


def scan(path):
    return scan_bytes(Path(path).read_bytes())


def assert_clean(path):
    hits = scan(path)
    if hits:
        raise PrivacyError(f'{path}: found {hits}; the writer was not neutralized (see programs/CAPABILITIES.md)')
