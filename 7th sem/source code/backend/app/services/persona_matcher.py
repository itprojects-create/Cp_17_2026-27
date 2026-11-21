from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
import re


# Path to persona dataset
PERSONA_FILE = Path(__file__).resolve().parents[2] / "agent_data" / "employee_personas.md"




@dataclass
class Persona:
    name: str
    role: str
    experience_level: str
    tech_stack: List[str]
    persona_key: str


FALLBACK_PERSONA = Persona(
    name="Backend Junior Python",
    role="backend",
    experience_level="junior",
    tech_stack=["python"],
    persona_key="BE-JR-PY",
)


# -----------------------------
# Load Personas from Markdown
# -----------------------------
def load_personas() -> List[Persona]:
    personas = []

    if not PERSONA_FILE.exists():
        raise FileNotFoundError(
            f"Persona file not found at {PERSONA_FILE}"
        )

    content = PERSONA_FILE.read_text(encoding="utf-8")

    pattern = r"### (.*?)\nRole: (.*?)\nExperience: (.*?)\nTech Stack: (.*?)\n"

    matches = re.findall(pattern, content)

    for name, role, exp, tech in matches:
        persona = Persona(
            name=name.strip(),
            role=role.strip(),
            experience_level=exp.strip(),
            tech_stack=[t.strip().lower() for t in tech.split(",")],
            persona_key=name.lower().replace(" ", "_"),
        )

        personas.append(persona)

    return personas


# -----------------------------
# Extract profile from intro
# -----------------------------
def extract_user_profile(message: str):

    text = message.lower()

    role = None
    experience = None
    tech_stack = []

    # Improved role detection
    if any(k in text for k in ["backend", "back-end", "server-side"]):
        role = "backend"
    elif any(k in text for k in ["frontend", "front-end", "client-side"]):
        role = "frontend"
    elif any(k in text for k in ["devops", "sre", "infrastructure"]):
        role = "devops"
    elif any(k in text for k in ["full-stack", "fullstack", "full stack", "mern", "mean"]):
        role = "fullstack"
    elif any(re.search(r"\b" + k + r"\b", text) for k in ["ml", "ai"]) or any(k in text for k in ["machine learning", "data science"]):
        role = "ml"

    # Improved experience detection
    if any(k in text for k in ["intern", "apprentice", "fresher", "beginner", "novice"]):
        experience = "intern"
    elif any(k in text for k in ["junior", "entry", "associate"]):
        experience = "junior"
    elif any(k in text for k in ["senior", "lead", "architect", "staff", "principal"]):
        experience = "senior"

    # Expanded tech keywords
    tech_map = {
        "node": "node.js",
        "node.js": "node.js",
        "python": "python",
        "django": "python",
        "fastapi": "fastapi",
        "flask": "python",
        "pytorch": "pytorch",
        "tensorflow": "tensorflow",
        "react": "react",
        "angular": "angular",
        "vue": "vue",
        "next.js": "next.js",
        "nextjs": "next.js",
        "docker": "docker",
        "k8s": "kubernetes",
        "kubernetes": "kubernetes",
        "aws": "aws",
        "typescript": "typescript",
        "javascript": "javascript",
        "mongodb": "mongodb",
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "express": "express",
    }

    for key, val in tech_map.items():
        if key in text:
            if val not in tech_stack:
                tech_stack.append(val)

    # Handle acronyms
    if "mern" in text:
        for t in ["mongodb", "express", "react", "node.js"]:
            if t not in tech_stack:
                tech_stack.append(t)
    if "mean" in text:
        for t in ["mongodb", "express", "angular", "node.js"]:
            if t not in tech_stack:
                tech_stack.append(t)

    return {
        "role": role,
        "experience_level": experience,
        "level": experience,
        "tech_stack": tech_stack,
    }


# -----------------------------
# Persona Matching Logic
# -----------------------------
def match_persona(user_profile, personas: List[Persona]) -> Optional[Persona]:
    signal_count = sum(
        1 for key in ["role", "experience_level", "tech_stack"]
        if user_profile.get(key)
    )

    if signal_count < 2:
        return FALLBACK_PERSONA

    best_match = None
    best_score = -1

    for persona in personas:
        score = 0

        # Role match
        user_role = (user_profile.get("role") or "").replace("-", "").lower()
        persona_role = (persona.role or "").replace("-", "").lower()
        if user_role and (user_role in persona_role or persona_role in user_role):
            score += 3

        # Experience match
        user_exp = (user_profile.get("experience_level") or "").lower()
        if user_exp and user_exp in persona.experience_level.lower():
            score += 1

        # Tech overlap outweighs seniority: a junior Node.js developer is closer to the
        # Node.js persona than to a junior Python one.
        overlap = set(user_profile.get("tech_stack", [])) & set(persona.tech_stack)
        score += 2 * len(overlap)

        if score > best_score:
            best_score = score
            best_match = persona

    if best_match is None or best_score <= 0:
        return FALLBACK_PERSONA

    return best_match


# -----------------------------
# Main Function
# -----------------------------
def identify_persona(user_message: str) -> Optional[Persona]:

    personas = load_personas()

    profile = extract_user_profile(user_message)

    persona = match_persona(profile, personas)

    return persona


# -----------------------------
# Test Runner
# -----------------------------
if __name__ == "__main__":

    intro = "Hi I am Monica, backend intern working with Node.js"

    persona = identify_persona(intro)

    if persona:
        print("Matched Persona:")
        print(persona)
    else:
        print("No matching persona found.")
