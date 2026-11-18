from slai.agents.qualifier import QualifierAgent

class GuestIntakeAgent:
    name = "guest_intake"

    def __init__(self, qualifier=None):
        self.qualifier = qualifier or QualifierAgent()

    def respond(self, state):
        labels = {
            "party_size": "количество гостей",
            "date": "дату",
            "time": "время",
        }
        missing = [
            labels[field]
            for field in state.missing_fields
            if field in labels
        ]

        if missing:
            return "Уточните, пожалуйста: " + ", ".join(missing) + "."

        return (
            f"Понял: {state.party_size} гостей, "
            f"{state.date} в {state.time}. "
            "Бронь пока не создана."
        )

    def run(self, prompt):
        state = self.qualifier.extract(prompt)
        return self.respond(state)
