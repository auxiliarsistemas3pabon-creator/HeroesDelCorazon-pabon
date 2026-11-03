from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from users.models import User

from .models import Category, Criterion, Evaluation, Question

# All data is fictitious.
PASSWORD = "Demo-Pass-2026"
# The 12 questions of the initial form come from the data migration.
CRITERIA = ["META", "EFECTIVA", "PRODUCTIVIDAD", "IMPLEMENTA", "APRENDIZAJE", "RECEPTIVA", "RESPETA", "ESCUCHA", "FOMENTA", "INTERACCION", "CONOCIMIENTO", "DISPOSICION"]
ALL_SCORES = {c: 4 for c in CRITERIA}


def create_user(username, role, area="Emergency"):
    return User.objects.create_user(
        username=username, email=f"{username}@demo.com", password=PASSWORD,
        first_name="Demo", last_name="Fictional", role=role, area=area,
    )


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


class MonthRolloverTests(APITestCase):
    """The monthly quota follows the calendar month in the project time zone (America/Bogota)."""

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        Evaluation.objects.update(closes_on=None, monthly_limit=3)  # these tests travel through several months: no deadline
        self.me = create_user("me.demo", User.Role.COLLABORATOR)
        self.team = [create_user(f"c{i}.demo", User.Role.COLLABORATOR) for i in range(6)]

    def at(self, year, month, day, hour, minute):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return patch("django.utils.timezone.now", return_value=datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/Bogota")))

    def send(self, personal):
        self.client.force_authenticate(self.me)
        body = {"personal": personal.pk, "answers": [{"criterion": c, "score": 4} for c in CRITERIA]}
        return self.client.post("/api/v1/questions/", body, format="json")

    def quota(self):
        self.client.force_authenticate(self.me)
        return self.client.get("/api/v1/questions/quota/").data

    def test_quota_resets_on_the_first_day_of_the_next_month(self):
        with self.at(2026, 10, 15, 10, 0):
            for p in self.team[:3]:
                self.assertEqual(self.send(p).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)
            self.assertEqual(self.quota()["used"], 3)

        with self.at(2026, 11, 2, 9, 0):  # next month: a clean quota, and the same colleagues can be scored again
            self.assertEqual(self.quota()["used"], 0)
            self.assertEqual(self.quota()["personal"], [])
            for p in self.team[:3]:
                self.assertEqual(self.send(p).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)
            self.assertEqual(self.quota()["used"], 3)

        with self.at(2026, 10, 20, 8, 0):  # going back to October still shows only October's three
            self.assertEqual(self.quota()["used"], 3)

    def test_month_boundary_uses_local_time_not_utc(self):
        # Oct 31 22:00 in Bogota is already Nov 1 03:00 UTC: it must still count as October.
        with self.at(2026, 10, 31, 22, 0):
            self.assertEqual(self.send(self.team[0]).status_code, 201)
        with self.at(2026, 10, 31, 23, 59):
            self.assertEqual(self.quota()["used"], 1)
        with self.at(2026, 11, 1, 0, 0):
            self.assertEqual(self.quota()["used"], 0)
        with self.at(2026, 11, 1, 0, 1):
            self.assertEqual(self.send(self.team[0]).status_code, 201)  # new month, same colleague allowed

    def test_partial_quota_leaves_the_rest_for_the_same_month(self):
        with self.at(2026, 10, 5, 10, 0):
            self.send(self.team[0])
            self.assertEqual(self.quota()["used"], 1)
            self.assertEqual(self.send(self.team[1]).status_code, 201)
            self.assertEqual(self.send(self.team[2]).status_code, 201)
            self.assertEqual(self.send(self.team[3]).status_code, 400)

    def test_each_collaborator_has_their_own_quota(self):
        other = self.team[5]
        with self.at(2026, 10, 5, 10, 0):
            for p in self.team[:3]:
                self.send(p)
            self.client.force_authenticate(other)
            body = {"personal": self.team[0].pk, "answers": [{"criterion": c, "score": 5} for c in CRITERIA]}
            self.assertEqual(self.client.post("/api/v1/questions/", body, format="json").status_code, 201)
            self.assertEqual(self.client.get("/api/v1/questions/quota/").data["used"], 1)


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
        self.assertEqual(get()["staff"], 3)
        self.assertEqual(get("?date_from=2026-09-01&date_to=2026-09-30")["staff"], 3)
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


class FormConfigurationTests(APITestCase):
    URL = "/api/v1/questions/categories/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
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


class EvaluationClosingDateTests(APITestCase):
    EVALUATIONS = "/api/v1/questions/evaluations/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
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

        closed = self.client.patch(
            f"{self.EVALUATIONS}{created.data['id']}/",
            {"closes_on": "2000-01-01"},
            format="json",
        )
        self.assertEqual(closed.data["status"], "closed")

        invalid = self.client.patch(
            f"{self.EVALUATIONS}{created.data['id']}/",
            {"closes_on": "invalid-date"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

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
        first = create_user("first.target", User.Role.COLLABORATOR, area="Emergency")
        second = create_user("second.target", User.Role.COLLABORATOR, area="Emergency")
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
            {"areas": ["Emergency"], "personal_ids": [create_user("other.target", User.Role.COLLABORATOR, area="Cardiology").pk]},
            format="json",
        )
        self.assertEqual(outside_areas.status_code, 400)


class EvaluationAreaScopeTests(APITestCase):
    def test_collaborators_only_see_evaluations_for_their_area_and_cannot_bypass_scope(self):
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


class AnswersImportTests(APITestCase):
    """Answers loaded from an Excel or CSV: one row per (evaluation, collaborator, colleague)."""

    URL = "/api/v1/questions/import/"

    def setUp(self):
        Evaluation.objects.update(monthly_limit=3)  # programmed with the default quota
        self.boss = create_user("boss.demo", User.Role.BOSS)
        self.ana = create_user("1001", User.Role.COLLABORATOR)
        self.luis = create_user("1002", User.Role.COLLABORATOR)
        self.eva = create_user("1003", User.Role.COLLABORATOR)
        self.first = Evaluation.objects.get()
        self.client.force_authenticate(self.boss)
        made = self.client.post("/api/v1/questions/evaluations/", {"name": "Liderazgo"}, format="json").data
        self.second = Evaluation.objects.get(pk=made["id"])
        self.client.post(
            "/api/v1/questions/categories/",
            {"evaluation": self.second.pk, "name": "Equipo", "criteria": ["Motiva.", "Decide."]},
            format="json",
        )
        self.second_codes = list(Criterion.active(self.second).values_list("code", flat=True))

    def csv_file(self, rows, header=None):
        import csv
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile

        header = header or ["evaluation", "collaborator", "personal"] + CRITERIA + self.second_codes
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerows(rows)
        return SimpleUploadedFile("respuestas.csv", out.getvalue().encode("utf-8-sig"))

    def row(self, evaluation, collaborator, personal, score=4):
        codes = CRITERIA if evaluation == self.first.name else self.second_codes
        return [evaluation, collaborator, personal] + [score if c in codes else "" for c in CRITERIA + self.second_codes]

    def upload(self, file, **extra):
        self.client.force_authenticate(self.boss)
        return self.client.post(self.URL, {"file": file, **extra}, format="multipart")

    def test_csv_loads_each_row_into_its_own_evaluation(self):
        r = self.upload(self.csv_file([
            self.row(self.first.name, "1001", "1002"),
            self.row("Liderazgo", "1001", "1002", score=5),         # same pair, other evaluation: allowed
            self.row(str(self.second.pk), "1002", "1003"),          # evaluation by id
        ]))
        self.assertEqual((r.status_code, r.data["created"], r.data["skipped"], r.data["errors"]), (200, 3, 0, []))
        self.assertEqual(Question.objects.filter(evaluation=self.first).count(), 12)
        self.assertEqual(Question.objects.filter(evaluation=self.second).count(), 4)
        saved = Question.objects.filter(evaluation=self.first, criterion="META").get()
        self.assertEqual((saved.area, saved.score, saved.category), (self.luis.area, 4, "capacidad_de_respuesta"))
        self.assertIsNotNone(saved.reviewed_at)

    def test_never_duplicates_and_reports_each_bad_row(self):
        self.upload(self.csv_file([self.row(self.first.name, "1001", "1002")]))
        r = self.upload(self.csv_file([
            self.row(self.first.name, "1001", "1002"),               # already loaded -> skipped
            self.row(self.first.name, "1001", "1001"),               # scores themselves
            self.row(self.first.name, "9999", "1002"),               # unknown person
            self.row("No existe", "1001", "1002"),                   # unknown evaluation
            self.row(self.first.name, "1002", "1003", score=9),      # score out of range
            self.row(self.first.name, "1002", "1001", score=3),      # fine
        ]))
        self.assertEqual((r.data["created"], r.data["skipped"], len(r.data["errors"])), (1, 1, 4))
        self.assertIn("Fila 3", r.data["errors"][0])
        self.assertEqual(Question.objects.filter(evaluation=self.first).count(), 24)

    def test_default_evaluation_when_the_column_is_empty(self):
        rows = [[""] + self.row(self.first.name, "1001", "1002")[1:]]  # the evaluation cell left empty
        self.assertEqual(len(self.upload(self.csv_file(rows)).data["errors"]), 1)  # two evaluations: which one?
        ok = self.upload(self.csv_file(rows), evaluation=self.first.pk)
        self.assertEqual((ok.data["created"], ok.data["errors"]), (1, []))

    def test_excel_works_like_the_csv(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Evaluación", "Colaborador", "Evaluado"] + CRITERIA)
        ws.append([self.first.name, 1001, 1003] + [5] * 12)  # numbers, like Excel stores them
        buffer = io.BytesIO()
        wb.save(buffer)
        r = self.upload(SimpleUploadedFile("respuestas.xlsx", buffer.getvalue()))
        self.assertEqual((r.status_code, r.data["created"], r.data["errors"]), (200, 1, []))

    def test_rejects_bad_files_and_non_bosses(self):
        self.assertEqual(self.client.post(self.URL, {}, format="multipart").status_code, 400)
        from django.core.files.uploadedfile import SimpleUploadedFile

        broken = self.upload(SimpleUploadedFile("x.xlsx", b"not an excel"))
        self.assertEqual(broken.status_code, 400)
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.client.post(self.URL, {"file": self.csv_file([])}, format="multipart").status_code, 403)
