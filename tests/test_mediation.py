from oscombo import mediation


class FakeGuest:
    """xdotool over a fake window table: ids -> pid, plus the active window."""

    def __init__(self, windows, active):
        self.windows, self.active = dict(windows), active
        self.titles: dict[str, str] = {}
        self.cmds = []

    def execute(self, argv, timeout=60):
        cmd = argv[-1]
        self.cmds.append(cmd)
        if "getwindowname" in cmd:  # titled(): "<id> <title>" lines
            return {"output": "\n".join(f"{w} {self.titles.get(w, '')}" for w in self.windows)}
        if "search --onlyvisible" in cmd:
            return {"output": "\n".join(self.windows)}
        if "getactivewindow" in cmd:
            return {"output": self.active}
        if "getwindowpid" in cmd:
            return {"output": self.windows.get(cmd.split()[2], "")}
        if "windowactivate" in cmd:
            self.active = cmd.split()[3]
        return {"output": ""}


def test_broker_brings_home_and_refuses_keys_into_foreign_window():
    g = FakeGuest({"10": "1", "20": "2"}, active="20")
    b = mediation.DesktopBroker(g, {"agentA": {"10"}, "agentB": {"20"}}, level=2)
    b.bring_home("agentA")
    assert g.active == "10" and b.stats["focus_restored"] == 1
    g.active = "20"
    assert b.refuses("agentA", "pyautogui.typewrite('x')")
    assert not b.refuses("agentA", "pyautogui.click(1, 1)")
    assert not mediation.DesktopBroker(g, {"agentA": {"10"}}, level=1).refuses("agentA", "pyautogui.press('a')")


def test_broker_adopts_windows_opened_during_own_batch():
    g = FakeGuest({"10": "1"}, active="10")
    b = mediation.DesktopBroker(g, {"agentA": {"10"}, "agentB": set()}, level=2)
    g.windows["30"] = "3"
    g.active = "30"
    b.after_batch("agentB", {"10"})
    assert b.owner["30"] == {"agentB"} and b.home["agentB"] == "30"


def test_selfguard_wraps_actions_and_refocuses():
    g = FakeGuest({"10": "1", "20": "2"}, active="20")
    s = mediation.SelfGuard(g, {"10"})
    s.front()
    assert g.active == "10"
    code = s.wrap("pyautogui.write('abc', interval=0.03)")
    assert "windowactivate', '--sync', '10'" in code and "interval=0)" in code
    g.windows["40"] = "1"  # same process as my window: mine
    assert s.mine("40")


def test_broker_title_fallback_for_unclaimed_windows():
    g = FakeGuest({"10": "1", "20": "2"}, active="20")
    g.titles = {"20": "New Tab - Google Chrome"}
    b = mediation.DesktopBroker(g, {"agentA": set(), "agentB": {"10"}}, level=2, app_titles={"agentA": "Chrome"})
    assert b.owner["20"] == {"agentA"} and b.home["agentA"] == "20"
