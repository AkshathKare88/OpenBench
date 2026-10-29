"""Regression tests for OpenBench trust/safety behavior.

Run from the project folder:
    python -m unittest discover -s tests -v
Install dependencies first with: pip install -r requirements.txt
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import app as openbench


class OpenBenchTrustSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_openbench.db")
        self.db_patch = patch.object(openbench, "DB_PATH", self.db_path)
        self.db_patch.start()
        openbench.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        openbench.init_db()
        self.client = openbench.app.test_client()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def login_as(self, user_id):
        return self.client.post("/login", data={"user_id": str(user_id)}, follow_redirects=True)

    def create_booking(self, resource_id, user_id, start_at, end_at, status="pending"):
        conn = openbench.db()
        cur = conn.execute(
            """INSERT INTO bookings(resource_id,user_id,start_at,end_at,purpose,status,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (resource_id, user_id, start_at, end_at, "Regression test", status, openbench.now()),
        )
        booking_id = cur.lastrowid
        conn.commit()
        conn.close()
        return booking_id

    def test_student_cannot_open_audit_page(self):
        self.login_as(1)  # Aarav Demo Student
        response = self.client.get("/audit", follow_redirects=True)
        self.assertIn(b"different role", response.data.lower())

    def test_owner_cannot_approve_another_owners_booking(self):
        # Seeded demo data has one owner; create a second owner and resource.
        conn = openbench.db()
        conn.execute("INSERT INTO profiles(name, role) VALUES('Other Owner', 'owner')")
        other_owner_id = conn.execute("SELECT id FROM profiles WHERE name='Other Owner'").fetchone()[0]
        cur = conn.execute(
            """INSERT INTO resources(name,category,location,description,owner_id)
               VALUES('Other Owner Resource','Test','Lab','Test resource',?)""",
            (other_owner_id,),
        )
        resource_id = cur.lastrowid
        conn.commit()
        conn.close()
        booking_id = self.create_booking(resource_id, 1, "2099-01-01 10:00", "2099-01-01 11:00")
        self.login_as(3)  # Lab Manager Demo
        response = self.client.post(
            f"/booking/{booking_id}/decision",
            data={"decision": "approved"},
            follow_redirects=True,
        )
        self.assertIn(b"only review requests for resources you own", response.data.lower())
        conn = openbench.db()
        status = conn.execute("SELECT status FROM bookings WHERE id=?", (booking_id,)).fetchone()["status"]
        conn.close()
        self.assertEqual(status, "pending")

    def test_overlapping_pending_booking_cannot_be_approved_after_first_is_approved(self):
        start, end = "2099-01-01 10:00", "2099-01-01 11:00"
        first = self.create_booking(3, 1, start, end)
        second = self.create_booking(3, 2, start, end)
        self.login_as(3)
        self.client.post(f"/booking/{first}/decision", data={"decision": "approved"})
        response = self.client.post(
            f"/booking/{second}/decision",
            data={"decision": "approved"},
            follow_redirects=True,
        )
        self.assertIn(b"another booking now occupies that slot", response.data.lower())
        conn = openbench.db()
        statuses = [row["status"] for row in conn.execute(
            "SELECT status FROM bookings WHERE id IN (?,?) ORDER BY id", (first, second)
        ).fetchall()]
        conn.close()
        self.assertEqual(statuses, ["approved", "pending"])

    def test_owner_audit_does_not_show_other_owners_incidents(self):
        conn = openbench.db()
        conn.execute("INSERT INTO profiles(name, role) VALUES('Other Owner', 'owner')")
        other_owner_id = conn.execute("SELECT id FROM profiles WHERE name='Other Owner'").fetchone()[0]
        cur = conn.execute(
            """INSERT INTO resources(name,category,location,description,owner_id)
               VALUES('Private Resource','Test','Lab','Test resource',?)""",
            (other_owner_id,),
        )
        resource_id = cur.lastrowid
        cur = conn.execute(
            """INSERT INTO bookings(resource_id,user_id,start_at,end_at,purpose,status,created_at)
               VALUES(?,?,?,?,?,'returned',?)""",
            (resource_id, 1, "2099-01-01 10:00", "2099-01-01 11:00", "Test", openbench.now()),
        )
        booking_id = cur.lastrowid
        conn.execute(
            """INSERT INTO incidents(booking_id,reporter_id,incident_type,description,created_at)
               VALUES(?,1,'damage','Private incident description',?)""",
            (booking_id, openbench.now()),
        )
        conn.commit()
        conn.close()
        self.login_as(3)
        response = self.client.get("/audit")
        self.assertNotIn(b"Private incident description", response.data)

    def test_resolving_one_incident_does_not_clear_another_open_damage_incident(self):
        conn = openbench.db()
        booking_id = self.create_booking(3, 1, "2099-01-01 10:00", "2099-01-01 11:00", "returned")
        cur = conn.execute(
            """INSERT INTO incidents(booking_id,reporter_id,incident_type,description,created_at)
               VALUES(?,1,'damage','First incident',?)""", (booking_id, openbench.now())
        )
        first_incident = cur.lastrowid
        conn.execute(
            """INSERT INTO incidents(booking_id,reporter_id,incident_type,description,created_at)
               VALUES(?,1,'damage','Second incident',?)""", (booking_id, openbench.now())
        )
        conn.execute("UPDATE resources SET available=0, condition_status='Needs review' WHERE id=3")
        conn.commit()
        conn.close()
        self.login_as(3)
        self.client.post(
            f"/incident/{first_incident}/resolve",
            data={"resolution": "Reviewed; second report remains open"},
            follow_redirects=True,
        )
        conn = openbench.db()
        resource = conn.execute("SELECT available, condition_status FROM resources WHERE id=3").fetchone()
        conn.close()
        self.assertEqual(resource["available"], 0)
        self.assertEqual(resource["condition_status"], "Needs review")


if __name__ == "__main__":
    unittest.main()
