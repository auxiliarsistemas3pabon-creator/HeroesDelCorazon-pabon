from unittest.mock import patch

from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation
from .helpers import CRITERIA, create_user


class MonthRolloverTests(APITestCase):
    """The monthly quota follows the calendar month in the project time zone (America/Bogota)."""

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        Evaluation.objects.update(closes_on=None, monthly_limit=3)  # these tests travel through several months: no deadline
        self.me = create_user("me.demo", User.Role.COLLABORATOR)
        self.team = [create_user(f"c{i}.demo", User.Role.COLLABORATOR) for i in range(6)]

    def at(self, year, month, day, hour, minute):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return patch("django.utils.timezone.now", return_value=datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/Bogota")))

    def send(self, personal):
        self.client.force_authenticate(self.me)
        body = {"personal": personal.pk, "answers": [{"criterion": c, "score": 4} for c in CRITERIA]}
        return self.client.post("/api/v1/questions/", body, format="json")

    def quota(self):
        self.client.force_authenticate(self.me)
        return self.client.get("/api/v1/questions/quota/").data

    def test_quota_resets_on_the_first_day_of_the_next_month(self):
        with self.at(2026, 10, 15, 10, 0):
            for p in self.team[:3]:
                self.assertEqual(self.send(p).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)
            self.assertEqual(self.quota()["used"], 3)

        with self.at(2026, 11, 2, 9, 0):  # next month: a clean quota, and the same colleagues can be scored again
            self.assertEqual(self.quota()["used"], 0)
            self.assertEqual(self.quota()["personal"], [])
            for p in self.team[:3]:
                self.assertEqual(self.send(p).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)
            self.assertEqual(self.quota()["used"], 3)

        with self.at(2026, 10, 20, 8, 0):  # going back to October still shows only October's three
            self.assertEqual(self.quota()["used"], 3)

    def test_month_boundary_uses_local_time_not_utc(self):
        # Oct 31 22:00 in Bogota is already Nov 1 03:00 UTC: it must still count as October.
        with self.at(2026, 10, 31, 22, 0):
            self.assertEqual(self.send(self.team[0]).status_code, 201)
        with self.at(2026, 10, 31, 23, 59):
            self.assertEqual(self.quota()["used"], 1)
        with self.at(2026, 11, 1, 0, 0):
            self.assertEqual(self.quota()["used"], 0)
        with self.at(2026, 11, 1, 0, 1):
            self.assertEqual(self.send(self.team[0]).status_code, 201)  # new month, same colleague allowed

    def test_partial_quota_leaves_the_rest_for_the_same_month(self):
        with self.at(2026, 10, 5, 10, 0):
            self.send(self.team[0])
            self.assertEqual(self.quota()["used"], 1)
            self.assertEqual(self.send(self.team[1]).status_code, 201)
            self.assertEqual(self.send(self.team[2]).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)

    def test_each_collaborator_has_their_own_quota(self):
        other = self.team[5]
        with self.at(2026, 10, 5, 10, 0):
            for p in self.team[:3]:
                self.send(p)
            self.client.force_authenticate(other)
            body = {"personal": self.team[0].pk, "answers": [{"criterion": c, "score": 5} for c in CRITERIA]}
            self.assertEqual(self.client.post("/api/v1/questions/", body, format="json").status_code, 201)
            self.assertEqual(self.client.get("/api/v1/questions/quota/").data["used"], 1)
