from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation
from .helpers import create_user


class EvaluationAreaScopeTests(APITestCase):
    def test_collaborators_only_see_evaluations_for_their_area_and_cannot_bypass_scope(self):
        Evaluation.objects.update(is_available=False)
        boss = create_user("scope.boss", User.Role.BOSS)
        collaborator = create_user("scope.me", User.Role.COLLABORATOR, area="Emergency")
        colleague = create_user("scope.peer", User.Role.COLLABORATOR, area="Emergency")
        other_area_person = create_user("scope.cardio", User.Role.COLLABORATOR, area="Cardiology")
        excluded_evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Cardiology only",
            created_by=boss,
            areas=["Cardiology"],
        )
        available_evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Emergency only",
            created_by=boss,
            areas=["Emergency"],
        )
        mixed_evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Emergency and Cardiology",
            created_by=boss,
            areas=["Emergency", "Cardiology"],
            personal_ids=[colleague.pk, other_area_person.pk],
        )
        client = self.client
        client.force_authenticate(collaborator)

        visible_evaluations = client.get("/api/v1/questions/evaluations/").data
        visible_ids = [item["id"] for item in visible_evaluations]
        self.assertEqual(visible_ids, [available_evaluation.pk, mixed_evaluation.pk])
        mixed = next(item for item in visible_evaluations if item["id"] == mixed_evaluation.pk)
        self.assertEqual(mixed["personal_ids"], [colleague.pk])
        self.assertEqual(client.get(f"/api/v1/questions/form/?evaluation={excluded_evaluation.pk}").data, [])
        visible_people = [item["id"] for item in client.get("/api/v1/users/collaborators/").data]
        self.assertEqual(visible_people, [colleague.pk])
        response = client.post(
            "/api/v1/questions/",
            {"evaluation": excluded_evaluation.pk, "personal": colleague.pk, "answers": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("evaluation", response.data)
        self.assertNotIn(other_area_person.pk, visible_people)
