from pathlib import Path
import re


class TicketManager:

    def __init__(self):
        self.tickets = {}
        self.load_tickets()

        self.persona_ticket_map = {
            "backend_intern_nodejs": ["FLOW-INTERN-001"],
            "junior_backend_python": ["FLOW-JR-001", "FLOW-JR-002"],
            "junior_frontend_react": ["FLOW-FE-001", "FLOW-FE-002"],
            "senior_backend_nodejs": ["FLOW-SR-001"],
            "senior_devops": ["FLOW-INFRA-001"],
            "junior_fullstack": ["FLOW-FS-001", "FLOW-FS-002"]
        }

    def load_tickets(self):

        path = Path(__file__).resolve().parents[2] / "agent_data" / "starter_tickets.md"

        if not path.exists():
            return

        content = path.read_text()

        tickets = re.split(r"###\s+", content)

        for block in tickets:

            match = re.search(r"(FLOW-[A-Z]+-\d+)", block)

            if not match:
                continue

            ticket_id = match.group(1)

            self.tickets[ticket_id] = {
                "ticket_id": ticket_id,
                "content": block.strip()
            }

    def assign_ticket(self, persona):

        ticket_ids = self.persona_ticket_map.get(persona, [])

        assigned = []

        for tid in ticket_ids:

            if tid in self.tickets:
                assigned.append(self.tickets[tid])

        return assigned
