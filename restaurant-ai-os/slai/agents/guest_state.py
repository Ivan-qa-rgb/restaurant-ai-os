from dataclasses import dataclass, field, asdict


@dataclass
class GuestState:
    guest_id: str = ""
    name: str = ""
    phone: str = ""
    party_size: int = 0
    date: str = ""
    time: str = ""
    occasion: str = ""
    notes: str = ""
    missing_fields: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
