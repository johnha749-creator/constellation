"""A tiny, hand-curated drug knowledge base for the demo.

This is NOT clinical decision support. A real system would normalize drugs with
RxNorm and use a licensed interaction database (e.g. First Databank, Medi-Span).
Add entries here to teach the conflict checker new rules.
"""
from __future__ import annotations

import re

SEVERITY_RANK = {"low": 1, "moderate": 2, "high": 3}

# Drug name as it appears in a med list (lowercase) -> therapeutic classes.
DRUGS: dict[str, set[str]] = {
    # antibiotics
    "amoxicillin": {"penicillin"},
    "ampicillin": {"penicillin"},
    "piperacillin": {"penicillin"},
    "cephalexin": {"cephalosporin"},
    "ceftriaxone": {"cephalosporin"},
    "sulfamethoxazole": {"sulfonamide_antibiotic"},
    "clarithromycin": {"macrolide", "strong_cyp3a4_inhibitor"},
    "azithromycin": {"macrolide"},
    # pain
    "ibuprofen": {"nsaid"},
    "naproxen": {"nsaid"},
    "aspirin": {"nsaid", "antiplatelet"},
    "tramadol": {"opioid", "serotonergic"},
    "acetaminophen": {"analgesic"},
    # heart and blood pressure
    "lisinopril": {"ace_inhibitor"},
    "enalapril": {"ace_inhibitor"},
    "losartan": {"arb"},
    "spironolactone": {"potassium_sparing_diuretic"},
    "amlodipine": {"calcium_channel_blocker"},
    "metoprolol": {"beta_blocker"},
    "atorvastatin": {"statin"},
    "simvastatin": {"statin", "cyp3a4_statin"},
    "warfarin": {"anticoagulant"},
    "apixaban": {"anticoagulant"},
    "rivaroxaban": {"anticoagulant"},
    "clopidogrel": {"antiplatelet"},
    "nitroglycerin": {"nitrate"},
    "sildenafil": {"pde5_inhibitor"},
    # other
    "metformin": {"biguanide"},
    "sertraline": {"ssri", "serotonergic"},
    "fluoxetine": {"ssri", "serotonergic"},
    "levothyroxine": {"thyroid_hormone"},
    "omeprazole": {"ppi"},
    "albuterol": {"beta_agonist"},
}

CLASS_LABELS = {
    "penicillin": "penicillin-class antibiotic",
    "cephalosporin": "cephalosporin antibiotic",
    "sulfonamide_antibiotic": "sulfa antibiotic",
    "nsaid": "NSAID",
    "antiplatelet": "antiplatelet",
    "ace_inhibitor": "ACE inhibitor",
    "arb": "ARB",
    "anticoagulant": "anticoagulant",
    "ssri": "SSRI",
    "statin": "statin",
    "beta_blocker": "beta blocker",
    "ppi": "proton pump inhibitor",
}

# Allergy wording -> {drug class it can react with: severity}.
ALLERGY_GROUPS: dict[str, dict[str, str]] = {
    # ~1-2% of penicillin-allergic patients also react to cephalosporins.
    "penicillin": {"penicillin": "high", "cephalosporin": "low"},
    "sulfa": {"sulfonamide_antibiotic": "high"},
    "sulfonamide": {"sulfonamide_antibiotic": "high"},
    "nsaid": {"nsaid": "high"},
}

# Classes where taking two *different* drugs usually means a duplicated prescription.
DUPLICATE_CLASSES = {
    "anticoagulant": "high",
    "ace_inhibitor": "moderate",
    "arb": "moderate",
    "nsaid": "moderate",
    "ssri": "moderate",
    "statin": "moderate",
    "beta_blocker": "moderate",
    "ppi": "low",
}

