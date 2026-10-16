"""
Generate a balanced MiroFish seed document of named consumers.

Output:
  - mirofish_seed_stride_studio_v3.md : upload to MiroFish as the reality seed
  - personas.csv                       : the same people as a table (later a dbt seed / dim_persona)

Design: 4 age bands x 2 genders x N people per cell. Inside every cell, fitness level,
money attitude, schedule and family type are rotated so no segment is skewed.
A fixed random seed makes the output identical every time it is run.

Usage: python generate_seed.py --per-cell 6
"""
import argparse
import csv
import random

RANDOM_SEED = 42

AGE_BANDS = [(30, 34), (35, 39), (40, 44), (45, 49)]
GENDERS = ["male", "female"]

FITNESS = ["never exercises", "used to be active", "works out sometimes", "very active"]
MONEY = ["careful with money", "average spender", "spends freely on health"]
SCHEDULES = [
    ("office worker with a 9-to-5 schedule", "office"),
    ("shift worker with rotating hours", "shift"),
    ("remote worker at home", "remote"),
    ("small business owner with long days", "business_owner"),
]
FAMILIES = [
    ("single with no kids", "single_no_kids"),
    ("married with no kids", "couple_no_kids"),
    ("parent of young children", "parent_young_kids"),
    ("parent of teenagers", "parent_teens"),
]
JOBS = {
    "office": ["accountant", "HR specialist", "insurance agent", "marketing coordinator", "bank analyst", "school administrator"],
    "shift": ["ER nurse", "firefighter", "warehouse supervisor", "pharmacist", "police dispatcher", "factory technician"],
    "remote": ["software developer", "customer-service lead", "graphic designer", "IT consultant", "medical billing specialist", "online tutor"],
    "business_owner": ["restaurant owner", "electrician who runs a small shop", "salon owner", "landscaping business owner", "bakery owner", "auto repair shop owner"],
}

MALE_FIRST = ["Marcus", "Kevin", "Tyler", "Daniel", "Brian", "Andre", "James", "Carlos", "Michael", "Robert",
              "Greg", "Anthony", "Jason", "Derek", "Luis", "Samuel", "Eric", "Omar", "Patrick", "Victor",
              "Nathan", "Ray", "Steven", "Hector"]
FEMALE_FIRST = ["Jasmine", "Emily", "Rachel", "Sarah", "Priya", "Lauren", "Dana", "Monica", "Angela", "Karen",
                "Denise", "Linda", "Tanya", "Maria", "Nicole", "Grace", "Keisha", "Holly", "Sofia", "Wendy",
                "Brenda", "Aisha", "Megan", "Teresa"]
LAST = ["Reed", "Patel", "Brooks", "Carter", "Nguyen", "Kim", "Ortiz", "Walsh", "Thompson", "Mitchell",
        "Shah", "Davis", "Wilson", "Rivera", "Chen", "Foster", "Hughes", "Hayes", "Sullivan", "Russo",
        "Lewis", "Howard", "Parker", "Bennett", "Coleman", "Diaz", "Edwards", "Fisher", "Garcia", "Hall",
        "Jenkins", "Lopez", "Morgan", "Perry", "Ramirez", "Sanders", "Torres", "Ward", "Young", "Price",
        "Bailey", "Cruz", "Flores", "Gray", "Hill", "James", "King", "Long"]


def build_people(per_cell: int) -> list[dict]:
    rng = random.Random(RANDOM_SEED)
    males, females, lasts = MALE_FIRST[:], FEMALE_FIRST[:], LAST[:]
    rng.shuffle(males); rng.shuffle(females); rng.shuffle(lasts)

    people, n = [], 0
    for lo, hi in AGE_BANDS:
        for g in GENDERS:
            for i in range(per_cell):
                # rotate attributes inside the cell so each cell gets a balanced mix
                fitness = FITNESS[(i + n) % len(FITNESS)]
                money = MONEY[(i + n) % len(MONEY)]
                sched_text, sched_key = SCHEDULES[(i + n // 2) % len(SCHEDULES)]
                fam_text, fam_key = FAMILIES[(i * 3 + n) % len(FAMILIES)]
                job = rng.choice(JOBS[sched_key])
                first = (males if g == "male" else females).pop()
                last = lasts[len(people) % len(lasts)]
                people.append({
                    "persona_id": f"P{len(people) + 1:03d}",
                    "full_name": f"{first} {last}",
                    "age": rng.randint(lo, hi),
                    "age_band": f"{lo}-{hi}",
                    "gender": g,
                    "job": job,
                    "schedule": sched_key,
                    "family": fam_key,
                    "fitness_level": fitness,
                    "money_attitude": money,
                    "_sched_text": sched_text,
                    "_fam_text": fam_text,
                })
            n += 1
    return people


ADS = """## The four ads each person sees

Ad A, Free Trial: "Try Stride Studio free for 7 days. Unlimited 20-minute home workouts. After the trial it is $14.99 a month, and you can cancel anytime." Button: Start Free Trial.

Ad B, Real Members: "50,000 people stopped paying for a gym they never used. 'I've done more workouts in 2 months than in 2 years of gym membership.'" Button: Join Them.

Ad C, 20 Minutes for You: "The kids are asleep. You have 20 minutes. No commute, no crowds, no equipment. Just a workout that fits the life you actually have." Button: Make Time for You.

Ad D, 30-Day Challenge: "The 30-Day Reset starts Monday. Join by Sunday to get a day-by-day plan and a progress tracker. Thousands are starting together." Button: Join the Challenge.

## How each person responds

Each person reacts to all four ads, in their own voice, based on their age, job, family, fitness and money habits. Every reaction starts with this exact line, then one or two natural sentences:

[Ad X] click: yes or no | trial: yes or no | main reason: price, time, trust, motivation, or fit

People can reply to each other's reactions, agree, disagree, or change their minds.
"""


def write_markdown(people: list[dict], path: str) -> None:
    total = len(people)
    lines = [
        f"# Stride Studio Ad Test: {total} Consumers React to Four Ads",
        "",
        "Stride Studio is a fictional home-workout app. It offers 20-minute guided workouts at home "
        "with no equipment. It costs $14.99 a month after a 7-day free trial, and members can cancel anytime.",
        "",
        f"This simulation takes place in the United States, on US Eastern time. The only people in it are "
        f"the {total} consumers listed below. Every post and comment comes from one of these {total} people. "
        "Stride Studio, the ads themselves, and any other company or media account do not post.",
        "",
        f"## The {total} consumers",
        "",
    ]
    current = None
    for p in people:
        group = (p["age_band"], p["gender"])
        if group != current:
            if current is not None:
                lines.append("")
            label = "men" if p["gender"] == "male" else "women"
            lines.append(f"Ages {p['age_band'].replace('-', '–')}, {label}:")
            current = group
        lines.append(
            f"- {p['full_name']}, {p['age']}, {p['gender']}, {p['job']}, {p['_sched_text']}, "
            f"{p['_fam_text']}, {p['fitness_level']}, {p['money_attitude']}."
        )
    lines += ["", ADS]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_csv(people: list[dict], path: str) -> None:
    cols = ["persona_id", "full_name", "age", "age_band", "gender", "job",
            "schedule", "family", "fitness_level", "money_attitude"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(people)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=6, help="people per age band x gender (6 -> 48 total)")
    args = ap.parse_args()
    people = build_people(args.per_cell)
    write_markdown(people, "mirofish_seed_stride_studio_v3.md")
    write_csv(people, "personas.csv")
    print(f"Wrote {len(people)} personas")
