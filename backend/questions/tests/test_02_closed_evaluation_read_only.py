from unittest.mock import patch

from rest_framework.test import APITestCase

from users.models import User

from ..models import Category, Criterion, Evaluation
from .helpers import create_user


class ClosedEvaluationReadOnlyTests(APITestCase):
    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("closed.boss", User.Role.BOSS)
        self.evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Evaluación cerrada",
            created_by=self.boss,
            is_available=False,
        )
        self.category = Category.objects.create(
            evaluation=self.evaluation,
            name="Categoría",
            code="closed-category",
        )
        self.criterion = Criterion.objects.create(
            category=self.category,
            name="Pregunta",
            code="closed-criterion",
        )
        self.client.force_authenticate(self.boss)

    def test_closed_evaluation_can_be_viewed_but_not_modified(self):
        evaluation_id = self.evaluation.pk
        evaluation_url = f"/api/v1/questions/evaluations/{evaluation_id}/"
        category_url = f"/api/v1/questions/categories/{self.category.pk}/"
        criterion_url = f"/api/v1/questions/criteria/{self.criterion.pk}/"

        self.assertEqual(
            self.client.get(f"/api/v1/questions/form/?evaluation={evaluation_id}&include_inactive=1").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/questions/categories/?evaluation={evaluation_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/questions/submissions/?evaluation={evaluation_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(evaluation_url, {"name": "Cambio no permitido"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(evaluation_url).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/questions/categories/",
                {"evaluation": evaluation_id, "name": "Nueva", "criteria": ["Pregunta nueva"]},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(self.client.patch(category_url, {"name": "Cambio"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(category_url).status_code, 403)
        self.assertEqual(
            self.client.post(f"{category_url}criteria/", {"name": "Pregunta nueva"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.patch(criterion_url, {"name": "Cambio"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(criterion_url).status_code, 403)

        self.evaluation.refresh_from_db()
        self.category.refresh_from_db()
        self.criterion.refresh_from_db()
        self.assertEqual(self.evaluation.name, "Evaluación cerrada")
        self.assertFalse(self.evaluation.is_available)
        self.assertEqual(self.category.name, "Categoría")
        self.assertEqual(self.criterion.name, "Pregunta")
        self.assertEqual(self.evaluation.categories.count(), 1)
        self.assertEqual(self.category.criteria.count(), 1)

    def test_expired_evaluation_is_also_read_only(self):
        from datetime import date

        self.evaluation.is_available = True
        self.evaluation.closes_on = date(2026, 10, 25)
        self.evaluation.save(update_fields=["is_available", "closes_on"])

        with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 26)):
            response = self.client.patch(
                f"/api/v1/questions/evaluations/{self.evaluation.pk}/",
                {"name": "Cambio no permitido"},
                format="json",
            )
            self.assertEqual(response.status_code, 403)
            evaluations = self.client.get("/api/v1/questions/evaluations/").data

        self.assertEqual(evaluations[0]["status"], "closed")
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.name, "Evaluación cerrada")
