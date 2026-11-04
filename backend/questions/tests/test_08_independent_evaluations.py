from unittest.mock import patch

from rest_framework.test import APITestCase

from users.models import User

from ..models import Category, Criterion, Evaluation, Question
from .helpers import create_user


class IndependentEvaluationsTests(APITestCase):
    """Each evaluation is its own form: categories added to one never reach the others."""

    EVALUATIONS = "/api/v1/questions/evaluations/"
    CATEGORIES = "/api/v1/questions/categories/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        self.me = create_user("me.demo", User.Role.COLLABORATOR)
        self.others = [create_user(f"o{i}.demo", User.Role.COLLABORATOR) for i in range(3)]
        self.first = Evaluation.objects.get()
        self.client.force_authenticate(self.boss)
        self.second = self.client.post(self.EVALUATIONS, {"name": "Evaluación de liderazgo"}, format="json").data
        self.client.post(
            self.CATEGORIES,
            {"evaluation": self.second["id"], "name": "Liderazgo", "criteria": ["Motiva al equipo.", "Decide a tiempo."]},
            format="json",
        )
    def form(self, evaluation):
        self.client.force_authenticate(self.me)
        return self.client.get(f"/api/v1/questions/form/?evaluation={evaluation}").data

    def codes(self, evaluation):
        return [q["code"] for c in self.form(evaluation) for q in c["criteria"]]

    def send(self, evaluation, personal, codes):
        self.client.force_authenticate(self.me)
        body = {
            "evaluation": evaluation,
            "personal": personal.pk,
            "answers": [{"criterion": c, "score": 4} for c in codes],
        }
        return self.client.post("/api/v1/questions/", body, format="json")

    def test_a_new_category_only_goes_into_its_evaluation(self):
        self.assertEqual(len(self.codes(self.first.pk)), 12)  # the old form is untouched
        self.assertEqual(len(self.codes(self.second["id"])), 2)
        self.assertEqual([c["name"] for c in self.form(self.second["id"])], ["Liderazgo"])

        # adding a category to the first one does not change the second
        self.client.force_authenticate(self.boss)
        self.client.post(self.CATEGORIES, {"evaluation": self.first.pk, "name": "Extra", "criteria": ["Una más."]}, format="json")
        self.assertEqual(len(self.codes(self.first.pk)), 13)
        self.assertEqual(len(self.codes(self.second["id"])), 2)

    def test_answers_belong_to_one_evaluation_and_have_their_own_quota(self):
        first_codes, second_codes = self.codes(self.first.pk), self.codes(self.second["id"])
        self.assertEqual(self.send(self.first.pk, self.others[0], first_codes).status_code, 201)
        # the questions of the other evaluation are not valid here
        self.assertEqual(self.send(self.first.pk, self.others[1], second_codes).status_code, 400)
        # the same colleague can be scored again, in the other evaluation
        self.assertEqual(self.send(self.second["id"], self.others[0], second_codes).status_code, 201)
        # but only once in each
        self.assertEqual(self.send(self.second["id"], self.others[0], second_codes).status_code, 400)

        used = self.client.get(f"/api/v1/questions/quota/?evaluation={self.second['id']}").data
        self.assertEqual((used["used"], used["personal"]), (1, [self.others[0].pk]))
        self.assertEqual(Question.objects.filter(evaluation_id=self.first.pk).count(), 12)
        self.assertEqual(Question.objects.filter(evaluation_id=self.second["id"]).count(), 2)

    def test_must_choose_when_several_are_open_and_closed_ones_are_hidden(self):
        codes = self.codes(self.first.pk)
        self.assertEqual(self.send(None, self.others[0], codes).status_code, 400)  # which one?

        self.client.force_authenticate(self.boss)
        closed = self.client.patch(f"{self.EVALUATIONS}{self.second['id']}/", {"is_available": False}, format="json")
        self.assertFalse(closed.data["is_available"])
        self.client.force_authenticate(self.me)
        self.assertEqual([e["name"] for e in self.client.get(self.EVALUATIONS).data], [self.first.name])
        self.assertEqual(self.form(self.second["id"]), [])
        self.assertEqual(self.send(self.second["id"], self.others[0], ["x"]).status_code, 400)
        self.assertEqual(self.send(None, self.others[0], codes).status_code, 201)  # one left: no need to choose

        self.client.force_authenticate(self.boss)
        self.assertEqual(len(self.client.get(self.EVALUATIONS).data), 2)  # the boss still sees both

    def test_boss_manages_evaluations_and_categories_need_one(self):
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.post(self.EVALUATIONS, {"name": "X"}, format="json").status_code, 403)
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.post(self.EVALUATIONS, {"name": " "}, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.CATEGORIES, {"name": "Suelta", "criteria": ["a"]}, format="json").status_code, 400)

        self.assertEqual(self.client.delete(f"{self.EVALUATIONS}{self.first.pk}/").status_code, 204 if not self.first.questions.exists() else 400)
        # one with answers cannot be deleted
        third = self.client.post(self.EVALUATIONS, {"name": "Tercera"}, format="json").data
        self.client.post(self.CATEGORIES, {"evaluation": third["id"], "name": "C", "criteria": ["p"]}, format="json")
        self.send(third["id"], self.others[0], self.codes(third["id"]))
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.delete(f"{self.EVALUATIONS}{third['id']}/").status_code, 400)

    def test_results_and_submissions_say_which_evaluation(self):
        self.send(self.second["id"], self.others[0], self.codes(self.second["id"]))
        self.client.force_authenticate(self.boss)
        submission = self.client.get("/api/v1/questions/submissions/").data[0]
        self.assertEqual(submission["evaluation_name"], "Evaluación de liderazgo")
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.get("/api/v1/questions/sent/").data[0]["evaluation"], self.second["id"])
        self.client.force_authenticate(self.others[0])
        evaluations = self.client.get("/api/v1/questions/results/").data["evaluations"]
        self.assertEqual([e["name"] for e in evaluations], ["Evaluación de liderazgo"])

    def test_an_evaluation_closes_at_the_end_of_its_closing_day(self):
        from datetime import date

        codes = self.codes(self.second["id"])
        evaluation = Evaluation.objects.get(pk=self.second["id"])
        evaluation.closes_on = date(2026, 9, 30)
        evaluation.save()

        # on the closing day itself it can still be answered (until the end of the day)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 9, 30)):
            self.assertEqual(self.form(self.second["id"]) != [], True)
            self.assertEqual(self.send(self.second["id"], self.others[0], codes).status_code, 201)

        # the next day it is closed: hidden from collaborators and no longer accepts answers
        with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 1)):
            self.client.force_authenticate(self.me)
            self.assertEqual([e["id"] for e in self.client.get(self.EVALUATIONS).data], [self.first.pk])
            self.assertEqual(self.form(self.second["id"]), [])
            self.assertEqual(self.send(self.second["id"], self.others[1], codes).status_code, 400)

            self.client.force_authenticate(self.boss)
            listed = {e["id"]: e for e in self.client.get(self.EVALUATIONS).data}
            self.assertEqual(listed[self.second["id"]]["status"], "closed")
            self.assertEqual(listed[self.second["id"]]["answers"], 1)

            # its answers are kept and nobody can add more
            self.assertEqual(Question.objects.filter(evaluation_id=self.second["id"]).count(), 2)

    def test_status_closed_by_the_boss_wins_over_the_date(self):
        self.client.force_authenticate(self.boss)
        r = self.client.patch(f"{self.EVALUATIONS}{self.second['id']}/", {"is_available": False}, format="json")
        self.assertEqual(r.data["status"], "closed")

    def test_an_evaluation_with_answers_is_locked_for_new_categories_and_questions(self):
        self.send(self.first.pk, self.others[0], self.codes(self.first.pk))
        self.client.force_authenticate(self.boss)
        listed = {e["id"]: e for e in self.client.get(self.EVALUATIONS).data}
        self.assertTrue(listed[self.first.pk]["used"])
        self.assertFalse(listed[self.second["id"]]["used"])

        # the one with answers does not accept new categories, new questions or re-activations
        locked = self.client.post(self.CATEGORIES, {"evaluation": self.first.pk, "name": "Nueva", "criteria": ["Algo"]}, format="json")
        self.assertEqual(locked.status_code, 400)
        category = Category.objects.filter(evaluation=self.first).first()
        self.assertEqual(self.client.post(f"{self.CATEGORIES}{category.pk}/criteria/", {"name": "Otra"}, format="json").status_code, 400)
        self.assertEqual(len(self.codes(self.first.pk)), 12)  # the form did not change

        # a question can be turned off, but not back on (that would add it again)
        self.client.force_authenticate(self.boss)
        meta = Criterion.objects.get(code="META")
        self.assertEqual(self.client.patch(f"/api/v1/questions/criteria/{meta.pk}/", {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/questions/criteria/{meta.pk}/", {"is_active": True}, format="json").status_code, 400)

        # the new evaluation (no answers yet) does accept them
        ok = self.client.post(self.CATEGORIES, {"evaluation": self.second["id"], "name": "Otra", "criteria": ["Algo"]}, format="json")
        self.assertEqual(ok.status_code, 201)

    def test_boss_sees_the_results_of_each_person_by_evaluation(self):
        first_codes, second_codes = self.codes(self.first.pk), self.codes(self.second["id"])
        self.send(self.first.pk, self.others[0], first_codes)
        self.send(self.second["id"], self.others[0], second_codes)
        self.send(self.first.pk, self.others[1], first_codes)

        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.get("/api/v1/questions/results-summary/").status_code, 403)

        self.client.force_authenticate(self.boss)
        data = self.client.get(f"/api/v1/questions/results-summary/?evaluation={self.first.pk}").data
        self.assertEqual(data["evaluation"]["id"], self.first.pk)
        self.assertEqual(len(data["categories"]), 4)
        self.assertEqual(sorted(r["personal"] for r in data["rows"]), sorted([self.others[0].pk, self.others[1].pk]))
        row = next(r for r in data["rows"] if r["personal"] == self.others[0].pk)
        self.assertEqual(row["average"], 4.0)
        self.assertEqual(set(row["by_category"]), {c["code"] for c in data["categories"]})

        # the other evaluation has its own categories and only the people evaluated in it
        other = self.client.get(f"/api/v1/questions/results-summary/?evaluation={self.second['id']}").data
        self.assertEqual([c["name"] for c in other["categories"]], ["Liderazgo"])
        self.assertEqual([r["personal"] for r in other["rows"]], [self.others[0].pk])
        self.assertEqual(self.client.get("/api/v1/questions/results-summary/?evaluation=999").data["rows"], [])
