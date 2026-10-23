"""Build-time helpers for the F4 (software development) pairs d1-d4: deterministic git repos, fonts, the
dev-server control script and a vendored copy of tomli 2.0.1 (MIT) for Python 3.10 guests."""
import base64
import io
import lzma
import os
import shutil
import subprocess
import tarfile
import tempfile

from PIL import ImageFont

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/lato"]


def font(size, bold=False, mono=False, serif=False, family=None):
    """A TrueType font when the build host has DejaVu/Lato, otherwise PIL's scalable default."""
    if family == "lato":
        names = ["Lato-Bold.ttf" if bold else "Lato-Regular.ttf"]
    elif mono:
        names = ["DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"]
    elif serif:
        names = ["DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"]
    else:
        names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for d in FONT_DIRS:
        for n in names:
            if os.path.exists(os.path.join(d, n)):
                return ImageFont.truetype(os.path.join(d, n), size)
    return ImageFont.load_default(size=size)


def scan_pdf(images, path, resolution=150):
    """Image-only PDF (one page per PIL image), like a scanned printout: no text layer."""
    pages = [im.convert("RGB") for im in images]
    pages[0].save(path, "PDF", resolution=resolution, save_all=True, append_images=pages[1:])


def scanify(im, seed=0):
    """Make a clean rendering look photocopied: slight grey background, tiny rotation, mild noise."""
    import random
    from PIL import Image, ImageFilter
    r = random.Random(seed)
    im = im.convert("L")
    im = im.rotate(r.uniform(-0.6, 0.6), resample=Image.BICUBIC, expand=False, fillcolor=255)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    px = im.load()
    w, h = im.size
    for _ in range(w * h // 400):
        x, y = r.randrange(w), r.randrange(h)
        px[x, y] = max(0, px[x, y] - r.randrange(40, 120))
    return im.point(lambda v: int(v * 0.93 + 8))


ENV = {"GIT_AUTHOR_NAME": "", "GIT_AUTHOR_EMAIL": "", "GIT_COMMITTER_NAME": "", "GIT_COMMITTER_EMAIL": "",
       "GIT_CONFIG_NOSYSTEM": "1", "HOME": "/nonexistent", "TZ": "UTC"}


def make_repo(out_tar, name, history, user, tags=None, gitignore=None, untracked=None):
    """Create a git repo from a scripted history and tar it (arcname = name).

    history: [(iso_date, author (name, email) or None, {path: text|bytes|None(delete)}, message)]
    tags: {tag: (commit_index, annotation message or None)}
    Returns {"base": HEAD hash, "commits": [hashes], "tags": {tag: commit hash}}."""
    tmp = tempfile.mkdtemp()
    repo = os.path.join(tmp, name)
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True, capture_output=True)
    hashes = []
    for when, author, files, msg in history:
        a = author or user
        env = {**os.environ, **ENV, "GIT_AUTHOR_NAME": a[0], "GIT_AUTHOR_EMAIL": a[1], "GIT_COMMITTER_NAME": a[0],
               "GIT_COMMITTER_EMAIL": a[1], "GIT_AUTHOR_DATE": when + " +0200", "GIT_COMMITTER_DATE": when + " +0200"}
        for p, content in files.items():
            fp = os.path.join(repo, p)
            if content is None:
                subprocess.run(["git", "-C", repo, "rm", "-q", p], check=True, env=env, capture_output=True)
                continue
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                f.write(content.encode() if isinstance(content, str) else content)
            if p.endswith(".sh"):
                os.chmod(fp, 0o755)
            subprocess.run(["git", "-C", repo, "add", p], check=True, env=env, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", msg], check=True, env=env, capture_output=True)
        hashes.append(subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True,
                                     check=True).stdout.strip())
    out_tags = {}
    for tag, (idx, ann) in (tags or {}).items():
        when = history[idx][0]
        env = {**os.environ, **ENV, "GIT_COMMITTER_NAME": user[0], "GIT_COMMITTER_EMAIL": user[1],
               "GIT_COMMITTER_DATE": when + " +0200"}
        args = ["git", "-C", repo, "tag"] + (["-a", "-m", ann] if ann else []) + [tag, hashes[idx]]
        subprocess.run(args, check=True, env=env, capture_output=True)
        out_tags[tag] = hashes[idx]
    with open(os.path.join(repo, ".git", "config"), "a") as f:
        f.write(f"[user]\n\tname = {user[0]}\n\temail = {user[1]}\n")
    for p, content in (untracked or {}).items():
        fp = os.path.join(repo, p)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w") as f:
            f.write(content)
    for d, _, fs in os.walk(repo):  # stable archive: fixed mtimes
        for x in fs + [d]:
            os.utime(os.path.join(d, x) if x != d else d, (1792000000, 1792000000))

    def norm(ti):
        ti.uid = ti.gid = 1000
        ti.uname = ti.gname = "user"
        ti.mtime = 1792000000
        return ti
    with tarfile.open(out_tar, "w:gz") as t:
        t.add(repo, arcname=name, filter=norm)
    shutil.rmtree(tmp)
    return {"base": hashes[-1], "commits": hashes, "tags": out_tags}


def dev_sh(module, port, label):
    """./dev.sh {start|stop|restart|status|log}: the repo's own dev-server control script (pidfile based)."""
    return f"""#!/usr/bin/env bash
# Control the local {label} dev server (http://127.0.0.1:{port}/).
# The server does NOT reload code: run ./dev.sh restart after changing Python files.
set -u
cd "$(dirname "$0")"
PIDFILE=.devserver.pid
LOG=logs/dev-server.log
PORT=${{PORT:-{port}}}
up() {{ curl -s -o /dev/null -m 2 "http://127.0.0.1:$PORT/"; }}
start() {{
  if up; then echo "already running on port $PORT"; return 0; fi
  mkdir -p logs
  setsid python3 -m {module} --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDFILE"
  for i in $(seq 40); do up && {{ echo "started (pid $(cat $PIDFILE)) on http://127.0.0.1:$PORT/"; return 0; }}; sleep 0.5; done
  echo "server did not come up, last log lines:"; tail -n 20 "$LOG"; return 1
}}
stop() {{
  if [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null; then
    for i in $(seq 20); do up || break; sleep 0.5; done
  fi
  rm -f "$PIDFILE"
  if up; then echo "something else is still listening on port $PORT (started by hand?)"; return 1; fi
  echo stopped
}}
case "${{1:-status}}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) if up; then echo "running on http://127.0.0.1:$PORT/"; else echo "not running"; fi ;;
  log) tail -n 50 "$LOG" ;;
  *) echo "usage: ./dev.sh start|stop|restart|status|log"; exit 2 ;;
esac
"""


TOMLI_BLOB = """
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
"""


def tomli_files(prefix):
    """{prefix + relative path: text} for the vendored tomli 2.0.1 (with its MIT licence)."""
    raw = lzma.decompress(base64.b64decode("".join(TOMLI_BLOB.split())))
    out = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        for m in t.getmembers():
            if m.isfile():
                rel = m.name.replace("tomli-2.0.1.dist-info/", "tomli/")
                out[prefix + rel] = t.extractfile(m).read().decode()
    return out
