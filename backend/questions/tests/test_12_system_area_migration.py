from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation, Question
from .helpers import create_user


class SystemAreaMigrationTests(APITestCase):
    def test_only_exact_system_area_is_replaced(self):
        from importlib import import_module

        old_area_user = create_user("legacy.system", User.Role.COLLABORATOR, area="Sistema")
        existing_sistemas_user = create_user("existing.sistemas", User.Role.COLLABORATOR, area="Sistemas")
        evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Histórica",
            areas=["Sistema", "Sistemas", "Urgencias"],
        )
        question = Question.objects.create(
            evaluation=evaluation,
            collaborator=old_area_user,
            personal=old_area_user,
            area="Sistema",
            category="Categoria",
            criterion="Criterio",
            score=4,
        )
        migration = import_module("questions.migrations.0033_replace_system_area")

        class MigrationApps:
            models = {
                ("users", "User"): User,
                ("questions", "Evaluation"): Evaluation,
                ("questions", "Question"): Question,
            }

            def get_model(self, app_label, model_name):
                return self.models[(app_label, model_name)]

        migration.replace_system_area(MigrationApps(), schema_editor=None)

        old_area_user.refresh_from_db()
        existing_sistemas_user.refresh_from_db()
        evaluation.refresh_from_db()
        question.refresh_from_db()
        self.assertEqual(old_area_user.area, "Sistemas")
        self.assertEqual(existing_sistemas_user.area, "Sistemas")
        self.assertEqual(evaluation.areas, ["Sistemas", "Urgencias"])
        self.assertEqual(question.area, "Sistemas")
        self.assertEqual(User.objects.filter(area="Sistema").count(), 0)
