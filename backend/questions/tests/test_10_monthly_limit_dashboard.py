from django.utils import timezone
from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation, Question
from .helpers import CRITERIA, create_user


class MonthlyLimitAndDashboardTests(APITestCase):
    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        self.team = [create_user(f"c{i}.demo", User.Role.COLLABORATOR) for i in range(5)]
        self.cardio = create_user("ines.demo", User.Role.COLLABORATOR, area="Cardiology")

    def send(self, collaborator, personal):
        self.client.force_authenticate(collaborator)
        body = {"personal": personal.pk, "answers": [{"criterion": c, "score": 4} for c in CRITERIA]}
        return self.client.post("/api/v1/questions/", body, format="json")

    def test_a_collaborator_can_score_only_3_colleagues_per_month(self):
        me, others = self.team[0], self.team[1:]
        for p in others[:3]:
            self.assertEqual(self.send(me, p).status_code, 201)
        self.assertEqual(self.send(me, others[3]).status_code, 400)  # 4th one
        quota = self.client.get("/api/v1/questions/quota/").data
        self.assertEqual((quota["limit"], quota["used"]), (3, 3))
        self.assertEqual(sorted(quota["personal"]), sorted(p.pk for p in others[:3]))

    def test_boss_sets_the_monthly_limit_from_1_to_30(self):
        url = "/api/v1/questions/settings/"
        self.client.force_authenticate(self.team[0])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.put(url, {"monthly_limit": 2}, format="json").status_code, 403)

        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.get(url).data, {"monthly_limit": 3})
        for bad in (0, -1, 31, 51, "abc", None):  # nothing above 30 is accepted
            self.assertEqual(self.client.put(url, {"monthly_limit": bad}, format="json").status_code, 400)
        self.assertEqual(self.client.get(url).data, {"monthly_limit": 3})

        self.assertEqual(self.client.put(url, {"monthly_limit": 2}, format="json").data, {"monthly_limit": 2})
        me, others = self.team[0], self.team[1:]
        self.assertEqual(self.send(me, others[0]).status_code, 201)
        self.assertEqual(self.send(me, others[1]).status_code, 201)
        self.assertEqual(self.send(me, others[2]).status_code, 400)  # over the limit of 2
        self.assertEqual(self.client.get("/api/v1/questions/quota/").data["limit"], 2)

        self.client.force_authenticate(self.boss)
        self.client.put(url, {"monthly_limit": 3}, format="json")
        self.assertEqual(self.send(me, others[2]).status_code, 201)  # 3rd one now allowed
        self.assertEqual(self.send(me, others[3]).status_code, 400)  # the limit is 3 now

        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.put(url, {"monthly_limit": 30}, format="json").data, {"monthly_limit": 30})
        self.assertEqual(self.send(me, others[3]).status_code, 201)  # raised well above 3

        self.client.force_authenticate(self.boss)
        self.client.put(url, {"monthly_limit": 1}, format="json")
        self.assertEqual(self.send(self.team[1], self.team[2]).status_code, 201)
        self.assertEqual(self.send(self.team[1], self.team[3]).status_code, 400)  # over the new limit

    def test_cannot_score_the_same_colleague_twice_in_a_month(self):
        self.assertEqual(self.send(self.team[0], self.team[1]).status_code, 201)
        self.assertEqual(self.send(self.team[0], self.team[1]).status_code, 400)

    def test_limit_does_not_apply_to_the_next_month(self):
        from datetime import timedelta

        self.send(self.team[0], self.team[1])
        Question.objects.update(created_at=timezone.now() - timedelta(days=40))
        self.assertEqual(self.send(self.team[0], self.team[1]).status_code, 201)

    def test_dashboard_counts_for_both_roles(self):
        self.send(self.team[0], self.team[1])

        for viewer in (self.boss, self.team[4]):
            self.client.force_authenticate(viewer)
            data = self.client.get("/api/v1/questions/dashboard/").data
            self.assertEqual(data["staff"], 7)  # boss + 5 + cardio
            self.assertEqual(data["areas"], 2)
            self.assertEqual(data["evaluated"], 1)
            emergency = next(a for a in data["by_area"] if a["area"] == "Emergency")
            self.assertEqual((emergency["staff"], emergency["evaluated"]), (6, 1))