# (class A, class B, severity, why it matters)
INTERACTIONS = [
    ("anticoagulant", "nsaid", "high",
     "Major bleeding risk: NSAIDs irritate the stomach and thin the blood on top of an anticoagulant."),
    ("anticoagulant", "antiplatelet", "high",
     "Major bleeding risk when an anticoagulant is combined with an antiplatelet."),
    ("ssri", "serotonergic", "high",
     "Risk of serotonin syndrome (and seizures with tramadol)."),
    ("nitrate", "pde5_inhibitor", "high",
     "Can cause a sudden, severe drop in blood pressure."),
    ("cyp3a4_statin", "strong_cyp3a4_inhibitor", "high",
     "Sharply raises statin levels, risking muscle breakdown (rhabdomyolysis)."),
    ("ace_inhibitor", "potassium_sparing_diuretic", "moderate",
     "Risk of dangerously high potassium (hyperkalemia)."),
    ("ace_inhibitor", "nsaid", "moderate",
     "NSAIDs blunt blood-pressure control and can injure the kidneys alongside ACE inhibitors."),
    ("ace_inhibitor", "arb", "moderate",
     "Dual RAAS blockade raises the risk of kidney injury and high potassium."),
]

# (keyword in the condition, drug class, severity, why it matters)
CONDITION_RULES = [
    ("kidney disease", "nsaid", "moderate", "NSAIDs can worsen kidney function in chronic kidney disease."),
    ("peptic ulcer", "nsaid", "high", "NSAIDs can make ulcers bleed."),
    ("peptic ulcer", "anticoagulant", "moderate", "Anticoagulants raise the risk of ulcer bleeding."),
]


def label(drug_class: str) -> str:
    return CLASS_LABELS.get(drug_class, drug_class.replace("_", " "))


def with_article(text: str) -> str:
    vowel_sound = text[0].lower() in "aeiou" or text.split()[0] in {"NSAID", "SSRI"}
    return f"{'an' if vowel_sound else 'a'} {text}"


def normalize_drug(text: str) -> str | None:
    """Map free-text like 'Amoxicillin 875 mg' to a known drug key."""
    text = text.lower()
    for name in sorted(DRUGS, key=len, reverse=True):
        if name in text:
            return name
    return None


def parse_dose_mg(dosage: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*mg\b", dosage.lower())
    return float(match.group(1)) if match else None


def allergy_risk(allergen: str, drug: str) -> tuple[str, str | None] | None:
    """(severity, matching class) if `drug` may trigger an allergy recorded as `allergen`.

    The class is None when the allergy names the drug itself.
    """
    allergen = allergen.lower()
    if drug in allergen:
        return "high", None
    drug_classes = DRUGS.get(drug, set())
    # Allergy recorded as a specific drug: treat its whole class as suspect.
    for name, classes in DRUGS.items():
        if name in allergen and (shared := classes & drug_classes):
            return "high", sorted(shared)[0]
    for term, reactions in ALLERGY_GROUPS.items():
        if term in allergen:
            for drug_class, severity in reactions.items():
                if drug_class in drug_classes:
                    return severity, drug_class
    return None


def duplicate_class(drug_a: str, drug_b: str) -> tuple[str, str] | None:
    """(severity, shared class) if two different drugs duplicate the same therapy."""
    if drug_a == drug_b:
        return None
    shared = DRUGS.get(drug_a, set()) & DRUGS.get(drug_b, set()) & DUPLICATE_CLASSES.keys()
    if not shared:
        return None
    drug_class = max(shared, key=lambda c: SEVERITY_RANK[DUPLICATE_CLASSES[c]])
    return DUPLICATE_CLASSES[drug_class], drug_class


def interaction(drug_a: str, drug_b: str) -> tuple[str, str] | None:
    """(severity, message) for the most severe known interaction between two drugs."""
    classes_a, classes_b = DRUGS.get(drug_a, set()), DRUGS.get(drug_b, set())
    best = None
    for x, y, severity, message in INTERACTIONS:
        if (x in classes_a and y in classes_b) or (y in classes_a and x in classes_b):
            if best is None or SEVERITY_RANK[severity] > SEVERITY_RANK[best[0]]:
                best = (severity, message)
    return best


def condition_risk(condition: str, drug: str) -> tuple[str, str] | None:
    """(severity, message) if `drug` is risky for a patient with `condition`."""
    condition = condition.lower()
    classes = DRUGS.get(drug, set())
    for keyword, drug_class, severity, message in CONDITION_RULES:
        if keyword in condition and drug_class in classes:
            return severity, message
    return None
