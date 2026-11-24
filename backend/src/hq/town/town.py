"""The town: 100 AI residents who decide whether, where and what health insurance to buy.

Residents are generated deterministically (seeded): name, age, suburb, occupation, income, household, health and lifestyle needs,
price sensitivity, their current cover (with our company, one of four fictional competitors, or none), and relations: family,
friends, neighbours, and links to the company's employees. Each simulated day some residents have a reason to shop (life
events, the 1 April premium notice, tax time, a friend's recommendation, a campaign they saw); their AI agent then reads the
company's information, a comparison site and the web, may ask an employee, talks to people they know, and decides.

All of it is synthetic. Competitor insurers are fictional. Health needs are used ONLY by the residents themselves: the company's
marketing can never target by health status (community rating) - the campaign audience is checked in code.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date
from typing import Any

from hq.company.store import Store

OURS = "aich"
INSURERS: dict[str, dict[str, Any]] = {
    OURS: {"name": "AI Company Health", "share": 4, "price": 1.0, "service": 0, "brand": 50,
           "note": "Runs the AI Company Health Private Hospital and Clinic in Wattle Grove: members pay no gap there."},
    "medibank": {"name": "Medibank", "share": 21, "price": 1.03, "service": 68, "brand": 80, "note": "Australia's largest health insurer."},
    "bupa": {"name": "Bupa", "share": 24, "price": 1.05, "service": 66, "brand": 78, "note": "Large national fund with its own dental and optical centres."},
    "hcf": {"name": "HCF", "share": 12, "price": 1.00, "service": 76, "brand": 62, "note": "Large not-for-profit fund."},
    "nib": {"name": "nib", "share": 10, "price": 0.96, "service": 70, "brand": 60, "note": "ASX-listed insurer with digital tools."},
    "hbf": {"name": "HBF", "share": 7, "price": 0.98, "service": 78, "brand": 52, "note": "Not-for-profit fund, strongest in Western Australia."},
    "ahm": {"name": "ahm", "share": 6, "price": 0.90, "service": 70, "brand": 55, "note": "Medibank's lower-cost online brand."},
    "teachers": {"name": "Teachers Health", "share": 3, "price": 0.97, "service": 82, "brand": 40, "eligible": "education",
                 "note": "Not-for-profit restricted fund for people working in education and their families."},
    "aunity": {"name": "Australian Unity", "share": 3, "price": 1.01, "service": 72, "brand": 45, "note": "Member-owned mutual."},
    "gmhba": {"name": "GMHBA", "share": 3, "price": 0.97, "service": 74, "brand": 40, "note": "Not-for-profit regional fund."},
}
INSURER_NOTE = ("Funds are real Australian health insurers with approximate public market shares. Prices, service scores and features in this "
                "simulation are indicative estimates, not quotes.")
SUBURBS = {"Harbourview": "high", "Riverside": "mid", "Wattle Park": "mid", "Eastgate": "low", "Banksia Hills": "high", "Old Town": "low",
           "Marina Bay": "high", "Gumtree Flats": "low"}
FIRST = ["Olivia", "Noah", "Charlotte", "Jack", "Amelia", "William", "Isla", "Oliver", "Mia", "Leo", "Ava", "Henry", "Grace", "Thomas", "Chloe", "Lucas",
         "Zoe", "James", "Ruby", "Ethan", "Aanya", "Arjun", "Mei", "Wei", "Hana", "Kenta", "Fatima", "Omar", "Layla", "Yusuf", "Sofia", "Mateo",
         "Lucia", "Diego", "Ngozi", "Kwame", "Amara", "Tane", "Aroha", "Jarrah", "Kirra", "Bindi", "Priya", "Rohan", "Linh", "Minh", "Elena", "Nikos",
         "Anika", "Lars", "Freya", "Hugo", "Ines", "Tariq", "Sana", "Jin", "Soo-ah", "Paolo", "Giulia", "Declan", "Siobhan", "Tom", "Ella", "Max"]
LAST = ["Nguyen", "Smith", "Williams", "Brown", "Wilson", "Taylor", "Patel", "Singh", "Chen", "Wang", "Kim", "Tran", "O'Connor", "Murphy", "Rossi",
        "Papadopoulos", "Kowalski", "Haddad", "Ahmed", "Okafor", "Mensah", "Walker", "Clarke", "Hughes", "Ng", "Lee", "Martin", "Garcia", "Silva",
        "Fernandes", "Yamamoto", "Sato", "Anderson", "Jensen", "Novak", "Ibrahim", "Kaur", "Sharma", "Thompson", "Campbell"]
JOBS = {"low": ["Retail assistant", "Barista", "Aged-care worker", "Delivery driver", "Student", "Cleaner", "Apprentice electrician", "Hospitality worker"],
        "mid": ["Teacher", "Nurse", "Electrician", "Office manager", "Paramedic", "Accountant", "Graphic designer", "Police officer", "Chef", "Physiotherapist"],
        "high": ["Software engineer", "Doctor", "Lawyer", "Business owner", "Engineering manager", "Architect", "Pharmacist", "Finance director", "Dentist"]}
NEEDS = ["dental", "optical", "physio", "pregnancy", "sports injuries", "mental health", "hip & knee", "ambulance", "chiropractic", "hearing aids"]
EMP_LINKS = [("sales.leo", "neighbour"), ("claims.tara", "sister"), ("care.amira", "friend"), ("mkt.julia", "cousin"), ("health.ayla", "friend"),
             ("people.ethan", "neighbour"), ("data.nora", "flatmate"), ("exec.mei", "friend"), ("prod.samir", "brother"), ("risk.lucas", "neighbour"),
             ("sales.ana", "aunt"), ("care.jonas", "friend"), ("claims.kofi", "neighbour"), ("bi.emma", "friend"), ("it.liam", "cousin"),
             ("mkt.omar", "friend"), ("health.piotr", "neighbour"), ("sales.wei", "former classmate"), ("care.sofia", "friend"), ("claims.victor", "uncle")]

# ----------------------------------------------------------------------------- where people work (the 3D city has these buildings)
WORKPLACES = {
    "mall": "Wattle Grove Mall", "hospital": "Wattle Grove Hospital", "school": "Wattle Grove Public School", "tafe": "TAFE & Uni campus",
    "towers": "Riverside business towers", "cafe": "High Street cafés & restaurants", "police": "Police station", "depot": "Logistics depot",
    "worksite": "Construction site", "clinic": "Medical & dental centre", "home": "Home",
}
JOB_PLACE = {"Retail assistant": "mall", "Barista": "cafe", "Aged-care worker": "hospital", "Delivery driver": "depot", "Cleaner": "towers",
             "Apprentice electrician": "worksite", "Hospitality worker": "cafe", "Teacher": "school", "Nurse": "hospital", "Electrician": "worksite",
             "Office manager": "towers", "Paramedic": "hospital", "Accountant": "towers", "Graphic designer": "towers", "Police officer": "police",
             "Chef": "cafe", "Physiotherapist": "clinic", "Software engineer": "towers", "Doctor": "hospital", "Lawyer": "towers", "Business owner": "mall",
             "Engineering manager": "towers", "Architect": "towers", "Pharmacist": "mall", "Finance director": "towers", "Dentist": "clinic",
             "Student": "tafe", "Retired": "home"}
EMPLOYERS = {"mall": ["Coastline Supermarket", "Wattle Pharmacy", "Urban Threads", "TechZone", "Bean & Leaf Café (mall)"],
             "hospital": ["Wattle Grove Hospital"], "school": ["Wattle Grove Public School"], "tafe": ["Wattle Grove TAFE"],
             "towers": ["Harbour Bank", "Southbank Software", "Gumtree Legal", "Koala Logistics HQ", "Riverside Architects", "Bright Accounting"],
             "cafe": ["The Grind", "Nonna's Kitchen", "Pho Corner", "Harbour Fish & Chips"], "police": ["NSW Police (Wattle Grove)"],
             "depot": ["ParcelGo depot"], "worksite": ["BuildRight Constructions"], "clinic": ["Wattle Grove Medical & Dental"], "home": ["—"]}
PAY = {"Retail assistant": (42, 55), "Barista": (40, 52), "Aged-care worker": (52, 66), "Delivery driver": (50, 68), "Cleaner": (44, 56),
       "Apprentice electrician": (35, 50), "Hospitality worker": (38, 52), "Teacher": (78, 115), "Nurse": (75, 110), "Electrician": (85, 125),
       "Office manager": (70, 95), "Paramedic": (80, 112), "Accountant": (75, 120), "Graphic designer": (62, 92), "Police officer": (78, 110),
       "Chef": (58, 80), "Physiotherapist": (78, 112), "Software engineer": (120, 210), "Doctor": (160, 320), "Lawyer": (110, 230),
       "Business owner": (60, 220), "Engineering manager": (150, 240), "Architect": (95, 160), "Pharmacist": (95, 135), "Finance director": (180, 300),
       "Dentist": (140, 260), "Student": (0, 22), "Retired": (28, 62)}
# Australian Government rebate tiers and Medicare Levy Surcharge (2025-26, approximate): singles thresholds; families and couples x2
TIERS = [(101_000, "Base tier", (.24288, .28337, .32385), 0.0), (118_000, "Tier 1", (.16192, .20240, .24289), .01),
         (158_000, "Tier 2", (.08095, .12143, .16192), .0125), (10**12, "Tier 3", (0.0, 0.0, 0.0), .015)]

SCHEMA = """
CREATE TABLE IF NOT EXISTS town_residents(id TEXT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS town_relations(a TEXT, b TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS town_events(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, resident TEXT, kind TEXT, insurer TEXT, plan TEXT, text TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS town_campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, by_agent TEXT, title TEXT, message TEXT, audience TEXT, offer TEXT, until TEXT);
CREATE TABLE IF NOT EXISTS town_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, resident TEXT, insurer TEXT, stars INTEGER, text TEXT);
CREATE TABLE IF NOT EXISTS town_msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, frm TEXT, to_res TEXT, text TEXT);
"""
HEALTH_WORDS = ("health", "condition", "claim", "illness", "disease", "pregnan", "injur", "chronic", "disab", "mental", "medical", "sick", "bmi")


def eligible(ins: str, members: list[dict[str, Any]]) -> bool:
    e = INSURERS[ins].get("eligible")
    return not e or any(m.get("workplace") in ("school", "tafe") or m.get("occupation") in ("Teacher",) for m in members)


def initial_cover(rnd: random.Random, adult: dict[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [k for k in INSURERS if eligible(k, members)]
    ins = rnd.choices(keys, [INSURERS[k]["share"] for k in keys])[0]
    old, fam = adult["age"] >= 55, len(members) > 2
    tier = rnd.choices(["gold", "silver", "bronze", "basic"], [40 if old else 15, 35 if fam else 25, 30, 15 if adult["income"] == "low" else 8])[0]
    return {"insurer": ins, "tier": tier, "extras": rnd.random() < (.75 if fam or adult["income"] != "low" else .45),
            "since": f"{rnd.randint(2008, 2025)}-{rnd.randint(1, 12):02d}-15"}


TRAITS = ["outgoing", "reserved", "curious", "cautious", "organised", "spontaneous", "warm", "practical", "ambitious", "easygoing", "anxious", "optimistic"]
HOBBIES = ["going to the gym", "running", "reading", "gardening", "gaming", "cooking", "surfing", "footy", "yoga", "fishing", "music", "painting", "cycling", "volunteering"]
VALUES = ["family first", "saving money", "staying healthy", "convenience", "community", "career growth", "adventure", "security"]


def enrich_person(r: dict[str, Any], rnd: random.Random) -> bool:
    """Personality, home and belongings: so each agent knows who they are, where they live and what they have."""
    if "traits" in r:
        return False
    r["traits"] = rnd.sample(TRAITS, 3)
    r["hobbies"] = rnd.sample(HOBBIES, 2) if r["age"] >= 8 else ["playing"]
    r["values"] = rnd.sample(VALUES, 2)
    rich = r.get("income") == "high"
    r["home"] = {"tenure": rnd.choice(["owns outright", "owns with a mortgage"] if rich or r["age"] > 55 else ["renting", "owns with a mortgage", "renting"]),
                 "dwelling": rnd.choice(["house", "house", "townhouse", "apartment"]), "bedrooms": rnd.randint(2, 5) if r["household_kind"] in ("family", "retirees") else rnd.randint(1, 3)}
    r["home"]["value_or_rent"] = (f"${rnd.randint(520, 980)}/week rent" if r["home"]["tenure"] == "renting" else f"${rnd.randint(7, 25) * 100_000:,} home")
    r["assets"] = {"savings": rnd.choice(["under $5k", "$5k-20k", "$20k-60k", "$60k-150k", "over $150k"] if rich else ["under $5k", "$5k-20k", "$20k-60k"]),
                   "pets": rnd.choice(["none", "none", "a dog", "a cat", "two cats", "a dog and a cat", "fish"])}
    return True


class Town:
    def __init__(self, store: Store, company: Any, seed: int = 11):
        self.store, self.co, self.seed = store, company, seed
        store.db.executescript(SCHEMA)
        store.commit()
        if not store.one("SELECT id FROM town_residents LIMIT 1"):
            self._generate()
        self._enrich_all()
        from hq.town.health import Health
        from hq.town.life import Life
        self.life = Life(self)
        self.health = Health(self)
        from hq.town.competitors import Competitors
        self.competitors = Competitors(self)

    # ------------------------------------------------------------------ generation
    def _generate(self) -> None:
        rnd = random.Random(self.seed)
        residents: list[dict[str, Any]] = []
        names: set[str] = set()
        house = 0
        seq = [0]

        def person(age: int, suburb: str, last: str, role: str, hh: int, kind: str) -> dict[str, Any]:
            while True:
                first = rnd.choice(FIRST)
                if f"{first} {last}" not in names:
                    names.add(f"{first} {last}")
                    break
            inc = SUBURBS[suburb] if age >= 22 else "low"
            if age >= 22 and rnd.random() < .25:
                inc = rnd.choice(["low", "mid", "high"])
            job = "Retired" if age >= 66 else ("Student" if age < 21 else rnd.choice(JOBS[inc]))
            needs = set()
            if age < 18 or rnd.random() < .45:
                needs.add("dental")
            if age > 40 or rnd.random() < .3:
                needs.add("optical")
            if 24 <= age <= 40 and kind in ("couple", "family") and rnd.random() < .3:
                needs.add("pregnancy")
            if age < 45 and rnd.random() < .3:
                needs.add("sports injuries")
            if age > 55 and rnd.random() < .5:
                needs.add("hip & knee")
            if rnd.random() < .2:
                needs.add(rnd.choice(["physio", "mental health", "chiropractic", "ambulance"]))
            if age > 70 and rnd.random() < .3:
                needs.add("hearing aids")
            seq[0] += 1
            return {"id": f"r{seq[0]:03d}", "name": f"{first} {last}", "age": age, "suburb": suburb, "occupation": job, "income": inc,
                    "household": hh, "household_kind": kind, "role_in_household": role, "needs": sorted(needs),
                    "price_sensitivity": round(min(1, max(0, rnd.gauss({"low": .8, "mid": .55, "high": .3}[inc], .15))), 2),
                    "digital": round(min(1, max(0, rnd.gauss(.75 if age < 45 else .45, .2))), 2),
                    "personality": rnd.choice(["careful researcher", "bargain hunter", "loyal and busy", "asks friends first", "brand-conscious", "sceptical of insurers"]),
                    "cover": None, "held_hospital_before": False}

        while len(residents) < 100:
            suburb = rnd.choice(list(SUBURBS))
            last = rnd.choice(LAST)
            kind = rnd.choices(["single", "couple", "family", "single_parent", "retirees", "share_house"], [22, 18, 26, 8, 12, 6])[0]
            if kind == "single":
                members = [(rnd.randint(19, 62), "single")]
            elif kind == "couple":
                a = rnd.randint(24, 60)
                members = [(a, "partner"), (max(20, a + rnd.randint(-4, 4)), "partner")]
            elif kind == "family":
                a = rnd.randint(29, 50)
                kids = rnd.randint(1, 3)
                members = [(a, "parent"), (a + rnd.randint(-3, 3), "parent")] + [(rnd.randint(1, 17), "child") for _ in range(kids)]
            elif kind == "single_parent":
                a = rnd.randint(27, 48)
                members = [(a, "parent")] + [(rnd.randint(2, 16), "child") for _ in range(rnd.randint(1, 2))]
            elif kind == "retirees":
                a = rnd.randint(64, 82)
                members = [(a, "partner"), (a + rnd.randint(-3, 3), "partner")]
            else:
                members = [(rnd.randint(20, 30), "housemate") for _ in range(3)]
            members = members[:100 - len(residents)]
            ppl = [person(age, suburb, last if kind != "share_house" else rnd.choice(LAST), role, house, kind) for age, role in members]
            residents += ppl
            house += 1
        # current cover, household-level (adults decide for the household)
        for hh in range(house):
            mem = [r for r in residents if r["household"] == hh]
            adult = max(mem, key=lambda r: r["age"])
            cover = initial_cover(rnd, adult, mem)            # membership is mandatory in Wattle Grove
            for r in mem:
                r["cover"] = dict(cover) if cover else None
                r["held_hospital_before"] = bool(cover and cover.get("tier")) or rnd.random() < .2
        rels: list[tuple[str, str, str]] = []
        for hh in range(house):
            mem = [r for r in residents if r["household"] == hh]
            for i, a in enumerate(mem):
                for b in mem[i + 1:]:
                    k = "partner" if a["role_in_household"] == b["role_in_household"] in ("partner", "parent") else \
                        "housemate" if a["role_in_household"] == "housemate" else "family"
                    rels.append((a["id"], b["id"], k))
        adults = [r for r in residents if r["age"] >= 16]
        for r in adults:
            for _ in range(rnd.randint(1, 3)):
                o = rnd.choice(adults)
                if o["id"] != r["id"] and o["household"] != r["household"]:
                    rels.append((r["id"], o["id"], rnd.choice(["friend", "friend", "work colleague", "gym buddy"])))
        for hh in range(house - 1):                                     # neighbours: next-door houses in the same street
            a = next(r for r in residents if r["household"] == hh)
            b = next(r for r in residents if r["household"] == hh + 1)
            rels.append((a["id"], b["id"], "neighbour"))
        for (emp, kind), r in zip(EMP_LINKS, rnd.sample(adults, len(EMP_LINKS))):
            rels.append((r["id"], emp, kind))
        self.store.db.executemany("INSERT INTO town_residents VALUES (?,?)", [(r["id"], json.dumps(r)) for r in residents])
        self.store.db.executemany("INSERT INTO town_relations VALUES (?,?,?)", rels)
        self.store.commit()

    def _enrich_all(self) -> None:
        """Jobs, employers, workplaces, pay and vehicles (added to towns created before these existed)."""
        changed = False
        res = self.residents()
        from hq.town.life import enrich_life
        hhs: dict[int, list] = {}
        for r in res:
            hhs.setdefault(r["household"], []).append(r)
        for r in res:
            rr = random.Random(f"{self.seed}-life-{r['id']}")
            a = enrich_life(r, rr)
            b = enrich_person(r, random.Random(f"{self.seed}-me-{r['id']}"))
            c = False
            if not r.get("cover") or r["cover"].get("insurer") not in INSURERS:   # mandatory membership with the real Australian funds
                mem = hhs[r["household"]]
                head = max(mem, key=lambda x: x["age"])
                if head.get("_cov") is None:
                    head["_cov"] = initial_cover(random.Random(f"{self.seed}-cov-{r['household']}"), head, mem)
                r["cover"] = dict(head["_cov"])
                c = True
            if a or b or c:
                changed = True
                self._save({k: v for k, v in r.items() if k != "_cov"})
            if "income_aud" in r:
                continue
            rnd = random.Random(f"{self.seed}-{r['id']}")
            if r["age"] < 18:
                r.update(occupation="School student", workplace="school", employer="Wattle Grove Public School", income_aud=0,
                         vehicle="walks to school" if r["age"] > 11 else "dropped off by a parent")
            else:
                job = r["occupation"]
                lo, hi = PAY.get(job, (50, 80))
                place = JOB_PLACE.get(job, "towers")
                r["workplace"] = place
                r["employer"] = rnd.choice(EMPLOYERS[place])
                r["income_aud"] = int(rnd.uniform(lo, hi) * 1000) if job != "Student" or rnd.random() < .6 else 0
                car = {"low": .55, "mid": .8, "high": .92}[r["income"]] - (.3 if r["age"] < 22 else 0)
                roll = rnd.random()
                r["vehicle"] = (rnd.choice(["Toyota Corolla", "Mazda 3", "Hyundai i30", "Kia Cerato"]) if r["income"] == "low" else
                                rnd.choice(["Toyota RAV4", "Mazda CX-5", "Ford Ranger ute", "Subaru Forester", "Kia Sportage"]) if r["income"] == "mid" else
                                rnd.choice(["Tesla Model 3", "BMW X3", "Audi Q5", "Volvo XC60", "Lexus RX"])) if roll < car else \
                    rnd.choice(["bicycle", "e-bike", "bus & train"]) if roll < car + .3 else "walks"
            changed = True
            self._save(r)
        if changed:
            self.store.commit()

    # ------------------------------------------------------------------ money: household income, rebate, Medicare Levy Surcharge
    def household(self, r: dict[str, Any]) -> list[dict[str, Any]]:
        return [x for x in self.residents() if x["household"] == r["household"]]

    def household_income(self, r: dict[str, Any]) -> int:
        return sum(int(x.get("income_aud", 0)) for x in self.household(r) if x["age"] >= 18)

    def tier(self, r: dict[str, Any]) -> tuple[str, tuple, float]:
        fam = r["household_kind"] in ("couple", "family", "single_parent", "retirees")
        inc = self.household_income(r) if fam else int(r.get("income_aud", 0))
        for limit, name, reb, mls in TIERS:
            if inc <= limit * (2 if fam else 1):
                return name, reb, mls
        return TIERS[-1][1], TIERS[-1][2], TIERS[-1][3]

    def mls(self, r: dict[str, Any]) -> int:
        """Medicare Levy Surcharge the household would pay per year WITHOUT hospital cover."""
        _, _, rate = self.tier(r)
        fam = r["household_kind"] in ("couple", "family", "single_parent", "retirees")
        return int(rate * (self.household_income(r) if fam else int(r.get("income_aud", 0))))

    # ------------------------------------------------------------------ reads
    def all_residents(self) -> list[dict[str, Any]]:
        """Everyone who ever lived in the town (including people who have passed away)."""
        return [json.loads(r["data"]) for r in self.store.rows("SELECT data FROM town_residents ORDER BY id")]

    def residents(self) -> list[dict[str, Any]]:
        return [r for r in self.all_residents() if not r.get("deceased")]

    def resident(self, rid: str) -> dict[str, Any] | None:
        r = self.store.one("SELECT data FROM town_residents WHERE id=?", (rid,))
        return json.loads(r["data"]) if r else None

    def _save(self, r: dict[str, Any]) -> None:
        self.store.db.execute("UPDATE town_residents SET data=? WHERE id=?", (json.dumps(r), r["id"]))

    def relations(self, rid: str) -> list[dict[str, Any]]:
        from hq.agents.roster import AGENTS
        out = []
        for row in self.store.rows("SELECT * FROM town_relations WHERE a=? OR b=?", (rid, rid)):
            other = row["b"] if row["a"] == rid else row["a"]
            if other.startswith("r"):
                o = self.resident(other)
                if o:
                    out.append({"id": other, "name": o["name"], "relation": row["kind"] + (" (passed away)" if o.get("deceased") else ""), "employee": False,
                                "cover": self._cover_label(o.get("cover")), "deceased": o.get("deceased")})
            elif other in AGENTS:
                a = AGENTS[other]
                out.append({"id": other, "name": a.name, "relation": row["kind"], "employee": True, "role": a.role, "dept": a.dept})
        return out

    def employee_contacts(self) -> list[dict[str, Any]]:
        return self.store.rows("SELECT a AS resident, b AS employee, kind FROM town_relations WHERE b NOT LIKE 'r%'")

    @staticmethod
    def _cover_label(c: dict | None) -> str:
        if not c:
            return "not yet a member of a fund (membership is mandatory)"
        t = f"{c['tier'].title()} hospital" if c.get("tier") else "extras only"
        return f"{INSURERS[c['insurer']]['name']}: {t}{' + extras' if c.get('tier') and c.get('extras') else ''}"

    # ------------------------------------------------------------------ the market (company + fictional competitors)
    def _our_plans(self) -> list[dict[str, Any]]:
        return [p for p in self.co.products_view() if p["active"] and p["category"] in ("hospital", "extras", "combined")]

    def household_factor(self, r: dict[str, Any]) -> float:
        return {"single": 1, "share_house": 1, "single_parent": 1, "couple": 2, "retirees": 2, "family": 2}[r["household_kind"]]

    def rebate(self, r: dict[str, Any]) -> float:
        """Australian Government rebate on premiums: by income tier and the oldest adult's age (under 65 / 65-69 / 70+)."""
        _, reb, _ = self.tier(r)
        age = max(x["age"] for x in self.household(r))
        return reb[0 if age < 65 else 1 if age < 70 else 2]

    def lhc(self, r: dict[str, Any]) -> float:
        """Lifetime Health Cover loading on hospital cover: 2% per year over 30 when first taking hospital cover, max 70%."""
        if r.get("held_hospital_before") or r["age"] <= 30:
            return 0.0
        return min(.70, .02 * (r["age"] - 30))

    def comparison(self, r: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """The comparison site: every insurer's matching plans, priced for this resident's household (after rebate, with LHC loading)."""
        rev = self.review_scores()
        k = self.co.kpi_window(28) or {}
        cur = k.get("current", {})
        our_service = max(40, min(95, 50 + (cur.get("claims_sla_pct", 90) - 85) * 1.2 + (cur.get("nps", 25) - 20) * 0.8 - max(0, cur.get("avg_wait_s", 150) - 150) / 12))
        promos = {c["offer"]: c for c in self.active_campaigns()}
        lev = self.co.economy.levers() if getattr(self.co, "economy", None) else {}
        our_service = min(97, our_service + lev.get("service_boost", 0))
        hh = self.household(r) if r else []
        member = r is not None and (r.get("cover") or {}).get("insurer") == OURS
        disc = 0.0 if member else lev.get("new_joiner_discount", 0.0)
        if r and lev.get("group_employers") and r.get("employer") in lev["group_employers"]:
            disc = max(disc, lev.get("group_discount", 0.05))
        out = []
        for ins, meta in INSURERS.items():
            if r and not eligible(ins, hh):
                continue
            cmult, cbrand, coffer = self.competitors.adjust(ins) if ins != OURS else (1.0, 0.0, "")
            for p in self._our_plans():
                price = p["monthly_price"] * ((1.0 - disc) if ins == OURS else meta["price"] * self.co.sim.s["market_idx"] * cmult)
                gross = price * (self.household_factor(r) if r else 1)
                net = gross * (1 - (self.rebate(r) if r else .164)) * (1 + (self.lhc(r) if r and p["category"] in ("hospital", "combined") else 0))
                name = p["name"] if ins == OURS else p["name"].replace("AI Company", meta["name"]).replace("Health ", "")
                out.append({"insurer": ins, "insurer_name": meta["name"], "plan_id": p["id"] if ins == OURS else f"{ins}:{p['id']}", "plan": name,
                            "category": p["category"], "tier": p["tier"], "monthly_price": round(net, 2),
                            "service_score": round(our_service if ins == OURS else meta["service"]), "brand": meta["brand"] + cbrand,
                            "reviews": rev.get(ins), "note": meta["note"],
                            "offer": ("; ".join([x for x in [f"{disc*100:.0f}% off for new members" if disc else "",
                                                             next((c["offer"] for c in promos.values() if c["offer"]), "")] if x]) if ins == OURS else
                                      "; ".join(x for x in [coffer, "No gap on selected extras" if ins in ("hcf", "bupa") else ""] if x)),
                            "perks": lev.get("perks", []) if ins == OURS else []})
        return out

    # ------------------------------------------------------------------ campaigns (Marketing)
    def launch_campaign(self, by: str, title: str, message: str, audience: dict[str, Any], offer: str, weeks: int) -> dict[str, Any]:
        flat = json.dumps(audience).lower() + " " + message.lower()
        if any(w in json.dumps(audience).lower() for w in HEALTH_WORDS):
            return {"error": "community rating: a campaign audience cannot use health status, conditions or claims history. Target by suburb, age band or life stage."}
        if int(audience.get("age_min", 18) or 18) < 18:
            return {"error": "marketing must not target under-18s"}
        if any(w in flat for w in ("guaranteed", "free forever", "no waiting period on pre-existing")):
            return {"error": "ASIC: the message looks misleading"}
        until = date.fromordinal(self.co.today.toordinal() + 7 * max(1, min(int(weeks), 8))).isoformat()
        cur = self.store.db.execute("INSERT INTO town_campaigns(date,by_agent,title,message,audience,offer,until) VALUES (?,?,?,?,?,?,?)",
                                    (self.co.today.isoformat(), by, title[:120], message[:400], json.dumps(audience), offer[:160], until))
        self.store.commit()
        n = len([r for r in self.residents() if self._targets(audience, r)])
        return {"ok": True, "campaign_id": int(cur.lastrowid or 0), "reach": n, "until": until}

    def active_campaigns(self) -> list[dict[str, Any]]:
        rows = self.store.rows("SELECT * FROM town_campaigns WHERE until >= ? ORDER BY id DESC", (self.co.today.isoformat(),))
        for r in rows:
            r["audience"] = json.loads(r["audience"] or "{}")
        return rows

    @staticmethod
    def _targets(a: dict[str, Any], r: dict[str, Any]) -> bool:
        if r["age"] < 18:
            return False
        if a.get("suburbs") and r["suburb"] not in a["suburbs"]:
            return False
        if a.get("age_min") and r["age"] < int(a["age_min"]):
            return False
        if a.get("age_max") and r["age"] > int(a["age_max"]):
            return False
        if a.get("life_stage") and r["household_kind"] not in a["life_stage"]:
            return False
        return True

    # ------------------------------------------------------------------ social
    def feed(self, rid: str) -> dict[str, Any]:
        r = self.resident(rid)
        ads = [{"title": c["title"], "message": c["message"], "offer": c["offer"]} for c in self.active_campaigns() if r and self._targets(c["audience"], r)]
        msgs = self.store.rows("SELECT date, frm, text FROM town_msgs WHERE to_res=? ORDER BY id DESC LIMIT 6", (rid,))
        for m in msgs:
            o = self.resident(m["frm"])
            m["from"] = o["name"] if o else m["frm"]
        reviews = self.store.rows("SELECT date, insurer, stars, text FROM town_reviews ORDER BY id DESC LIMIT 8")
        return {"ads_you_saw": ads[:3], "messages_from_people_you_know": msgs, "recent_reviews_in_town": reviews}

    def message(self, frm: str, to: str, text: str) -> dict[str, Any]:
        if not self.resident(to):
            return {"error": "unknown resident"}
        self.store.db.execute("INSERT INTO town_msgs(date,frm,to_res,text) VALUES (?,?,?,?)", (self.co.today.isoformat(), frm, to, text[:300]))
        self.store.commit()
        return {"ok": True}

    def review(self, rid: str, insurer: str, stars: int, text: str) -> dict[str, Any]:
        if insurer not in INSURERS:
            return {"error": f"insurer must be one of {list(INSURERS)}"}
        self.store.db.execute("INSERT INTO town_reviews(date,resident,insurer,stars,text) VALUES (?,?,?,?,?)",
                              (self.co.today.isoformat(), rid, insurer, max(1, min(5, int(stars))), text[:300]))
        self.store.commit()
        return {"ok": True}

    def review_scores(self) -> dict[str, dict[str, Any]]:
        return {r["insurer"]: {"avg_stars": round(r["s"], 1), "count": r["n"]}
                for r in self.store.rows("SELECT insurer, AVG(stars) s, COUNT(*) n FROM town_reviews GROUP BY insurer")}

    # ------------------------------------------------------------------ decisions
    def event(self, rid: str, kind: str, text: str, insurer: str | None = None, plan: str | None = None, data: dict | None = None) -> dict[str, Any]:
        cur = self.store.db.execute("INSERT INTO town_events(date,resident,kind,insurer,plan,text,data) VALUES (?,?,?,?,?,?,?)",
                                    (self.co.today.isoformat(), rid, kind, insurer, plan, text[:400], json.dumps(data or {})))
        self.store.commit()
        return {"id": int(cur.lastrowid or 0), "date": self.co.today.isoformat(), "resident": rid, "kind": kind, "insurer": insurer, "plan": plan, "text": text[:400]}

    def buy(self, rid: str, plan_id: str, reason: str) -> dict[str, Any]:
        r = self.resident(rid)
        offer = next((p for p in self.comparison(r) if p["plan_id"] == plan_id), None)
        if not r or not offer:
            return {"error": "unknown plan; use a plan_id from compare_insurers"}
        before = self._cover_label(r.get("cover"))
        tier = offer["tier"]
        cover = {"insurer": offer["insurer"], "tier": tier, "extras": offer["category"] in ("extras", "combined"), "since": self.co.today.isoformat(),
                 "plan_id": plan_id, "plan": offer["plan"], "monthly_price": offer["monthly_price"],
                 "transferred": bool((r.get("cover") or {}).get("insurer"))}     # waiting periods already served carry over when switching
        for m in [x for x in self.residents() if x["household"] == r["household"]]:          # the policy covers the household
            m["cover"] = dict(cover)
            m["held_hospital_before"] = m.get("held_hospital_before") or bool(tier)
            self._save(m)
        self.store.commit()
        prev_ins = (r.get("cover") or {}).get("insurer")
        switched = bool(prev_ins)
        kind = "switch" if switched and prev_ins != offer["insurer"] else ("buy" if not switched else "change_plan")
        return self.event(rid, kind, f"{r['name']} {'switched to' if kind == 'switch' else 'bought' if kind == 'buy' else 'changed to'} "
                                     f"{offer['insurer_name']} {offer['plan']} (${offer['monthly_price']:.0f}/mo for the household). Why: {reason}",
                          offer["insurer"], plan_id, {"before": before, "before_insurer": prev_ins, "price": offer["monthly_price"], "reason": reason})

    def keep(self, rid: str, reason: str) -> dict[str, Any]:
        r = self.resident(rid) or {}
        return self.event(rid, "keep", f"{r.get('name', rid)} kept {self._cover_label(r.get('cover'))}. Why: {reason}", (r.get("cover") or {}).get("insurer"),
                          data={"reason": reason})

    def cancel(self, rid: str, reason: str) -> dict[str, Any]:
        r = self.resident(rid)
        if True:
            return {"error": "Health insurance membership is mandatory in Wattle Grove: you cannot cancel, but you can switch fund or plan with buy_policy."}
        if not r or not r.get("cover"):
            return {"error": "you have no cover to cancel"}
        ins = r["cover"]["insurer"]
        for m in [x for x in self.residents() if x["household"] == r["household"]]:
            m["cover"] = None
            self._save(m)
        self.store.commit()
        return self.event(rid, "cancel", f"{r['name']} cancelled {INSURERS[ins]['name']} cover. Why: {reason}", ins, data={"reason": reason})

    # ------------------------------------------------------------------ who shops today
    def triggers(self, d: date, limit: int = 6) -> list[dict[str, Any]]:
        rnd = random.Random(f"{self.seed}-{d.isoformat()}")
        res = [r for r in self.residents() if r["age"] >= 18]
        heads: dict[int, dict] = {}
        for r in sorted(res, key=lambda x: -x["age"]):
            heads.setdefault(r["household"], r)                     # one decision-maker per household
        camps = self.active_campaigns()
        recent_msg = {m["to_res"] for m in self.store.rows("SELECT to_res FROM town_msgs WHERE date >= date(?, '-3 day')", (d.isoformat(),))}
        out = []
        for r in heads.values():
            c, why = r.get("cover"), None
            if d.month == 3 and d.day >= 10 and c and rnd.random() < .05:
                why = "Your premium increase notice for 1 April just arrived."
            elif d.month in (5, 6) and r["income"] == "high" and not (c and c.get("tier")) and rnd.random() < .08:
                why = "Your accountant warned you about the Medicare Levy Surcharge at tax time."
            elif 29 <= r["age"] <= 31 and not (c and c.get("tier")) and rnd.random() < .03:
                why = "You just learned about the Lifetime Health Cover loading that starts after 30."
            elif r["id"] in recent_msg and rnd.random() < .5:
                why = "Someone you know messaged you about health insurance."
            elif any(self._targets(cp["audience"], r) for cp in camps) and rnd.random() < .05:
                why = "You saw an AI Company Health ad."
            elif rnd.random() < .035:
                why = rnd.choice(["You're expecting a baby next year.", "You just moved house.", "You started a new job with a better salary.",
                                  "A friend had a big dental bill.", "You're getting knee pain when running.", "Your last claim was slow and annoying.",
                                  "You're retiring soon and reviewing your costs."])
            if why:
                out.append({"resident": r["id"], "name": r["name"], "reason": why})
        rnd.shuffle(out)
        return out[:limit]

    # ------------------------------------------------------------------ insights (for the company's teams, aggregate only)
    def insights(self) -> dict[str, Any]:
        res = self.residents()
        heads: dict[int, dict] = {}
        for r in res:
            heads.setdefault(r["household"], r)
        share: dict[str, int] = {}
        for r in res:
            k = (r.get("cover") or {}).get("insurer") or "none"
            share[k] = share.get(k, 0) + 1
        ev = self.store.rows("SELECT * FROM town_events ORDER BY id DESC LIMIT 400")
        since = self.store.rows("SELECT kind, insurer, COUNT(*) n FROM town_events WHERE date >= date(?, '-28 day') GROUP BY kind, insurer", (self.co.today.isoformat(),))
        return {"residents": len(res), "households": len(heads),
                "note_on_funds": INSURER_NOTE,
                "people_covered_by": {(INSURERS[k]["name"] if k in INSURERS else "no fund yet"): v for k, v in sorted(share.items(), key=lambda x: -x[1])},
                "our_share_of_people": round(share.get(OURS, 0) / max(1, len(res)), 3),
                "decisions_last_28d": since,
                "recent_reasons": [e["text"] for e in ev[:12]],
                "reviews": self.review_scores(),
                "active_campaigns": [{k: c[k] for k in ("title", "offer", "until")} for c in self.active_campaigns()],
                "note": "Aggregate view only. Never target people by health status (community rating)."}

    def snapshot(self) -> dict[str, Any]:
        """Everything the 3D town needs."""
        res = self.residents()
        rels = self.store.rows("SELECT * FROM town_relations")
        why = self.reasons()
        return {"residents": [{k: r.get(k) for k in ("id", "name", "age", "suburb", "occupation", "income", "household", "household_kind", "role_in_household",
                                                      "needs", "personality", "cover", "workplace", "employer", "income_aud", "vehicle", "gender", "birthday",
                                                      "traits", "hobbies", "values", "home", "assets")}
                              | {"cover_label": self._cover_label(r.get("cover")), "cover_reason": why.get(r["household"])} for r in res],
                "workplaces": WORKPLACES, "facilities": self.life.facilities(), "funds_note": INSURER_NOTE,
                "departed": [{"id": r["id"], "name": r["name"], "age": r["age"], "date": r["deceased"]} for r in self.all_residents() if r.get("deceased")][-30:],
                "relations": rels, "insurers": {k: v["name"] for k, v in INSURERS.items()},
                "events": self.store.rows("SELECT * FROM town_events ORDER BY id DESC LIMIT 60"), "campaigns": self.active_campaigns()}

    def reasons(self) -> dict[int, str]:
        """The latest reason behind each household's current cover (None when they never told us)."""
        res = {r["id"]: r for r in self.residents()}
        out: dict[int, str] = {}
        for e in self.store.rows("SELECT resident, data FROM town_events WHERE kind IN ('buy','switch','change_plan','keep','cancel') ORDER BY id"):
            r = res.get(e["resident"])
            if r:
                out[r["household"]] = (json.loads(e["data"] or "{}").get("reason") or "").strip() or None
        return out

    def history(self, rid: str) -> dict[str, Any]:
        r = self.resident(rid)
        if not r:
            return {}
        tname, reb, _ = self.tier(r)
        money = {"income_aud": r.get("income_aud", 0), "household_income_aud": self.household_income(r), "income_tier": tname,
                 "government_rebate_pct": round(self.rebate(r) * 100, 2), "medicare_levy_surcharge_if_no_hospital_cover_aud": self.mls(r),
                 "lhc_loading_pct": round(self.lhc(r) * 100)}
        return {"resident": r | {"cover_label": self._cover_label(r.get("cover"))}, "cover_reason": self.reasons().get(r["household"]),
                "health": self.health.claims(rid, 20),
                "money": money, "relations": self.relations(rid),
                "events": self.store.rows("SELECT * FROM town_events WHERE resident=? ORDER BY id DESC LIMIT 30", (rid,)),
                "messages": self.store.rows("SELECT * FROM town_msgs WHERE frm=? OR to_res=? ORDER BY id DESC LIMIT 20", (rid, rid)),
                "reviews": self.store.rows("SELECT * FROM town_reviews WHERE resident=? ORDER BY id DESC", (rid,))}


def mock_choice(town: Town, r: dict[str, Any], comparison: list[dict[str, Any]], feed: dict[str, Any]) -> tuple[str | None, str]:
    """Offline decision rule for a resident (tests and no-Gemini mode): needs, price sensitivity, service, word of mouth and ads."""
    needs = set(r["needs"])
    kind = r["household_kind"]
    mls = int(r.get("mls_if_no_hospital", 0) or 0)
    want_hospital = kind in ("family", "couple", "retirees") or mls > 0 or r["age"] > 45 or "pregnancy" in needs or "hip & knee" in needs
    want_extras = bool(needs & {"dental", "optical", "physio", "chiropractic", "hearing aids"})
    if not want_hospital and not want_extras:
        want_hospital = True                                                    # membership is mandatory: the cheapest fitting hospital cover
    cat = "combined" if want_hospital and want_extras else ("hospital" if want_hospital else "extras")
    tier = "gold" if ("pregnancy" in needs or "hip & knee" in needs or r["age"] > 65) else ("silver" if kind == "family" else ("basic" if r["price_sensitivity"] > .7 else "bronze"))
    cands = [c for c in comparison if c["category"] == cat and (c["tier"] in (tier, None) or cat == "extras")] or [c for c in comparison if c["category"] == cat]
    if not cands:
        return "keep", "Nothing on the comparison site was better for me."
    ads = 1 if feed.get("ads_you_saw") else 0
    wom = " ".join(m["text"].lower() for m in feed.get("messages_from_people_you_know", []))
    lo = min(c["monthly_price"] for c in cands)

    def score(c: dict) -> float:
        s = -r["price_sensitivity"] * (c["monthly_price"] - lo) / max(lo, 1) * 10 + (c["service_score"] - 60) / 10 + c["brand"] / 50
        if c["insurer"] == OURS:
            s += ads * .8 + (2 if "ai company" in wom and "avoid" not in wom else 0) + (.7 if needs & {"dental", "optical", "physio"} else 0) + .4 * len(c.get("perks") or [])
        if (r.get("cover") or {}).get("insurer") == c["insurer"]:
            s += 1.2                                                    # inertia
        if c["offer"]:
            s += .6
        return s
    best = max(cands, key=score)
    cur = (r.get("cover") or {}).get("insurer")
    if cur == best["insurer"] and (r.get("cover") or {}).get("tier") == best["tier"]:
        return "keep", f"My {best['insurer_name']} cover still fits my needs at a fair price."
    return best["plan_id"], (f"Best fit for {', '.join(sorted(needs)) or 'my situation'} at ${best['monthly_price']:.0f}/mo, service score {best['service_score']}"
                             + (f"; it also avoids ${mls:,}/yr Medicare Levy Surcharge" if mls and best["tier"] else "")
                             + (", and the ad caught my eye" if ads and best["insurer"] == OURS else ""))


def mock_search(query: str, town: Town) -> str:
    q = query.lower()
    tips = ["Private Health Insurance in Australia: hospital cover tiers are Gold, Silver, Bronze and Basic; extras cover dental, optical and physio.",
            "Lifetime Health Cover: if you take hospital cover after 1 July following your 31st birthday you pay a 2% loading per year over 30 (max 70%) for 10 years.",
            "Medicare Levy Surcharge: singles earning over ~$97k without hospital cover pay 1-1.5% extra tax.",
            "The government rebate reduces premiums by up to ~25% depending on income and age.",
            "Waiting periods: 2 months general, 12 months for pre-existing conditions and pregnancy."]
    pick = [t for t in tips if any(w in t.lower() for w in q.split())] or tips[:3]
    rev = town.review_scores()
    news = [f"{v['name']}: {v['note']}" for k, v in INSURERS.items()]
    return " | ".join(pick + news[:3] + [f"Town reviews: {json.dumps(rev)}" if rev else "No reviews yet."])


def _unused() -> float:  # keep math import for future pricing tweaks
    return math.pi
