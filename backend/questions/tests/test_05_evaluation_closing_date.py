from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation
from .helpers import PASSWORD, create_user


class EvaluationClosingDateTests(APITestCase):
    EVALUATIONS = "/api/v1/questions/evaluations/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        Evaluation.objects.filter(created_by__isnull=True).update(created_by=self.boss)
        self.client.force_authenticate(self.boss)

    def test_boss_can_choose_any_closing_date_and_it_closes_automatically(self):
        created = self.client.post(self.EVALUATIONS, {"name": "Sin cierre automático"}, format="json")
        self.assertEqual((created.status_code, created.data["closes_on"], created.data["status"]), (201, None, "available"))

        scheduled = self.client.patch(
            f"{self.EVALUATIONS}{created.data['id']}/",
            {"closes_on": "2030-01-01"},
            format="json",
        )
        self.assertEqual((scheduled.status_code, scheduled.data["closes_on"]), (200, "2030-01-01"))

        invalid = self.client.patch(
            f"{self.EVALUATIONS}{created.data['id']}/",
            {"closes_on": "invalid-date"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

        closed = self.client.patch(
            f"{self.EVALUATIONS}{created.data['id']}/",
            {"closes_on": "2000-01-01"},
            format="json",
        )
        self.assertEqual(closed.data["status"], "closed")

    def test_boss_can_assign_all_selected_or_no_evaluation_areas(self):
        User.objects.create_user(
            username="area.demo",
            email="area.demo@demo.com",
            password=PASSWORD,
            first_name="Area",
            last_name="Demo",
            role=User.Role.COLLABORATOR,
            area="Emergency",
        )
        evaluation = self.client.post(self.EVALUATIONS, {"name": "Áreas"}, format="json").data
        url = f"{self.EVALUATIONS}{evaluation['id']}/"

        selected = self.client.patch(url, {"areas": ["Emergency"]}, format="json")
        self.assertEqual((selected.status_code, selected.data["areas"]), (200, ["Emergency"]))

        invalid = self.client.patch(url, {"areas": ["No existe"]}, format="json")
        self.assertEqual(invalid.status_code, 400)

        no_areas = self.client.patch(url, {"areas": []}, format="json")
        self.assertEqual((no_areas.status_code, no_areas.data["areas"]), (200, []))
        all_areas = self.client.patch(url, {"areas": None}, format="json")
        self.assertEqual((all_areas.status_code, all_areas.data["areas"]), (200, None))

    def test_evaluation_with_no_selected_areas_is_hidden_from_collaborators(self):
        collaborator = create_user("area.none", User.Role.COLLABORATOR, area="Emergency")
        evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Sin áreas",
            created_by=self.boss,
            areas=[],
        )
        self.client.force_authenticate(collaborator)

        self.assertNotIn(
            evaluation.pk,
            [item["id"] for item in self.client.get(self.EVALUATIONS).data],
        )
        self.assertEqual(
            self.client.get(f"/api/v1/questions/form/?evaluation={evaluation.pk}").data,
            [],
        )

    def test_boss_can_assign_staff_members_and_only_they_can_be_evaluated(self):
        first = create_user("first.target", User.Role.PERSONAL, area="Emergency")
        second = create_user("second.target", User.Role.PERSONAL, area="Emergency")
        self.client.force_authenticate(self.boss)
        evaluation = self.client.post(self.EVALUATIONS, {"name": "Personas elegidas"}, format="json").data
        url = f"{self.EVALUATIONS}{evaluation['id']}/"

        selected = self.client.patch(
            url,
            {"areas": ["Emergency"], "personal_ids": [first.pk]},
            format="json",
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.data["personal_ids"], [first.pk])

        self.client.force_authenticate(first)
        visible_people = self.client.get("/api/v1/users/collaborators/").data
        self.assertIn(second.pk, [person["id"] for person in visible_people])

        self.client.force_authenticate(self.boss)
        outside_areas = self.client.patch(
            url,
            {"areas": ["Emergency"], "personal_ids": [create_user("other.target", User.Role.PERSONAL, area="Cardiology").pk]},
            format="json",
        )
        self.assertEqual(outside_areas.status_code, 400)
