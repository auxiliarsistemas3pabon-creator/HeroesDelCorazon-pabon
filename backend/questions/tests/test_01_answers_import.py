from rest_framework.test import APITestCase

from users.models import User

from ..models import Criterion, Evaluation, Question
from .helpers import CRITERIA, create_user


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
