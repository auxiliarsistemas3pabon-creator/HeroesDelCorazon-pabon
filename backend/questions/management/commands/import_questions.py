"""Import evaluation forms from a CSV or Excel workbook.

Usage from Docker (repository mounted at /app):
    python manage.py import_questions data/evaluations.xlsx
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from questions.staff_import import AnswersFileError, import_evaluations, read_table


class Command(BaseCommand):
    help = "Create evaluation forms from evaluation, category and question columns."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path, help="Path to a .csv or .xlsx file, for example data/evaluations.xlsx.")

    def handle(self, *args, **options):
        path = options["file"]
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        if path.suffix.lower() not in {".csv", ".xlsx"}:
            raise CommandError("File must be .csv or .xlsx")

        try:
            with path.open("rb") as source:
                table = read_table(source, path.name)
            # All-or-nothing for the file. created_by stays None, so no boss will see these evaluations in the app (views filter
            # by created_by): assign an owner in the admin afterwards, or use the web import instead.
            with transaction.atomic():
                result = import_evaluations(table)
        except AnswersFileError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Evaluations created: {result['created']}")
        self.stdout.write(f"Evaluations already existed (skipped): {result['skipped']}")
        self.stdout.write(f"Questions created: {result['criteria_created']}")
        for name in result["evaluations_created"]:
            self.stdout.write(f"  - {name}")
        self.stdout.write(f"Rows with problems: {len(result['errors'])}")
        for error in result["errors"]:
            self.stderr.write(error)

        # Rows with errors were skipped (the rest was imported), but the exit code is still non-zero.
        if result["errors"]:
            raise CommandError("Some rows were not imported. See errors above.")
