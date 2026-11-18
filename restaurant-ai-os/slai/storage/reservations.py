
from slai.storage.database import get_connection, init_database

class ReservationService:
    def __init__(self):
        init_database()

    def is_available(self, date, time, party_size):
        if not date or not time or party_size <= 0:
            return False

        suitable_tables = self._suitable_tables(party_size)

        if not suitable_tables:
            return False

        with get_connection() as connection:
            for table in suitable_tables:
                result = connection.execute(
                    """
                    SELECT 1
                    FROM reservations
                    WHERE table_id = ?
                      AND date = ?
                      AND time = ?
                      AND status IN ('confirmed', 'seated')
                    """,
                    (table["id"], date, time),
                ).fetchone()

                if result is None:
                    return True

        return False

    def create_reservation(self, guest_id, date, time, party_size, occasion=""):
        if not self.is_available(date, time, party_size):
            return None

        table_id = self._find_free_table(date, time, party_size)

        if table_id is None:
            return None

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reservations (
                    guest_id, table_id, date, time, party_size, occasion, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
                """,
                (guest_id, table_id, date, time, party_size, occasion),
            )
            reservation_id = cursor.lastrowid

        return self.get_reservation(reservation_id)

    def get_reservation(self, reservation_id):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM reservations WHERE id = ?",
                (reservation_id,),
            ).fetchone()

        return dict(row) if row else None

    def _suitable_tables(self, party_size):
        return [
            {"id": 1, "capacity": 2},
            {"id": 2, "capacity": 4},
            {"id": 3, "capacity": 4},
            {"id": 4, "capacity": 6},
            {"id": 5, "capacity": 8},
        ]

    def _find_free_table(self, date, time, party_size):
        suitable_tables = self._suitable_tables(party_size)

        with get_connection() as connection:
            for table in suitable_tables:
                result = connection.execute(
                    """
                    SELECT 1
                    FROM reservations
                    WHERE table_id = ?
                      AND date = ?
                      AND time = ?
                      AND status IN ('confirmed', 'seated')
                    """,
                    (table["id"], date, time),
                ).fetchone()

                if result is None:
                    return table["id"]

        return None