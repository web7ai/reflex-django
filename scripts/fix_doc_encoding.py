from pathlib import Path
import sys

def normalize(text):
    return text.replace("\u2014", "-").replace("\u2013", "-")

def to_utf8(path):
    raw = Path(path).read_bytes()
    nulls = sum(1 for b in raw if b == 0)
    text = raw.decode("utf-16-le") if nulls > len(raw) // 4 else raw.decode("utf-8", errors="replace")
    Path(path).write_text(normalize(text), encoding="utf-8", newline="\n")
    print("fixed", path)

for arg in sys.argv[1:]:
    to_utf8(arg)