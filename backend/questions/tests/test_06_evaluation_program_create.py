from rest_framework.test import APITestCase

from users.models import User

from ..models import Category, Criterion, Evaluation, Question
from .helpers import create_user


class EvaluationProgramCreateTests(APITestCase):
    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("program.boss", User.Role.BOSS)
        self.emergency = create_user("program.emergency", User.Role.COLLABORATOR, area="Emergency")
        self.cardiology = create_user("program.cardiology", User.Role.COLLABORATOR, area="Cardiology")
        self.source = Evaluation.objects.create(monthly_limit=3, 
            name="Desempeño",
            created_by=self.boss,
            rating_type=Evaluation.RatingType.DESCRIPTIVE,
        )
        self.category = Category.objects.create(
            evaluation=self.source,
            name="Trabajo en equipo",
            code="program-source-category",
        )
        self.criterion = Criterion.objects.create(
            category=self.category,
            name="Colabora con el equipo",
            code="program-source-criterion",
        )
        self.client.force_authenticate(self.boss)

    def program(self, close_date, area, person, monthly_limit):
        return self.client.post(
            f"/api/v1/questions/evaluations/{self.source.pk}/programs/",
            {
                "closes_on": close_date,
                "areas": [area],
                "personal_ids": [person.pk],
                "monthly_limit": monthly_limit,
            },
            format="json",
        )

    def test_reusing_a_form_creates_independent_programs(self):
        from datetime import date

        emergency_evaluator = create_user("program.emergency.evaluator", User.Role.COLLABORATOR, area="Emergency")
        cardiology_evaluator = create_user("program.cardiology.evaluator", User.Role.COLLABORATOR, area="Cardiology")
        first = self.program("2026-11-15", "Emergency", self.emergency, 2)
        second = self.program("2026-12-20", "Cardiology", self.cardiology, 5)

        self.assertEqual((first.status_code, second.status_code), (201, 201))
        first_id, second_id = first.data["id"], second.data["id"]
        self.assertNotEqual(first_id, second_id)

        first_evaluation = Evaluation.objects.get(pk=first_id)
        second_evaluation = Evaluation.objects.get(pk=second_id)
        self.assertEqual(
            (first_evaluation.name, first_evaluation.rating_type, first_evaluation.areas,
             first_evaluation.personal_ids, first_evaluation.closes_on, first_evaluation.monthly_limit),
            ("Desempeño", Evaluation.RatingType.DESCRIPTIVE, ["Emergency"],
             [self.emergency.pk], date(2026, 11, 15), 2),
        )
        self.assertEqual(
            (second_evaluation.name, second_evaluation.areas, second_evaluation.personal_ids,
             second_evaluation.closes_on, second_evaluation.monthly_limit),
            ("Desempeño", ["Cardiology"], [self.cardiology.pk],
             date(2026, 12, 20), 5),
        )

        first_category = first_evaluation.categories.get()
        second_category = second_evaluation.categories.get()
        self.assertNotEqual(first_category.pk, second_category.pk)
        self.assertNotEqual(first_category.code, second_category.code)
        self.assertEqual(first_category.criteria.get().name, self.criterion.name)
        self.assertEqual(second_category.criteria.get().name, self.criterion.name)
        self.assertNotEqual(first_category.criteria.get().code, second_category.criteria.get().code)

        for evaluation, evaluator, target in (
            (first_evaluation, emergency_evaluator, self.emergency),
            (second_evaluation, cardiology_evaluator, self.cardiology),
        ):
            self.client.force_authenticate(evaluator)
            response = self.client.post(
                "/api/v1/questions/",
                {
                    "evaluation": evaluation.pk,
                    "personal": target.pk,
                    "answers": [{"criterion": evaluation.categories.get().criteria.get().code, "score": 3}],
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(Question.objects.filter(evaluation=first_evaluation).count(), 1)
        self.assertEqual(Question.objects.filter(evaluation=second_evaluation).count(), 1)
        self.assertEqual(Question.objects.filter(evaluation=self.source).count(), 0)

        self.source.refresh_from_db()
        self.assertIsNone(self.source.closes_on)
        self.assertIsNone(self.source.areas)
        self.assertEqual(self.source.categories.count(), 1)
        self.assertEqual(Evaluation.objects.filter(name="Desempeño").count(), 3)

    def test_cannot_program_another_boss_form_or_assign_people_outside_areas(self):
        other_boss = create_user("other.program.boss", User.Role.BOSS)
        other_form = Evaluation.objects.create(monthly_limit=3, name="Privada", created_by=other_boss)
        forbidden = self.client.post(
            f"/api/v1/questions/evaluations/{other_form.pk}/programs/",
            {"closes_on": "2026-11-15", "areas": [], "personal_ids": [], "monthly_limit": 3},
            format="json",
        )
        invalid_person = self.program("2026-11-15", "Emergency", self.cardiology, 3)

        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(invalid_person.status_code, 400)
        self.assertEqual(Evaluation.objects.filter(created_by=self.boss).count(), 1)
