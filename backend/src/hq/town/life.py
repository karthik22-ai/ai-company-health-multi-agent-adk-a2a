"""Life in Wattle Grove: every simulated day people age, have birthdays, grow up and get jobs, retire, make friends, find partners, have
babies, pass away, and new families move in. Once a month the town council decides what the town needs to build.

Rates are realistic Australian orders of magnitude, accelerated (ACCEL) so that changes are visible within weeks of simulated time.
Deterministic per (seed, date). All of it is synthetic.
"""
from __future__ import annotations

import json
import random
from datetime import date
from typing import Any

from hq.town.town import EMPLOYERS, JOB_PLACE, JOBS, LAST, PAY, SUBURBS

ACCEL = 10
FEMALE = {"Olivia", "Charlotte", "Amelia", "Isla", "Mia", "Ava", "Grace", "Chloe", "Zoe", "Ruby", "Aanya", "Mei", "Hana", "Fatima", "Layla", "Sofia",
          "Lucia", "Ngozi", "Amara", "Aroha", "Kirra", "Bindi", "Priya", "Linh", "Elena", "Anika", "Freya", "Ines", "Sana", "Soo-ah", "Giulia", "Siobhan", "Ella"}
MALE_NEW = ["Noah", "Jack", "William", "Oliver", "Leo", "Henry", "Thomas", "Lucas", "James", "Ethan", "Arjun", "Wei", "Kenta", "Omar", "Yusuf", "Mateo",
            "Diego", "Kwame", "Tane", "Jarrah", "Rohan", "Minh", "Nikos", "Lars", "Hugo", "Tariq", "Jin", "Paolo", "Declan", "Tom", "Max"]
FACILITIES = {
    "childcare": ("Little Wattles Childcare", "young children need care while parents work"),
    "park": ("Wattle Grove Park & Playground", "families and kids need green space"),
    "gym": ("FitGrove Gym", "working-age adults want somewhere to exercise"),
    "aged_care": ("Banksia Aged Care", "older residents need care close to home"),
    "bus": ("Wattle Grove Bus Interchange", "people without cars need public transport"),
    "community": ("Community Centre & Library", "a growing town needs a place to meet"),
    "supermarket": ("FreshCo Supermarket", "a bigger population needs another grocery store"),
    "gp": ("Wattle Grove GP Clinic", "more residents need local doctors"),
}
ANNUAL_DEATH = [(40, .0008), (60, .004), (70, .012), (80, .035), (90, .10), (200, .25)]


def gender_for(first: str, rnd: random.Random) -> str:
    if rnd.random() < .02:
        return "non-binary"
    return "female" if first in FEMALE else "male"


def enrich_life(r: dict[str, Any], rnd: random.Random) -> bool:
    changed = False
    if "gender" not in r:
        r["gender"] = gender_for(r["name"].split()[0], rnd)
        changed = True
    if "birthday" not in r:
        r["birthday"] = f"{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}"
        changed = True
    return changed


