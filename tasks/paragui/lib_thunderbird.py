"""Offline Thunderbird 115 profile for paraGUI mail tasks (same recipe as C4 in build_assets.py, made reusable).

    from lib_thunderbird import make_profile, mbox_entry
    make_profile(out_tar, me=("Jordan Lee", "jordan.lee@northwindlabs.com"),
                 folders={"Inbox": [EmailMessage, ...], "Archives/2025": [...]},
                 unread=lambda msg: True)

The profile has one POP3 account (never contacts a server) plus Local Folders; mail lives in mbox files under
Mail/<host>/, index files are dropped so Thunderbird rebuilds them on first start. Software rendering is forced:
under QEMU without KVM the GL compositor leaves the main window and the message pane unpainted.
Guest path after `tar xzf <tar> -C ~`: ~/.thunderbird/t5q2a5hp.default-release
Calendar: Thunderbird 115 keeps the local "Home" calendar in calendar-data/local.sqlite (table cal_events, cal_properties).
Address book: abook.sqlite (table properties: card, name, value).
"""
from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile

TB_BASE = os.environ.get("PARAGUI_TB_BASE", os.path.expanduser("~/.cache/oscombo/paragui/base/thunderbird-profile.tar.gz"))
PROFILE = "t5q2a5hp.default-release"


def mbox_entry(msg, when, unread: bool = True) -> bytes:
    """One mbox record with the X-Mozilla headers Thunderbird expects (status 0x0001 = read)."""
    raw = msg.as_bytes(policy=msg.policy.clone(linesep="\n")).replace(b"\nFrom ", b"\n>From ")
    return (b"From - " + when.strftime("%a %b %d %H:%M:%S %Y").encode() + b"\n"
            + b"X-Mozilla-Status: " + (b"0000" if unread else b"0001") + b"\n"
            + b"X-Mozilla-Status2: 00000000\nX-Mozilla-Keys: " + b" " * 80 + b"\n" + raw.rstrip(b"\n") + b"\n\n")


def make_profile(out_tar: str, me: tuple[str, str], folders: dict[str, list[tuple]], host: str | None = None,
                 extra_prefs: dict | None = None, extra_files: dict[str, bytes] | None = None) -> str:
    """Write a .tar.gz containing .thunderbird/ and return the account's mailbox:// URI prefix.

    folders: {"Inbox": [(EmailMessage, datetime, unread_bool), ...], "Projects/Apollo": [...]} -- nested folders use
    "/" and become Projects.sbd/Apollo. Drafts, Sent, Trash, Templates, Archives always exist.
    extra_files: {profile-relative path: bytes}, e.g. a prepared calendar-data/local.sqlite or abook.sqlite.
    """
    name, addr = me
    user = addr.split("@")[0]
    host = host or "pop." + addr.split("@")[1]
    tmp = tempfile.mkdtemp()
    with tarfile.open(TB_BASE) as t:
        t.extractall(tmp)
    prof = f"{tmp}/.thunderbird/{PROFILE}"
    shutil.rmtree(f"{prof}/ImapMail")
    for root, _, files in os.walk(prof):
        for f in files:
            if f.endswith(".msf") or f in ("folderCache.json", "folderTree.json", "session.json", "session.json.backup",
                                          "global-messages-db.sqlite"):
                os.remove(os.path.join(root, f))
    if os.path.lexists(f"{prof}/lock"):
        os.remove(f"{prof}/lock")
    os.remove(f"{prof}/Mail/Local Folders/Bills")
    shutil.rmtree(f"{prof}/Mail/Local Folders/Trash.sbd", ignore_errors=True)
    box = f"mailbox://{user}@{host}"
    keep = [ln for ln in open(f"{prof}/prefs.js") if not any(
        k in ln for k in ("mail.server.server1.", "mail.identity.id1.", "mail.smtpserver.smtp1.", "mail.root.",
                          "mail.last_msg_movecopy_target_uri", "mail.imap.", "server2.directory\""))]
    prefs = {
        "mail.server.server1.type": "pop3", "mail.server.server1.hostname": host,
        "mail.server.server1.userName": user, "mail.server.server1.name": addr,
        "mail.server.server1.directory-rel": f"[ProfD]Mail/{host}", "mail.server.server1.check_new_mail": False,
        "mail.server.server1.login_at_startup": False, "mail.server.server1.download_on_biff": False,
        "mail.server.server1.storeContractID": "@mozilla.org/msgstore/berkeleystore;1",
        "mail.server.server1.port": 995, "mail.server.server1.socketType": 3,
        "mail.identity.id1.fullName": name, "mail.identity.id1.useremail": addr, "mail.identity.id1.valid": True,
        "mail.identity.id1.smtpServer": "smtp1", "mail.identity.id1.reply_on_top": 1,
        "mail.identity.id1.draft_folder": f"{box}/Drafts", "mail.identity.id1.drafts_folder_picker_mode": "0",
        "mail.identity.id1.fcc_folder": f"{box}/Sent", "mail.identity.id1.fcc_folder_picker_mode": "0",
        "mail.identity.id1.archive_folder": f"{box}/Archives", "mail.identity.id1.stationery_folder": f"{box}/Templates",
        "mail.identity.id1.tmpl_folder_picker_mode": "0",
        "mail.smtpserver.smtp1.hostname": "smtp." + addr.split("@")[1], "mail.smtpserver.smtp1.port": 587,
        "mail.smtpserver.smtp1.username": user, "mail.smtpserver.smtp1.try_ssl": 2,
        "mail.smtpserver.smtp1.authMethod": 3, "mail.smtpserver.smtp1.description": "Work",
        "mail.root.none-rel": "[ProfD]Mail", "mail.root.pop3-rel": "[ProfD]Mail",
        "mail.shell.checkDefaultClient": False, "mail.spam.manualMark": False,
        "datareporting.policy.dataSubmissionPolicyBypassNotification": True, "mailnews.start_page.enabled": False,
        "gfx.webrender.software": True, "layers.acceleration.disabled": True,
        **(extra_prefs or {}),
    }
    with open(f"{prof}/prefs.js", "w") as f:
        f.writelines(keep)
        for k, v in prefs.items():
            f.write(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n")
    acct = f"{prof}/Mail/{host}"
    os.makedirs(acct)
    open(f"{acct}/msgFilterRules.dat", "w").write('version="9"\nlogging="no"\n')
    for special in ("Drafts", "Sent", "Trash", "Templates", "Archives"):
        open(f"{acct}/{special}", "w").close()
    for folder, msgs in folders.items():
        parts = folder.split("/")
        path = os.path.join(acct, *[p + ".sbd" for p in parts[:-1]], parts[-1])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            for msg, when, unread in msgs:
                f.write(mbox_entry(msg, when, unread))
    for rel, data in (extra_files or {}).items():
        os.makedirs(os.path.dirname(f"{prof}/{rel}"), exist_ok=True)
        open(f"{prof}/{rel}", "wb").write(data)
    with tarfile.open(out_tar, "w:gz") as t:
        t.add(f"{tmp}/.thunderbird", arcname=".thunderbird")
    shutil.rmtree(tmp)
    return box
