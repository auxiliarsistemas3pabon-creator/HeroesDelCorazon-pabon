from unittest.mock import patch

from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation
from .helpers import CRITERIA, create_user


class DashboardDateFilterTests(APITestCase):
    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        self.a = create_user("a.demo", User.Role.COLLABORATOR)
        self.b = create_user("b.demo", User.Role.COLLABORATOR)

    def send_on(self, day, collaborator, personal):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, day, 12, 0, tzinfo=ZoneInfo("America/Bogota"))):
            self.client.force_authenticate(collaborator)
            body = {"personal": personal.pk, "answers": [{"criterion": c, "score": 4} for c in CRITERIA]}
            self.assertEqual(self.client.post("/api/v1/questions/", body, format="json").status_code, 201)

    def test_date_range_limits_questions_and_staff(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        self.send_on(5, self.a, self.b)
        self.send_on(20, self.b, self.a)
        self.client.force_authenticate(self.boss)

        def get(query=""):
            return self.client.get(f"/api/v1/questions/dashboard/{query}").data

        self.assertEqual(get()["evaluated"], 2)
        self.assertEqual(get("?date_from=2026-10-10")["evaluated"], 1)
        self.assertEqual(get("?date_to=2026-10-10")["evaluated"], 1)
        self.assertEqual(get("?date_from=2026-10-05&date_to=2026-10-20")["evaluated"], 2)  # both ends inclusive
        self.assertEqual(get("?date_from=2026-11-01")["evaluated"], 0)
        # staff is filtered by the registration date
        User.objects.update(date_joined=datetime(2026, 9, 1, 12, 0, tzinfo=ZoneInfo("America/Bogota")))
        self.assertEqual(get()["staff"], 2)
        self.assertEqual(get("?date_from=2026-09-01&date_to=2026-09-30")["staff"], 2)
        self.assertEqual(get("?date_from=2026-10-01")["staff"], 0)
        self.assertEqual(get("?date_from=no-es-fecha")["evaluated"], 2)  # invalid dates are ignored
        self.assertEqual(get("?date_from=2026-13-45")["evaluated"], 2)

    def test_category_averages_by_person(self):
        self.send_on(5, self.a, self.b)
        self.client.force_authenticate(self.boss)
        url = "/api/v1/questions/category-averages/"
        data = self.client.get(f"{url}?personal={self.b.pk}").data
        self.assertEqual(data["average"], 4.0)
        self.assertTrue(all(c["average"] == 4.0 for c in data["by_category"]))
        self.assertIsNone(self.client.get(f"{url}?personal={self.a.pk}").data["average"])
        self.client.force_authenticate(self.a)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_stats_for_the_boss_respect_the_range(self):
        self.send_on(5, self.a, self.b)
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.get("/api/v1/questions/stats/").data["evaluated"], 1)
        self.assertEqual(self.client.get("/api/v1/questions/stats/?date_from=2026-10-10").data["evaluated"], 0)