class Life:
    def __init__(self, town: Any):
        self.t = town
        town.store.db.executescript("""CREATE TABLE IF NOT EXISTS town_facilities(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, name TEXT, built TEXT,
                                       reason TEXT, by_res TEXT, lot INTEGER);""")
        town.store.commit()

    # ------------------------------------------------------------------ helpers
    def alive(self) -> list[dict[str, Any]]:
        return self.t.residents()

    def _save(self, r: dict[str, Any]) -> None:
        self.t._save(r)

    def _ev(self, rid: str, kind: str, text: str, **data: Any) -> dict[str, Any]:
        e = self.t.event(rid, kind, text, data=data)
        e["data"] = data
        return e

    def _new_id(self) -> str:
        n = max(int(r["id"][1:]) for r in self.t.all_residents()) + 1
        return f"r{n:03d}"

    def _person(self, rnd: random.Random, age: int, last: str, hh: int, kind: str, role: str, suburb: str, gender: str | None = None) -> dict[str, Any]:
        g = gender or rnd.choice(["female", "male"])
        first = rnd.choice(sorted(FEMALE)) if g == "female" else rnd.choice(MALE_NEW)
        inc_band = SUBURBS.get(suburb, "mid")
        p: dict[str, Any] = {"id": self._new_id(), "name": f"{first} {last}", "age": age, "gender": g, "birthday": f"{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}",
                             "suburb": suburb, "income": inc_band, "household": hh, "household_kind": kind, "role_in_household": role,
                             "needs": [] if age > 2 else [], "price_sensitivity": round(rnd.uniform(.3, .85), 2), "digital": round(rnd.uniform(.3, .95), 2),
                             "personality": rnd.choice(["careful researcher", "bargain hunter", "loyal and busy", "asks friends first", "brand-conscious"]),
                             "cover": None, "held_hospital_before": False}
        self._give_job(p, rnd)
        return p

    def _give_job(self, p: dict[str, Any], rnd: random.Random) -> None:
        if p["age"] < 18:
            p.update(occupation="School student" if p["age"] >= 5 else ("Toddler" if p["age"] >= 1 else "Baby"), workplace="school" if p["age"] >= 5 else "home",
                     employer="Wattle Grove Public School" if p["age"] >= 5 else "—", income_aud=0, vehicle="walks to school" if p["age"] >= 12 else "with a parent")
            return
        if p["age"] >= 67:
            p.update(occupation="Retired", workplace="home", employer="—", income_aud=int(rnd.uniform(28, 55) * 1000), vehicle=p.get("vehicle") or "Toyota Corolla")
            return
        band = p.get("income", "mid")
        job = rnd.choice(JOBS[band])
        place = JOB_PLACE.get(job, "towers")
        lo, hi = PAY.get(job, (50, 80))
        p.update(occupation=job, workplace=place, employer=rnd.choice(EMPLOYERS[place]), income_aud=int(rnd.uniform(lo, hi) * 1000))
        if not p.get("vehicle") or p["vehicle"] in ("walks to school", "with a parent"):
            p["vehicle"] = rnd.choice(["Toyota Corolla", "Mazda 3", "Hyundai i30", "bicycle", "bus & train"])

    # ------------------------------------------------------------------ one day of life
    def advance_day(self, d: date) -> list[dict[str, Any]]:
        st = self.t.store
        if (st.get_kv("life_date") or "") >= d.isoformat():
            return []
        st.set_kv("life_date", d.isoformat())
        rnd = random.Random(f"{self.t.seed}-life-{d.isoformat()}")
        out: list[dict[str, Any]] = []
        people = self.alive()
        mmdd = d.strftime("%m-%d")
        for r in people:
            if r.get("birthday") == mmdd:
                r["age"] += 1
                e = self._ev(r["id"], "birthday", f"{r['name']} turned {r['age']} 🎂", age=r["age"])
                if r["age"] == 18:
                    self._give_job(r, rnd)
                    e = self._ev(r["id"], "new_job", f"{r['name']} turned 18 and started as {r['occupation']} at {r['employer']}", age=18)
                elif r["age"] == 5:
                    self._give_job(r, rnd)
                elif r["age"] == 67 and r.get("occupation") not in ("Retired",):
                    old = r.get("occupation")
                    self._give_job(r, rnd)
                    e = self._ev(r["id"], "retired", f"{r['name']} retired after working as {old}", age=67)
                self._save(r)
                out.append({"event": e, "resident": r})
            q = next(v for a, v in ANNUAL_DEATH if r["age"] < a)
            if rnd.random() < q / 365 * ACCEL:
                r["deceased"] = d.isoformat()
                self._save(r)
                e = self._ev(r["id"], "death", f"{r['name']} passed away aged {r['age']} 🕊️", age=r["age"])
                out.append({"event": e, "removed": r["id"], "resident": r})
        # babies
        for hh, mem in self._households().items():
            adults = [m for m in mem if m["age"] >= 18]
            mom = [m for m in adults if m.get("gender") == "female" and 22 <= m["age"] <= 42]
            if len(adults) >= 2 and mom and rnd.random() < .06 / 365 * ACCEL:
                last = mom[0]["name"].split()[-1]
                baby = self._person(rnd, 0, last, hh, "family", "child", mom[0]["suburb"])
                baby["cover"] = dict(mom[0]["cover"]) if mom[0].get("cover") else None
                st.db.execute("INSERT INTO town_residents VALUES (?,?)", (baby["id"], json.dumps(baby)))
                for m in mem:
                    st.db.execute("INSERT INTO town_relations VALUES (?,?,?)", (baby["id"], m["id"], "parent" if m in adults else "sibling"))
                    if m["household_kind"] != "family":
                        m["household_kind"] = "family"
                        self._save(m)
                st.commit()
                e = self._ev(baby["id"], "birth", f"{baby['name']} was born to {' & '.join(a['name'].split()[0] for a in adults[:2])} 👶")
                out.append({"event": e, "resident": baby, "added": True})
        # a new household moves in
        if rnd.random() < .004 * ACCEL:
            hh = max(r["household"] for r in self.t.all_residents()) + 1
            kind = rnd.choice(["single", "couple", "family", "retirees"])
            last = rnd.choice(LAST)
            suburb = rnd.choice(["Wattle Grove North", "Wattle Grove South"])
            SUBURBS.setdefault(suburb, "mid")
            ages = {"single": [rnd.randint(22, 45)], "couple": [rnd.randint(25, 40)] * 2, "family": [rnd.randint(30, 44)] * 2 + [rnd.randint(1, 12) for _ in range(rnd.randint(1, 2))],
                    "retirees": [rnd.randint(66, 78)] * 2}[kind]
            newbies = []
            for i, a in enumerate(ages):
                role = "single" if kind == "single" else ("child" if kind == "family" and i >= 2 else ("partner" if kind in ("couple", "retirees") else "parent"))
                p = self._person(rnd, a + (rnd.randint(-3, 3) if i == 1 else 0), last, hh, kind, role, suburb, gender=("female" if i == 0 else "male") if i < 2 else None)
                st.db.execute("INSERT INTO town_residents VALUES (?,?)", (p["id"], json.dumps(p)))
                newbies.append(p)
            for i, a in enumerate(newbies):
                for b in newbies[i + 1:]:
                    st.db.execute("INSERT INTO town_relations VALUES (?,?,?)", (a["id"], b["id"], "family" if b["role_in_household"] == "child" else "partner"))
            st.commit()
            for p in newbies:
                e = self._ev(p["id"], "move_in", f"{p['name']} moved to {suburb} ({kind.replace('_', ' ')}) and works as {p['occupation']} 🚚")
                out.append({"event": e, "resident": p, "added": True})
        # friendships and partners
        adults = [r for r in self.alive() if r["age"] >= 18]
        rel = {(x["a"], x["b"]) for x in st.rows("SELECT a, b FROM town_relations")}
        known = lambda a, b: (a, b) in rel or (b, a) in rel  # noqa: E731
        for _ in range(2):
            a = rnd.choice(adults)
            mates = [b for b in adults if b["id"] != a["id"] and b.get("workplace") == a.get("workplace") and a.get("workplace") not in ("home", None) and not known(a["id"], b["id"])]
            if mates and rnd.random() < .5:
                b = rnd.choice(mates)
                st.db.execute("INSERT INTO town_relations VALUES (?,?,?)", (a["id"], b["id"], "friend"))
                st.commit()
                e = self._ev(a["id"], "friendship", f"{a['name']} and {b['name']} became friends at {a.get('employer') or 'work'} 🤝", other=b["id"])
                out.append({"event": e, "resident": a, "other": b["id"]})
        singles = [r for r in adults if r["household_kind"] in ("single", "share_house") and 22 <= r["age"] <= 55]
        if len(singles) >= 2 and rnd.random() < .02 * ACCEL / 10 * 3:
            a, b = rnd.sample(singles, 2)
            st.db.execute("INSERT INTO town_relations VALUES (?,?,?)", (a["id"], b["id"], "partner"))
            st.commit()
            e = self._ev(a["id"], "partner", f"{a['name']} and {b['name']} are now a couple 💕", other=b["id"])
            out.append({"event": e, "resident": a, "other": b["id"]})
        return out

    def _households(self) -> dict[int, list[dict[str, Any]]]:
        hh: dict[int, list[dict[str, Any]]] = {}
        for r in self.alive():
            hh.setdefault(r["household"], []).append(r)
        return hh

    # ------------------------------------------------------------------ the town council builds what the town needs
    def needs(self) -> dict[str, Any]:
        p = self.alive()
        built = {f["kind"] for f in self.facilities()}
        kids5 = sum(1 for r in p if r["age"] < 5)
        kids = sum(1 for r in p if r["age"] < 18)
        old = sum(1 for r in p if r["age"] >= 70)
        work = sum(1 for r in p if 20 <= r["age"] <= 45)
        nocar = sum(1 for r in p if r["age"] >= 18 and str(r.get("vehicle", "")).lower() in ("bicycle", "e-bike", "bus & train", "walks"))
        cands = []
        for k, cond in (("childcare", kids5 >= 3), ("park", kids >= 10), ("gym", work >= 25), ("aged_care", old >= 8), ("bus", nocar >= 15),
                        ("gp", len(p) >= 105), ("community", len(p) >= 110), ("supermarket", len(p) >= 120)):
            if cond and k not in built:
                cands.append({"kind": k, "name": FACILITIES[k][0], "why": FACILITIES[k][1]})
        return {"population": len(p), "children_under_5": kids5, "children": kids, "aged_70_plus": old, "adults_20_45": work,
                "adults_without_a_car": nocar, "already_built": sorted(built), "options": cands}

    def facilities(self) -> list[dict[str, Any]]:
        return self.t.store.rows("SELECT * FROM town_facilities ORDER BY id")

    def build(self, kind: str, reason: str, by: str, d: date) -> dict[str, Any]:
        if kind not in FACILITIES:
            return {"error": f"kind must be one of {list(FACILITIES)}"}
        if kind in {f["kind"] for f in self.facilities()}:
            return {"error": "already built"}
        lot = len(self.facilities())
        cur = self.t.store.db.execute("INSERT INTO town_facilities(kind,name,built,reason,by_res,lot) VALUES (?,?,?,?,?,?)",
                                      (kind, FACILITIES[kind][0], d.isoformat(), reason[:300], by, lot))
        self.t.store.commit()
        f = {"id": int(cur.lastrowid or 0), "kind": kind, "name": FACILITIES[kind][0], "built": d.isoformat(), "reason": reason[:300], "by_res": by, "lot": lot}
        self.t.event(by, "facility", f"The council approved {f['name']}: {reason[:160]} 🏗️", data={"facility": f})
        return f

    def mayor(self) -> dict[str, Any] | None:
        adults = [r for r in self.alive() if 35 <= r["age"] <= 75]
        return max(adults, key=lambda r: (r["personality"] == "careful researcher", r["age"])) if adults else None

    def rule_council(self, d: date) -> dict[str, Any] | None:
        n = self.needs()
        m = self.mayor()
        if not n["options"] or not m:
            return None
        o = n["options"][0]
        return self.build(o["kind"], o["why"], m["id"], d)
