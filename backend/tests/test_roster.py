"""The backend roster must match the 3D UI: same departments, agent ids, names and roles."""
import re

from hq.agents.roster import AGENTS, DEPARTMENTS, ROOM_IDS
from hq.core.config import PROJECT_DIR


def ui_text():
    """The whole frontend (index.html + every JS module) as one text."""
    fe = PROJECT_DIR / "frontend"
    return "\n".join(p.read_text(encoding="utf-8") for p in [fe / "index.html", *sorted((fe / "js").glob("*.js"))])


def test_departments_agents_and_roles_match_the_ui():
    html = ui_text()
    t_block = html[html.index("const T={"): html.index("const COL=")]
    seen = {}
    for m in re.finditer(r"\n (\w+):\{name:'([^']+)'.*?people:\[(.*?)\]\}", t_block, re.S):
        dept, name, people = m.group(1), m.group(2), m.group(3)
        seen[dept] = (name, re.findall(r"\['([^']+)','([^']+)'\]", people))
    assert set(seen) == set(DEPARTMENTS)
    for dept, (name, people) in seen.items():
        assert DEPARTMENTS[dept].name == name
        assert [(a.name, a.role) for a in DEPARTMENTS[dept].agents] == people
        assert [a.id for a in DEPARTMENTS[dept].agents] == [f"{dept}.{n.split()[0].lower()}" for n, _ in people]


def test_room_ids_match_the_ui():
    html = ui_text()
    block = html[html.index("const RD=["): html.index("const ROOMS=[]")]
    ui_rooms = set(re.findall(r"\['(\w+)',[012],", block))
    assert ui_rooms == ROOM_IDS


def test_agent_count():
    assert len(AGENTS) == 50


def test_vertex_settings_select_real_llm_and_clear_api_key(monkeypatch):
    import os

    from hq.core.config import Settings, get_settings
    s = Settings(use_vertex=True, gcp_project="my-proj", gcp_location="us-central1", google_api_key="should-be-dropped")
    assert not s.use_mock and "Vertex AI" in s.llm_label and "my-proj" in s.llm_label
    monkeypatch.setenv("HQ_USE_VERTEX", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-proj")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    get_settings.cache_clear()
    try:
        get_settings()
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"
        assert os.environ["GOOGLE_CLOUD_PROJECT"] == "my-proj" and "GOOGLE_API_KEY" not in os.environ
    finally:
        get_settings.cache_clear()
