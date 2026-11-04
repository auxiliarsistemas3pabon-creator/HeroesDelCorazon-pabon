from rest_framework.test import APITestCase

from users.models import User

from ..models import Evaluation, Question
from .helpers import ALL_SCORES, create_user


class QuestionTests(APITestCase):
    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        self.laura = create_user("laura.demo", User.Role.COLLABORATOR)
        self.pedro = create_user("pedro.demo", User.Role.COLLABORATOR)
        self.other_area = create_user("ines.demo", User.Role.COLLABORATOR, area="Cardiology")

    def payload(self, personal, scores=ALL_SCORES):
        return {
            "personal": personal.pk,
            "answers": [{"criterion": c, "score": s} for c, s in scores.items()],
        }

    def test_form_groups_12_criteria_in_4_categories_in_spanish(self):
        self.client.force_authenticate(self.boss)
        data = self.client.get("/api/v1/questions/form/").data
        self.assertEqual(len(data), 4)
        self.assertTrue(all(len(c["criteria"]) == 3 for c in data))
        self.assertEqual(data[0]["name"], "Capacidad de respuesta")
        self.assertEqual(data[0]["criteria"][0]["code"], "META")

    def test_collaborator_scores_a_colleague(self):
        self.client.force_authenticate(self.laura)
        r = self.client.post("/api/v1/questions/", self.payload(self.pedro), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Question.objects.filter(collaborator=self.laura, personal=self.pedro).count(), 12)

    def test_evaluation_only_allows_selected_staff_members(self):
        excluded = create_user("excluded.demo", User.Role.COLLABORATOR)
        evaluation = Evaluation.objects.get()
        evaluation.areas = ["Emergency"]
        evaluation.personal_ids = [self.pedro.pk]
        evaluation.save(update_fields=["areas", "personal_ids"])
        self.client.force_authenticate(self.laura)

        response = self.client.post(
            "/api/v1/questions/",
            {**self.payload(excluded), "evaluation": evaluation.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("personal", response.data)

        allowed = self.client.post(
            "/api/v1/questions/",
            {**self.payload(self.pedro), "evaluation": evaluation.pk},
            format="json",
        )
        self.assertEqual(allowed.status_code, 201)

    def test_cannot_score_yourself(self):
        self.client.force_authenticate(self.laura)
        r = self.client.post("/api/v1/questions/", self.payload(self.laura), format="json")
        self.assertEqual(r.status_code, 400)

    def test_collaborator_list_excludes_themselves_and_other_areas(self):
        self.client.force_authenticate(self.laura)
        ids = [u["id"] for u in self.client.get("/api/v1/users/collaborators/").data]
        self.assertEqual(ids, [self.pedro.pk])

    def test_evaluation_area_scope_hides_evaluation_and_rejects_submission(self):
        evaluation = Evaluation.objects.create(monthly_limit=3, 
            name="Solo Cardiology",
            created_by=self.boss,
            areas=["Cardiology"],
        )
        self.client.force_authenticate(self.laura)
        evaluations = self.client.get("/api/v1/questions/evaluations/").data
        self.assertNotIn(evaluation.pk, [item["id"] for item in evaluations])
        self.assertEqual(
            self.client.get(f"/api/v1/questions/form/?evaluation={evaluation.pk}").data,
            [],
        )

        r = self.client.post(
            "/api/v1/questions/",
            {**self.payload(self.pedro), "evaluation": evaluation.pk},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_validates_score_complete_criteria_and_area(self):
        self.client.force_authenticate(self.laura)
        bad = {**ALL_SCORES, "META": 9}
        self.assertEqual(self.client.post("/api/v1/questions/", self.payload(self.pedro, bad), format="json").status_code, 400)
        incomplete = {"META": 4}
        self.assertEqual(self.client.post("/api/v1/questions/", self.payload(self.pedro, incomplete), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/v1/questions/", self.payload(self.other_area), format="json").status_code, 400)

    def test_boss_cannot_score_directly(self):
        self.client.force_authenticate(self.boss)
        r = self.client.post("/api/v1/questions/", self.payload(self.laura), format="json")
        self.assertEqual(r.status_code, 403)

    def submit(self, collaborator, personal, scores=ALL_SCORES):
        self.client.force_authenticate(collaborator)
        self.client.post("/api/v1/questions/", self.payload(personal, scores), format="json")

    def test_evaluation_counts_when_sent_and_final_score_is_the_average(self):
        self.submit(self.pedro, self.laura, {**ALL_SCORES, "META": 5, "EFECTIVA": 3})  # average 4.0
        ines_area_mate = create_user("sofia.demo", User.Role.COLLABORATOR)
        self.submit(ines_area_mate, self.laura, {c: 5 for c in ALL_SCORES})  # average 5.0

        self.client.force_authenticate(self.laura)
        results = self.client.get("/api/v1/questions/results/").data
        self.assertEqual(results["average"], 4.5)
        self.assertEqual(len(results["evaluations"]), 1)
        self.assertEqual(len(results["evaluations"][0]["by_category"]), 4)
        self.assertEqual(len(self.client.get("/api/v1/questions/").data), 24)

        self.client.force_authenticate(self.boss)
        submissions = self.client.get("/api/v1/questions/submissions/").data
        self.assertEqual(sorted(s["average"] for s in submissions), [4.0, 5.0])
        self.assertTrue(all(len(s["answers"]) == 12 for s in submissions))

    def test_collaborator_sees_the_evaluations_they_sent(self):
        self.submit(self.pedro, self.laura, {**ALL_SCORES, "META": 5, "EFECTIVA": 3})
        self.submit(self.laura, self.pedro)
        self.client.force_authenticate(self.pedro)
        sent = self.client.get("/api/v1/questions/sent/").data
        self.assertEqual(len(sent), 1)
        self.assertEqual((sent[0]["personal"], sent[0]["average"], len(sent[0]["answers"])), (self.laura.pk, 4.0, 12))
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.get("/api/v1/questions/sent/").status_code, 403)

    def test_only_the_boss_sees_the_submissions_and_there_is_no_review_endpoint(self):
        self.submit(self.pedro, self.laura)
        self.assertEqual(self.client.get("/api/v1/questions/submissions/").status_code, 403)
        self.client.force_authenticate(self.boss)
        self.assertEqual(self.client.post("/api/v1/questions/review/", {}, format="json").status_code, 404)

    def sent_email(self, scores):
        from django.core import mail

        with self.captureOnCommitCallbacks(execute=True):
            self.submit(self.pedro, self.laura, scores)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["laura.demo@demo.com"])
        return mail.outbox[0]

    def test_email_congratulates_from_4_0_up(self):
        email = self.sent_email(ALL_SCORES)  # average 4.0
        self.assertIn("4.0", email.body)
        self.assertIn("Felicitaciones", email.subject)
        self.assertIn("Felicitaciones", email.body)
        self.assertIn("Héroes del Corazón", email.body)
        self.assertNotIn("Ánimo", email.body)

    def test_email_encourages_below_4_0(self):
        email = self.sent_email({c: 3 for c in ALL_SCORES})  # average 3.0
        self.assertIn("3.0", email.body)
        self.assertNotIn("Felicitaciones", email.subject + email.body)
        self.assertIn("Ánimo", email.body)
        self.assertIn("Héroes del Corazón", email.body)

    def test_stats_count_evaluated_users(self):
        self.client.force_authenticate(self.boss)
        r = self.client.get("/api/v1/questions/stats/").data
        self.assertEqual((r["total"], r["evaluated"], r["pending"]), (2, 0, 2))
        self.submit(self.pedro, self.laura)
        self.client.force_authenticate(self.boss)
        r = self.client.get("/api/v1/questions/stats/").data
        # the boss belongs to Emergency: sees Laura and Pedro, not the Cardiology one
        self.assertEqual((r["total"], r["evaluated"], r["pending"]), (2, 1, 1))
        self.client.force_authenticate(self.laura)
        self.assertEqual(self.client.get("/api/v1/questions/stats/").status_code, 403)
