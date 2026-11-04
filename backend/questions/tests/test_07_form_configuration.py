from rest_framework.test import APITestCase

from users.models import User

from ..models import Category, Criterion, Evaluation, Question
from .helpers import CRITERIA, create_user


class FormConfigurationTests(APITestCase):
    URL = "/api/v1/questions/categories/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        Evaluation.objects.filter(created_by__isnull=True).update(created_by=self.boss)
        self.me = create_user("me.demo", User.Role.COLLABORATOR)
        self.other = create_user("other.demo", User.Role.COLLABORATOR)
        self.evaluation = Evaluation.objects.get()  # the one created by the data migration

    def form(self):
        self.client.force_authenticate(self.me)
        return self.client.get("/api/v1/questions/form/").data

    def send(self, answers):
        self.client.force_authenticate(self.me)
        body = {"personal": self.other.pk, "answers": [{"criterion": c, "score": 5} for c in answers]}
        return self.client.post("/api/v1/questions/", body, format="json")

    def test_initial_form_comes_from_the_database(self):
        form = self.form()
        self.assertEqual([c["name"] for c in form][0], "Capacidad de respuesta")
        self.assertEqual(sum(len(c["criteria"]) for c in form), 12)

    def test_only_the_boss_configures(self):
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.post(self.URL, {"evaluation": self.evaluation.pk, "name": "X", "criteria": ["a"]}, format="json").status_code, 403)

    def test_create_category_with_its_questions_and_it_enters_the_form(self):
        self.client.force_authenticate(self.boss)
        bad = self.client.post(self.URL, {"evaluation": self.evaluation.pk, "name": "", "criteria": ["a"]}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.post(self.URL, {"evaluation": self.evaluation.pk, "name": "Liderazgo", "criteria": []}, format="json").status_code, 400)
        r = self.client.post(self.URL, {"evaluation": self.evaluation.pk, "name": "Liderazgo", "criteria": ["Motiva al equipo.", "  Toma decisiones  ", ""]}, format="json")
        self.assertEqual(r.status_code, 201)
        created = next(c for c in r.data if c["name"] == "Liderazgo")
        self.assertEqual([q["name"] for q in created["criteria"]], ["Motiva al equipo.", "Toma decisiones"])

        form = self.form()
        self.assertEqual(len(form), 5)
        self.assertEqual(sum(len(c["criteria"]) for c in form), 14)
        # the form now needs the 2 new questions too
        self.assertEqual(self.send(CRITERIA).status_code, 400)
        new_codes = [q["code"] for q in form[-1]["criteria"]]
        self.assertEqual(self.send(CRITERIA + new_codes).status_code, 201)
        saved = Question.objects.filter(criterion=new_codes[0]).first()
        self.assertEqual(saved.category, created["code"])

    def test_deactivating_removes_from_new_forms_but_keeps_history(self):
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.send(CRITERIA).status_code, 201)

        self.client.force_authenticate(self.boss)
        meta = Criterion.objects.get(code="META")
        r = self.client.patch(f"/api/v1/questions/criteria/{meta.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sum(len(c["criteria"]) for c in self.form()), 11)
        self.assertEqual(self.send([c for c in CRITERIA if c != "META"]).status_code, 400)  # already scored this month
        # read-only tables can still ask for the old question
        self.client.force_authenticate(self.me)
        everything = self.client.get("/api/v1/questions/form/?include_inactive=1").data
        self.assertEqual(sum(len(c["criteria"]) for c in everything), 12)

        category = Category.objects.get(code="comunicacion")
        self.client.force_authenticate(self.boss)
        self.client.patch(f"/api/v1/questions/categories/{category.pk}/", {"is_active": False}, format="json")
        self.assertEqual(len(self.form()), 3)

    def test_used_items_cannot_be_deleted_but_unused_ones_can(self):
        self.client.force_authenticate(self.boss)
        self.send(CRITERIA)
        self.client.force_authenticate(self.boss)
        meta = Criterion.objects.get(code="META")
        self.assertEqual(self.client.delete(f"/api/v1/questions/criteria/{meta.pk}/").status_code, 400)
        cat = Category.objects.get(code="comunicacion")
        self.assertEqual(self.client.delete(f"/api/v1/questions/categories/{cat.pk}/").status_code, 400)

        fresh = self.client.post("/api/v1/questions/evaluations/", {"name": "Nueva"}, format="json").data
        made = self.client.post(self.URL, {"evaluation": fresh["id"], "name": "Temporal", "criteria": ["Una pregunta"]}, format="json").data
        temp = next(c for c in made if c["name"] == "Temporal")
        self.assertFalse(temp["used"])
        added = self.client.post(f"/api/v1/questions/categories/{temp['id']}/criteria/", {"name": "Otra"}, format="json")
        self.assertEqual(added.status_code, 201)
        self.assertEqual(self.client.delete(f"/api/v1/questions/categories/{temp['id']}/").status_code, 200)
        self.assertFalse(Category.objects.filter(code=temp["code"]).exists())
        self.assertFalse(Criterion.objects.filter(category__code=temp["code"]).exists())

    def test_rename_and_averages_follow_the_categories(self):
        self.client.force_authenticate(self.boss)
        cat = Category.objects.get(code="comunicacion")
        self.client.patch(f"/api/v1/questions/categories/{cat.pk}/", {"name": "Comunicación efectiva"}, format="json")
        self.send(CRITERIA)
        self.client.force_authenticate(self.boss)
        names = [c["name"] for c in self.client.get("/api/v1/questions/category-averages/").data["by_category"]]
        self.assertIn("Comunicación efectiva", names)
        self.assertEqual(len(names), 4)
