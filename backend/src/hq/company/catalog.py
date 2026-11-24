"""Static facts about the (fictional) company and the Australian private-health market it operates in.

Everything here is SYNTHETIC. Figures are shaped to look like an Australian mid-size health insurer (~4% market share):
hospital tiers Gold/Silver/Bronze/Basic (the 2019 product-tier reforms), extras cover, ambulance, overseas visitor/student
cover, a loss ratio in the mid-80s, and the regulatory calendar (premium round on 1 April, end of financial year on 30 June).
It is not real data and not financial or insurance advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ----------------------------------------------------------------------------- geography / channels / people
STATES = {"NSW": 0.320, "VIC": 0.260, "QLD": 0.210, "WA": 0.110, "SA": 0.070, "TAS": 0.022, "ACT": 0.017, "NT": 0.010}
AGE_BANDS = ["18-29", "30-44", "45-59", "60-74", "75+"]


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    base_leads: float       # leads per day before seasonality
    cpl: float              # marketing cost per lead (AUD) used for campaign effects
    conv: float             # lead -> policy conversion at the market price
    phone: bool = False     # handled by the sales team (capacity limited)


CHANNELS: dict[str, Channel] = {c.id: c for c in [
    Channel("online_direct", "Online (direct)", 900, 11.0, 0.105),
    Channel("phone_direct", "Phone (direct)", 300, 30.0, 0.200, phone=True),
    Channel("comparison_site", "Comparison sites", 750, 18.0, 0.085),
    Channel("broker", "Brokers", 120, 45.0, 0.240, phone=True),
    Channel("corporate", "Corporate schemes", 40, 35.0, 0.380, phone=True),
    Channel("retail_partner", "Retail partners", 100, 22.0, 0.120),
]}


# ----------------------------------------------------------------------------- products
@dataclass
class Product:
    id: str
    name: str
    category: str            # hospital | extras | combined | ambulance | ovhc | oshc
    tier: str | None         # gold | silver | bronze | basic (hospital tiers) – None for non-hospital
    price: float             # monthly premium for a single, before the government rebate, AUD
    claims_ratio: float      # expected benefits paid / premium
    avg_claim: float         # average benefit per claim, AUD
    sales_share: float       # share of new policies
    start_share: float       # share of the opening book
    age_mix: list[float]     # buyer age distribution over AGE_BANDS
    target: str = ""
    description: str = ""
    active: bool = True
    launched: str = "2019-04-01"
    waiting: str = "2 months general · 12 months pre-existing · 12 months pregnancy"
    inclusions: list[str] = field(default_factory=list)
    lapse: float = 0.15      # annual cancellation rate (lapses + switching), set below


def _p(*a, **k) -> Product:
    return Product(*a, **k)


PRODUCTS: list[Product] = [
    _p("hosp_gold", "Gold Hospital", "hospital", "gold", 285, 0.88, 4200, 0.043, 0.06, [.10, .22, .30, .28, .10],
       "Complete hospital cover", "Covers all clinical categories including pregnancy, joint replacements and cardiac.",
       inclusions=["All 38 clinical categories", "Pregnancy & birth", "Joint replacements", "Cardiac & vascular", "Choice of doctor"]),
    _p("hosp_silver", "Silver Hospital", "hospital", "silver", 196, 0.87, 3900, 0.145, 0.17, [.14, .30, .30, .20, .06],
       "Broad hospital cover with some exclusions", "Most clinical categories; excludes pregnancy and some high-cost categories.",
       inclusions=["Most clinical categories", "Cataracts & hernia", "Heart-related (limited)", "Choice of doctor"]),
    _p("hosp_bronze", "Bronze Hospital", "hospital", "bronze", 146, 0.85, 3500, 0.124, 0.12, [.28, .34, .22, .12, .04],
       "Essential hospital cover", "Covers the essentials: appendix, bone fractures, hernia, brain & nervous system.",
       inclusions=["Essential categories", "Bone, joint & muscle (injury)", "Brain & nervous system", "Surgical & medical services"]),
    _p("hosp_basic", "Basic Hospital", "hospital", "basic", 98, 0.82, 3100, 0.058, 0.05, [.35, .30, .18, .12, .05],
       "Entry-level hospital cover", "Basic protection and a way to avoid the Lifetime Health Cover loading.",
       inclusions=["Minimum clinical categories", "Accident cover", "Avoids LHC loading"]),
    _p("ext_essential", "Extras Essential", "extras", None, 38, 0.78, 140, 0.054, 0.04, [.30, .35, .20, .11, .04],
       "Everyday extras", "General dental check-ups, optical, physio with annual limits.",
       inclusions=["General dental", "Optical", "Physiotherapy", "Annual limits $600"]),
    _p("ext_plus", "Extras Plus", "extras", None, 69, 0.80, 160, 0.036, 0.03, [.22, .35, .25, .14, .04],
       "More extras", "Higher limits plus major dental, remedial massage and psychology.",
       inclusions=["General & major dental", "Optical", "Physio & remedial massage", "Psychology", "Annual limits $1,400"]),
    _p("ext_premium", "Extras Premium", "extras", None, 108, 0.82, 190, 0.019, 0.02, [.12, .30, .30, .22, .06],
       "Top extras", "Highest limits including orthodontics, hearing aids and travel vaccinations.",
       inclusions=["Major dental & orthodontics", "Optical", "Physio", "Hearing aids", "Annual limits $2,800"]),
    _p("combo_young", "Young Adult Combined", "combined", "bronze", 155, 0.85, 420, 0.075, 0.07, [.78, .22, 0, 0, 0],
       "Under 30s, hospital + extras", "Bronze hospital plus extras at up to 10% under 30 discount.",
       inclusions=["Bronze hospital", "General dental", "Optical", "Physio", "Under-30 discount"]),
    _p("combo_family", "Family Silver Combined", "combined", "silver", 428, 0.86, 460, 0.113, 0.14, [.02, .55, .38, .05, 0],
       "Families", "Silver hospital with extras for the whole family, kids covered to 31.",
       inclusions=["Silver hospital", "Extras for all", "Pregnancy upgrade option", "Dependants to 31"]),
    _p("combo_gold", "Gold Complete Combined", "combined", "gold", 362, 0.87, 700, 0.057, 0.08, [.06, .24, .32, .28, .10],
       "Maximum cover", "Gold hospital plus Extras Premium.",
       inclusions=["Gold hospital", "Extras Premium", "Priority claims", "Overseas emergency cover"]),
    _p("combo_senior", "Seniors Silver Plus", "combined", "silver", 301, 0.89, 520, 0.075, 0.12, [0, 0, .10, .65, .25],
       "Over 60s", "Silver hospital plus extras with joint replacement and cataract cover.",
       inclusions=["Silver Plus hospital", "Joint replacement", "Cataracts", "Podiatry & optical"]),
    _p("ambulance", "Ambulance Cover", "ambulance", None, 14, 0.70, 480, 0.035, 0.03, [.20, .30, .25, .18, .07],
       "Ambulance only", "Emergency ambulance transport (not needed in QLD/TAS where government covers it).",
       inclusions=["Emergency ambulance", "Interstate transport"], waiting="None for accidents · 2 months otherwise"),
    _p("ovhc", "Overseas Visitors (OVHC)", "ovhc", None, 92, 0.82, 2200, 0.114, 0.05, [.45, .38, .12, .05, 0],
       "Temporary visa holders", "Hospital and medical cover for visitors on temporary working visas.",
       inclusions=["Hospital cover", "Medical services", "Repatriation"], waiting="2 months"),
    _p("oshc", "Overseas Students (OSHC)", "oshc", None, 58, 0.84, 900, 0.05, 0.02, [.95, .05, 0, 0, 0],
       "International students", "Overseas Student Health Cover required for student visas.",
       inclusions=["Hospital & medical", "Pharmacy", "Mental health"], waiting="Per visa rules"),
]
LAPSE = {"hosp_gold": 0.1, "hosp_silver": 0.13, "hosp_bronze": 0.17, "hosp_basic": 0.2, "ext_essential": 0.22, "ext_plus": 0.19, "ext_premium": 0.15, "combo_young": 0.18, "combo_family": 0.12, "combo_gold": 0.1, "combo_senior": 0.08, "ambulance": 0.2, "ovhc": 0.45, "oshc": 0.5}
for _pr in PRODUCTS:
    _pr.lapse = LAPSE[_pr.id]
PRODUCT_BY_ID = {p.id: p for p in PRODUCTS}

OPENING_POLICIES = 410_000
LIVES_PER_POLICY = 1.9
CALLS_PER_POLICY_DAY = 0.0115
INVESTMENT_YIELD = 0.012          # investment income as a share of premium revenue
VARIABLE_EXPENSE = 0.025          # commissions, payment fees, etc. (share of premium)

# ----------------------------------------------------------------------------- departments (simulated workforce)
@dataclass(frozen=True)
class DeptCosts:
    headcount: int
    salary: float            # average fully-loaded cost per FTE per year, AUD
    productivity: float      # units of work per FTE per working day (claims, calls, phone leads) – 0 where not modelled
    unit: str = ""


DEPT_COSTS: dict[str, DeptCosts] = {
    "exec": DeptCosts(12, 360_000, 0),
    "sales": DeptCosts(75, 118_000, 38, "phone leads"),
    "mkt": DeptCosts(36, 135_000, 0),
    "data": DeptCosts(22, 160_000, 0),
    "bi": DeptCosts(8, 140_000, 0),
    "it": DeptCosts(20, 145_000, 0),
    "claims": DeptCosts(130, 96_000, 71, "claims"),
    "care": DeptCosts(100, 88_000, 55, "calls"),
    "health": DeptCosts(48, 142_000, 0),
    "people": DeptCosts(14, 125_000, 0),
    "prod": DeptCosts(16, 150_000, 0),
    "risk": DeptCosts(22, 152_000, 0),
}

FIXED_OPEX_DAILY = 52_000        # property, technology licences, APRA levies, etc. (IT staff are now in DEPT_COSTS['it'])
BASE_MARKETING_DAILY = 75_000    # always-on media (baseline already included in lead volumes)
ANNUAL_STRATEGY_BUDGET = 24_000_000   # what the executive team can commit to initiatives per financial year
BASE_ANNUAL_ATTRITION = 0.14

TARGETS = {
    "loss_ratio": 0.87,        # benefits / premium – at or below
    "claims_sla_pct": 92.0,    # claims assessed within 5 business days – at or above
    "avg_wait_s": 150.0,       # contact centre wait – at or below
    "nps": 28.0,
    "net_adds": 120.0,         # net new policies per day – at or above
    "margin": 0.04,            # operating margin – at or above
    "engagement": 70.0,        # staff engagement index – at or above
}

# ----------------------------------------------------------------------------- seasonality
DOW_SALES = [1.18, 1.10, 1.05, 1.02, 0.95, 0.62, 0.55]          # Mon..Sun
MONTH_SALES = [1.12, 0.98, 1.15, 0.92, 0.90, 1.30, 1.20, 0.95, 0.90, 0.95, 1.00, 0.82]   # Jan..Dec (Mar: ahead of 1 April rise, Jun: tax time)
DOW_CALLS = [1.28, 1.08, 1.0, 0.98, 0.92, 0.35, 0.25]
DOW_CLAIMS = [1.35, 1.10, 1.0, 0.98, 0.95, 0.45, 0.35]
CARE_CAPACITY_DOW = [1.15, 1.05, 1.0, 1.0, 0.95, 0.45, 0.30]
CLAIMS_CAPACITY_DOW = [1, 1, 1, 1, 1, 0.30, 0.20]               # claims team mostly works weekdays


def industry_rate_rise(year: int) -> float:
    """Approved average industry premium increase effective 1 April (synthetic)."""
    return {2025: 0.0373, 2026: 0.0362, 2027: 0.0385}.get(year, 0.037)
