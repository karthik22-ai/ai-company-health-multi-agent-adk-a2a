"""The company roster: an Australian private health insurer that also runs health services.

Agent ids, department ids and room ids MUST match the 3D UI (finance-hq-agents.html).
A test (tests/test_roster.py) parses the HTML and fails if the two drift apart.

The 3D UI shows five or fewer AI agents per department: they are the department's leaders/analysts. The *simulated* workforce
behind each department is much larger (see biz/catalog.py: DEPT_HEADCOUNT); the agents make decisions about it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    id: str            # e.g. "claims.helen" – <dept>.<firstname>
    name: str
    role: str
    dept: str
    lead: bool = False


@dataclass(frozen=True)
class Department:
    id: str
    name: str
    floor: int         # 1-3, as in the UI
    lead_name: str
    mission: str
    responsibilities: list[str] = field(default_factory=list)
    agents: list[AgentSpec] = field(default_factory=list)


def _agents(dept: str, people: list[tuple[str, str]], lead_name: str) -> list[AgentSpec]:
    return [AgentSpec(f"{dept}.{n.split()[0].lower()}", n, r, dept, lead=n == lead_name) for n, r in people]


_D = [
    ("exec", "Executive Office", 3, "Priya Raman",
     "Sets strategy for the group, owns the budget and the board relationship, and makes the final call on initiatives.",
     ["decide on proposed initiatives within the strategy budget", "set targets and priorities", "report to the board and APRA-facing executives"],
     [("Priya Raman", "Chief Executive Officer"), ("Daniel Okafor", "Chief Financial Officer"), ("Mei Tanaka", "Chief of Staff & Strategy")]),
    ("sales", "Sales & Distribution", 2, "Leo Martins",
     "Grows the member base across online, phone, comparison sites, brokers, corporate and retail partners.",
     ["new policy sales and conversion", "channel performance", "broker and corporate partnerships", "sales capacity"],
     [("Leo Martins", "Head of Sales & Distribution"), ("Sara Haddad", "Online & Partnerships Manager"), ("Tom Becker", "Broker & Corporate Manager"),
      ("Ana Duarte", "Phone Sales Team Lead"), ("Wei Chen", "Sales Performance Analyst")]),
    ("mkt", "Marketing & Growth", 2, "Grace Liu",
     "Builds brand awareness and demand, runs campaigns and manages retention marketing.",
     ["campaigns and media spend", "brand and content", "retention marketing", "comparison-site presence"],
     [("Grace Liu", "Head of Marketing & Growth"), ("Omar Siddiqui", "Performance Marketing Manager"), ("Julia Novak", "Brand & Content Lead"),
      ("Ben Carter", "CRM & Retention Marketing Manager"), ("Ines Costa", "Digital Partnerships Lead")]),
    ("data", "Data & Actuarial", 2, "Arjun Nair",
     "Owns the data platform, pricing and claims models, forecasting and the daily trading numbers.",
     ["daily KPI reporting", "forecasting", "actuarial pricing and reserving", "data quality"],
     [("Arjun Nair", "Chief Data & Actuarial Officer"), ("Chloe Dubois", "Data Engineer"), ("Marco Rossi", "BI Developer"),
      ("Yuki Sato", "Actuary (Pricing & Reserving)"), ("Nora Berg", "Data Scientist")]),
    ("claims", "Claims", 1, "Helen Park",
     "Assesses and pays hospital, extras and ambulance claims accurately and quickly, and protects the fund from fraud.",
     ["claims turnaround and backlog", "claims accuracy", "fraud and integrity", "claims automation"],
     [("Helen Park", "Head of Claims"), ("Victor Alves", "Hospital Claims Manager"), ("Tara Singh", "Extras Claims Team Lead"),
      ("Kofi Mensah", "Fraud & Integrity Lead"), ("Lena Fischer", "Claims Operations Analyst")]),
    ("care", "Member Care", 1, "Rafael Gomez",
     "Looks after members by phone, chat and digital self-service, and keeps them with us.",
     ["call-centre service levels", "member satisfaction (CSAT/NPS)", "digital self-service", "retention conversations"],
     [("Rafael Gomez", "Head of Member Care"), ("Amira Khan", "Contact Centre Manager"), ("Jonas Weber", "Quality & Training Lead"),
      ("Sofia Lund", "Digital Self-Service Lead")]),
    ("health", "Health Services", 1, "Marcus Bell",
     "Runs our clinics, provider network and preventive-health programs so members get better care at lower cost.",
     ["provider network and agreements", "dental, optical and physio clinics", "preventive health and telehealth", "clinical governance"],
     [("Marcus Bell", "Chief Medical Officer"), ("Nia Okonkwo", "Provider Network & Partnerships Manager"), ("Piotr Zielinski", "Clinic Operations Manager"),
      ("Ayla Demir", "Preventive Health & Telehealth Lead")]),
    ("people", "People & Culture", 1, "Camille Roy",
     "Keeps the team healthy, skilled and the right size: hiring, training, engagement and wellbeing.",
     ["workforce planning and hiring", "engagement and attrition", "training and capability", "wellbeing programs"],
     [("Camille Roy", "Chief People Officer"), ("Ethan Wright", "Talent Acquisition Partner"), ("Zara Malik", "Learning & Engagement Lead"),
      ("Hugo Lemoine", "Workforce Planning Analyst")]),
    ("prod", "Product & Pricing", 3, "Elena Petrova",
     "Designs the hospital, extras and combined plans we offer and sets prices within the Private Health Insurance rules.",
     ["plan design and tiers", "annual premium round (1 April)", "promotions", "product performance"],
     [("Elena Petrova", "Head of Product & Pricing"), ("Samir Patel", "Product Manager (Hospital)"), ("Clara Jensen", "Product Manager (Extras & Ancillary)")]),
    ("risk", "Risk & Compliance", 3, "Isabel Moreno",
     "Keeps us inside the rules (APRA, ASIC, the Private Health Insurance Act, the Ombudsman, privacy law) and challenges risky ideas.",
     ["review initiatives for compliance", "community rating and fair-treatment rules", "privacy and data security", "regulatory reporting"],
     [("Isabel Moreno", "Chief Risk & Compliance Officer"), ("Kwame Boateng", "Regulatory Compliance Manager"),
      ("Hana Yamada", "Information Security Analyst"), ("Lucas Meyer", "Privacy Officer")]),
    ("bi", "Reporting & Insights", 2, "Olivia Grant",
     "Turns the company's data into dashboards, reports and board packs that every team and the executives use to run the business.",
     ["build and maintain dashboards", "weekly and monthly performance reports", "board and executive packs", "self-service reporting"],
     [("Olivia Grant", "Head of Reporting & Insights"), ("Ravi Kumar", "Dashboard Developer"), ("Emma Wilson", "Reporting Analyst"),
      ("Diego Ramirez", "Data Visualisation Designer")]),
    ("it", "IT & Apps", 3, "Kenji Watanabe",
     "Builds and runs the internal apps and platforms: reporting apps, team tools and the systems the business relies on.",
     ["internal apps for reporting and operations", "platform reliability", "access and identity", "automation tooling"],
     [("Kenji Watanabe", "Head of IT & Apps"), ("Fatima Hassan", "Full-stack App Developer"), ("Liam Murphy", "Platform & Cloud Engineer"),
      ("Aisha Bello", "Internal Tools Developer")]),
]

DEPARTMENTS: dict[str, Department] = {}
AGENTS: dict[str, AgentSpec] = {}
for did, dname, floor, lead, mission, resp, people in _D:
    ags = _agents(did, people, lead)
    DEPARTMENTS[did] = Department(did, dname, floor, lead, mission, resp, ags)
    for a in ags:
        AGENTS[a.id] = a

SHARED_ROOMS = {"lob": "Reception & Café", "mr1": "Meeting Room 1", "mr2": "Meeting Room 2", "mr3": "Meeting Room 3",
                "brd": "Boardroom"}
MEETING_ROOMS = ["mr1", "mr2", "mr3", "brd"]
MAX_PER_DEPT = 8          # desks per department room in the 3D office
ROOM_IDS = set(SHARED_ROOMS) | set(DEPARTMENTS)

# core IT systems the agents can check (ids must match the UI's system list)
SYSTEMS = {"policy": "Policy Admin", "claims": "Claims Platform", "crm": "Contact Centre & CRM", "dw": "Data Warehouse",
           "web": "Web & Quote Engine", "pay": "Payments & Billing"}


def colleagues_text(exclude: str | None = None) -> str:
    lines = []
    for d in DEPARTMENTS.values():
        lines.append(f"- {d.name} ({d.id}): " + "; ".join(f"{a.id} = {a.name}, {a.role}" for a in d.agents if a.id != exclude))
    return "\n".join(lines)


def agent_name(agent_id: str) -> str:
    return AGENTS[agent_id].name


def dept_lead(dept: str) -> AgentSpec:
    return next(a for a in DEPARTMENTS[dept].agents if a.lead)


def add_agent(name: str, role: str, dept: str, aid: str | None = None) -> AgentSpec:
    """Hire a new AI agent into a department at runtime (People & Culture's hire_agent tool). Ids stay <dept>.<firstname>."""
    if dept not in DEPARTMENTS:
        raise ValueError(f"unknown department '{dept}'")
    if len(DEPARTMENTS[dept].agents) >= MAX_PER_DEPT:
        raise ValueError(f"{DEPARTMENTS[dept].name} is full ({MAX_PER_DEPT} desks)")
    if aid is None:
        base = "".join(ch for ch in name.split()[0].lower() if ch.isalnum()) or "agent"
        aid, n = f"{dept}.{base}", 2
        while aid in AGENTS:
            aid, n = f"{dept}.{base}{n}", n + 1
    elif aid in AGENTS:
        return AGENTS[aid]
    spec = AgentSpec(aid, name.strip()[:40], role.strip()[:60], dept)
    DEPARTMENTS[dept].agents.append(spec)
    AGENTS[aid] = spec
    return spec


def adk_name(agent_id: str) -> str:
    """ADK agent names must be Python identifiers."""
    return agent_id.replace(".", "_")
