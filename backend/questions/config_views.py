"""Vistas de configuración, programación e importación de evaluaciones.

Las escrituras administrativas requieren jefe o superadmin y respetan pertenencia del formulario.
Los registros con respuestas se conservan para no romper el historial.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.text import slugify
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.mixins import AuditLogMixin
from common.permissions import MANAGER_ROLES, IsBossOrSuperAdmin, owned_by
from users.areas import is_removed_area
from users.models import User

from .limits import monthly_limit as evaluation_limit
from .limits import scored_this_month
from .models import Category, Criterion, Evaluation, EvaluationSetting, Question
from .staff_import import (
    AnswersFileError,
    import_answers,
    import_evaluations,
    read_table,
)


# Category.code and Criterion.code are unique across all evaluations, so slugs get a numeric suffix on collision.
# `limit - 6` leaves room for the "-NN" suffix within max_length.
def _unique(model, field, base, limit):
    """`base` slug, with a number appended if it is already taken."""
    base = (slugify(base) or "item")[:limit - 6]
    value, n = base, 1
    while model.objects.filter(**{field: value}).exists():
        n += 1
        value = f"{base}-{n}"
    return value


def _clean(value):
    return " ".join(str(value or "").split())


def _next_order(model, **filters):
    return (model.objects.filter(**filters).aggregate(m=Max("order"))["m"] or 0) + 1


# The `used` flags (has scores) tell the UI whether an item can be deleted or can only be deactivated.
def _listing(evaluation):
    """The categories (with their criteria) of one evaluation."""
    used_criteria = set(Question.objects.filter(evaluation=evaluation).values_list("criterion", flat=True).distinct())
    used_categories = set(Question.objects.filter(evaluation=evaluation).values_list("category", flat=True).distinct())
    return [
        {
            "id": category.pk,
            "code": category.code,
            "name": category.name,
            "is_active": category.is_active,
            "used": category.code in used_categories,
            "criteria": [
                {"id": c.pk, "code": c.code, "name": c.name, "is_active": c.is_active, "used": c.code in used_criteria}
                for c in category.criteria.all()
            ],
        }
        for category in evaluation.categories.prefetch_related("criteria")
    ]


def _evaluation_data(evaluation):
    answers = evaluation.questions.values("collaborator", "personal", "created_at__date").distinct().count()
    evaluators = User.objects.filter(pk__in=evaluation.questions.values("collaborator")).order_by("first_name", "last_name", "username")
    return {
        "id": evaluation.pk,
        "name": evaluation.name,
        "evaluated_by": [user.get_full_name() or user.username for user in evaluators],
        "rating_type": evaluation.rating_type,
        "is_available": evaluation.is_available,
        "random_selection": evaluation.random_selection,
        "evaluator_ids": evaluation.evaluator_ids,
        "closes_on": evaluation.closes_on.isoformat() if evaluation.closes_on else None,
        "areas": evaluation.areas,
        "personal_ids": evaluation.personal_ids,
        "status": evaluation.status,
        "answers": answers,
        "used": evaluation.questions.exists(),
        "categories": evaluation.categories.count(),
        "criteria": Criterion.objects.filter(category__evaluation=evaluation, is_active=True).count(),
    }


# Reading is open to every boss; writing (write=True) only reaches evaluations they created (None otherwise,
# which callers report as invalid). A superadmin is never restricted.
def _evaluation_of(raw, user, write=False):
    evaluations = Evaluation.objects.filter(pk=raw) if str(raw or "").isdigit() else Evaluation.objects.none()
    if write:
        evaluations = evaluations.filter(**owned_by(user))
    return evaluations.first()


def _clean_evaluator_ids(raw, areas):
    """List of ids of active collaborators (inside `areas`, None = any) or None when the value is invalid. [] = everyone."""
    if not isinstance(raw, list) or any(not isinstance(pk, int) or isinstance(pk, bool) or pk < 1 for pk in raw):
        return None
    ids = list(dict.fromkeys(raw))
    found = User.objects.filter(pk__in=ids, role=User.Role.COLLABORATOR, is_active=True).exclude(area="")
    if found.count() != len(ids):
        return None
    if any(areas is not None and area not in areas for area in found.values_list("area", flat=True)):
        return None
    return ids


def _bad(field, message):
    return Response({field: [message]}, status=status.HTTP_400_BAD_REQUEST)


def _closed(evaluation, user):
    """403 response when the evaluation is closed (manually or past closes_on) and `user` is not a superadmin;
    None if it can still be edited. Only a superadmin may touch a closed evaluation."""
    if evaluation.status == "closed" and user.role != User.Role.SUPERADMIN:
        return Response(
            {"detail": _("Closed evaluations are read-only.")},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _apply_changes(obj, data):
    """Applies the optional `name` / `is_active` of a PATCH. Returns an error response or None.

    Turning a category/question ON adds it to the form. Categories and questions may be added at any point;
    submitted answers keep the values they had when they were sent.
    """
    if "name" in data:
        name = _clean(data["name"])
        if not name:
            return _bad("name", _("Enter a name."))
        obj.name = name
    if "is_active" in data:
        obj.is_active = bool(data["is_active"])
    obj.save()
    return None


class EvaluationsView(AuditLogMixin, APIView):
    """GET/POST /questions/evaluations/: lista evaluaciones visibles o crea un formulario independiente.

    Los colaboradores reciben solo formularios abiertos que correspondan a su área/elegibilidad, con su cupo.
    Jefes y superadmins pueden crear formularios con categorías y criterios; las escrituras las audita AuditLogMixin.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Collaborators: only open evaluations of their area that include someone of that area. `remaining` is their
        # leftover monthly quota and personal_ids is trimmed to people of their own area.
        evaluations = Evaluation.objects.all()
        area_person_ids = set()
        if request.user.role not in MANAGER_ROLES:
            evaluations = evaluations.available()
            if not request.user.area:
                evaluations = evaluations.none()
            else:
                area_person_ids = set(
                    User.objects.filter(
                        role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL],
                        is_active=True,
                        area=request.user.area,
                    ).values_list("pk", flat=True)
                )
                evaluations = [
                    evaluation for evaluation in evaluations
                    if (evaluation.areas is None or request.user.area in evaluation.areas)
                    and (not evaluation.evaluator_ids or request.user.pk in evaluation.evaluator_ids)
                    and (not evaluation.personal_ids or area_person_ids.intersection(evaluation.personal_ids))
                ]
        else:
            # A boss sees every evaluation (editing is still limited to the ones they created).
            if request.query_params.get("mine") == "1":
                evaluations = evaluations.filter(questions__isnull=False)
            evaluations = evaluations.distinct()
        data = [_evaluation_data(e) for e in evaluations]
        if request.user.role not in MANAGER_ROLES:
            for evaluation, item in zip(evaluations, data):
                item["remaining"] = max(0, evaluation_limit(evaluation) - len(scored_this_month(request.user, evaluation)))
            for item in data:
                if item["personal_ids"]:
                    item["personal_ids"] = [personal_id for personal_id in item["personal_ids"] if personal_id in area_person_ids]
        return Response(data)

    @transaction.atomic
    def post(self, request):
        if request.user.role not in MANAGER_ROLES:
            return Response(status=status.HTTP_403_FORBIDDEN)
        name = _clean(request.data.get("name"))
        if not name:
            return _bad("name", _("Enter a name."))
        rating_type = request.data.get("rating_type", Evaluation.RatingType.QUANTITATIVE)
        if rating_type not in Evaluation.RatingType.values:
            return _bad("rating_type", _("Choose quantitative or descriptive ratings."))
        categories = request.data.get("categories", [])
        if not isinstance(categories, list):
            return _bad("categories", _("Enter a list of categories."))
        cleaned = []
        for item in categories:
            if not isinstance(item, dict):
                return _bad("categories", _("Each category must have a name and questions."))
            category_name = _clean(item.get("name"))
            raw = item.get("criteria")
            questions = [_clean(q) for q in raw] if isinstance(raw, list) else []
            questions = [q for q in questions if q]
            if not category_name or not questions:
                return _bad("categories", _("Each category needs a name and at least one question."))
            cleaned.append((category_name, questions))

        evaluation = Evaluation.objects.create(name=name, rating_type=rating_type, created_by=request.user)
        for category_name, questions in cleaned:
            category = Category.objects.create(
                evaluation=evaluation,
                name=category_name,
                code=_unique(Category, "code", category_name, 50),
                order=_next_order(Category, evaluation=evaluation),
            )
            for number, text in enumerate(questions, start=1):
                Criterion.objects.create(
                    category=category,
                    name=text,
                    order=number,
                    code=_unique(Criterion, "code", text, 50),
                )
        return Response(_evaluation_data(evaluation), status=status.HTTP_201_CREATED)


class EvaluationDetailView(AuditLogMixin, APIView):
    """PATCH/DELETE /questions/evaluations/<id>/: edita, cierra o elimina una evaluación sin respuestas.

    El jefe solo modifica sus evaluaciones. Reprogramar inicia una nueva ronda; una evaluación con respuestas
    no puede eliminarse, para preservar el historial.
    """

    permission_classes = [IsBossOrSuperAdmin]

    def patch(self, request, pk):
        evaluation = Evaluation.objects.filter(pk=pk, **owned_by(request.user)).first()
        if evaluation is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(evaluation, request.user)
        if closed_response:
            return closed_response
        if "name" in request.data:
            name = _clean(request.data["name"])
            if not name:
                return _bad("name", _("Enter a name."))
            evaluation.name = name
        if "rating_type" in request.data:
            rating_type = request.data["rating_type"]
            if rating_type not in Evaluation.RatingType.values:
                return _bad("rating_type", _("Choose quantitative or descriptive ratings."))
            evaluation.rating_type = rating_type
        # "Reprogramming" (reopening, new closing date, areas or people) stamps program_started_at below, which starts a new
        # round: collaborators can score the same people again even in the same month (see limits.scored_this_month).
        reprogrammed = False
        if "is_available" in request.data:
            is_available = bool(request.data["is_available"])
            reprogrammed = is_available and not evaluation.is_available
            evaluation.is_available = is_available
        if "closes_on" in request.data:
            raw_closes_on = request.data["closes_on"]
            closes_on = parse_date(raw_closes_on) if isinstance(raw_closes_on, str) else None
            if raw_closes_on is not None and closes_on is None:
                return _bad("closes_on", _("Enter a valid closing date."))
            reprogrammed = reprogrammed or closes_on != evaluation.closes_on
            evaluation.closes_on = closes_on
        if "areas" in request.data:
            areas = request.data["areas"]
            if areas is not None and (
                not isinstance(areas, list)
                or any(not isinstance(area, str) or not area.strip() for area in areas)
            ):
                return _bad("areas", _("Choose a list of areas."))
            if areas is not None:
                areas = list(dict.fromkeys(area.strip() for area in areas))
                known_areas = set(
                    User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True)
                    .exclude(area="")
                    .values_list("area", flat=True)
                    .distinct()
                )
                known_areas = {area for area in known_areas if not is_removed_area(area)}
                unknown_areas = set(areas) - known_areas
                if unknown_areas:
                    return _bad("areas", _("Choose areas that exist in the staff list."))
            reprogrammed = reprogrammed or areas != evaluation.areas
            evaluation.areas = areas
        if "personal_ids" in request.data:
            personal_ids = request.data["personal_ids"]
            if (
                not isinstance(personal_ids, list)
                or any(not isinstance(personal_id, int) or isinstance(personal_id, bool) or personal_id < 1
                       for personal_id in personal_ids)
            ):
                return _bad("personal_ids", _("Choose a list of staff members."))
            personal_ids = list(dict.fromkeys(personal_ids))
            staff = User.objects.filter(
                pk__in=personal_ids,
                role=User.Role.PERSONAL,
                is_active=True,
            ).exclude(area="")
            if staff.count() != len(personal_ids):
                return _bad("personal_ids", _("Choose active staff members from the staff list."))
            areas = evaluation.areas
            if any(areas is not None and area not in areas for area in staff.values_list("area", flat=True)):
                return _bad("personal_ids", _("Choose staff members from the selected areas."))
            reprogrammed = reprogrammed or personal_ids != evaluation.personal_ids
            evaluation.personal_ids = personal_ids
        if "evaluator_ids" in request.data:
            evaluator_ids = _clean_evaluator_ids(request.data["evaluator_ids"], evaluation.areas)
            if evaluator_ids is None:
                return _bad("evaluator_ids", _("Choose active collaborators from the selected areas."))
            reprogrammed = reprogrammed or evaluator_ids != evaluation.evaluator_ids
            evaluation.evaluator_ids = evaluator_ids
        if "random_selection" in request.data:
            random_selection = bool(request.data["random_selection"])
            reprogrammed = reprogrammed or random_selection != evaluation.random_selection
            evaluation.random_selection = random_selection
        if reprogrammed:
            evaluation.program_started_at = timezone.now()
        evaluation.save()
        return Response(_evaluation_data(evaluation))

    @transaction.atomic
    def delete(self, request, pk):
        evaluation = Evaluation.objects.filter(pk=pk, **owned_by(request.user)).first()
        if evaluation is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(evaluation, request.user)
        if closed_response:
            return closed_response
        if evaluation.questions.exists():
            return Response(
                {"detail": _("This evaluation has answers: close it instead of deleting it.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Category/Criterion are PROTECTed by FK, so children are deleted explicitly before the evaluation.
        Criterion.objects.filter(category__evaluation=evaluation).delete()
        evaluation.categories.all().delete()
        evaluation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EvaluationProgramCreateView(AuditLogMixin, APIView):
    """POST /questions/evaluations/<id>/programs/: crea una copia independiente ya programada."""

    permission_classes = [IsBossOrSuperAdmin]

    @transaction.atomic
    def post(self, request, pk):
        source = Evaluation.objects.filter(pk=pk, **owned_by(request.user)).first()
        if source is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        raw_closes_on = request.data.get("closes_on")
        closes_on = parse_date(raw_closes_on) if isinstance(raw_closes_on, str) else None
        if closes_on is None:
            return _bad("closes_on", _("Enter a valid closing date."))

        areas = request.data.get("areas")
        if areas is not None and (
            not isinstance(areas, list)
            or any(not isinstance(area, str) or not area.strip() for area in areas)
        ):
            return _bad("areas", _("Choose a list of areas."))
        if areas is not None:
            areas = list(dict.fromkeys(area.strip() for area in areas))
            known_areas = set(
                User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True)
                .exclude(area="")
                .values_list("area", flat=True)
                .distinct()
            )
            known_areas = {area for area in known_areas if not is_removed_area(area)}
            if set(areas) - known_areas:
                return _bad("areas", _("Choose areas that exist in the staff list."))

        personal_ids = request.data.get("personal_ids", [])
        if (
            not isinstance(personal_ids, list)
            or any(
                not isinstance(personal_id, int) or isinstance(personal_id, bool) or personal_id < 1
                for personal_id in personal_ids
            )
        ):
            return _bad("personal_ids", _("Choose a list of staff members."))
        personal_ids = list(dict.fromkeys(personal_ids))
        staff = User.objects.filter(
            pk__in=personal_ids,
            role=User.Role.PERSONAL,
            is_active=True,
        ).exclude(area="")
        if staff.count() != len(personal_ids):
            return _bad("personal_ids", _("Choose active staff members from the staff list."))
        if any(areas is not None and area not in areas for area in staff.values_list("area", flat=True)):
            return _bad("personal_ids", _("Choose staff members from the selected areas."))

        evaluator_ids = _clean_evaluator_ids(request.data.get("evaluator_ids", []), areas)
        if evaluator_ids is None:
            return _bad("evaluator_ids", _("Choose active collaborators from the selected areas."))

        monthly_limit = request.data.get("monthly_limit")
        if (
            not isinstance(monthly_limit, int)
            or isinstance(monthly_limit, bool)
            or not 1 <= monthly_limit <= EvaluationSetting.MAX_MONTHLY_LIMIT
        ):
            return _bad("monthly_limit", _("Enter a whole number between 1 and 30."))

        # The copy is a new, independent evaluation (answers are NOT copied); codes get new unique slugs below.
        programmed = Evaluation.objects.create(
            name=source.name,
            rating_type=source.rating_type,
            created_by=request.user,
            is_available=True,
            closes_on=closes_on,
            areas=areas,
            personal_ids=personal_ids,
            monthly_limit=monthly_limit,
            random_selection=bool(request.data.get("random_selection", False)),
            evaluator_ids=evaluator_ids,
            program_started_at=timezone.now(),
        )
        for source_category in source.categories.prefetch_related("criteria"):
            category = Category.objects.create(
                evaluation=programmed,
                name=source_category.name,
                code=_unique(Category, "code", source_category.code, 50),
                order=source_category.order,
                is_active=source_category.is_active,
            )
            for source_criterion in source_category.criteria.all():
                Criterion.objects.create(
                    category=category,
                    name=source_criterion.name,
                    code=_unique(Criterion, "code", source_criterion.code, 50),
                    order=source_criterion.order,
                    is_active=source_criterion.is_active,
                )

        return Response(_evaluation_data(programmed), status=status.HTTP_201_CREATED)


class CategoriesView(AuditLogMixin, APIView):
    """GET/POST /questions/categories/: consulta categorías o crea una con criterios en una evaluación.

    GET exige ?evaluation=<id>. POST requiere evaluation, name y una lista criteria; no altera otros formularios.
    Solo un jefe/superadmin con acceso de escritura puede modificar la evaluación.
    """

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        evaluation = _evaluation_of(request.query_params.get("evaluation"), request.user)
        if evaluation is None:
            return _bad("evaluation", _("Choose an evaluation."))
        return Response(_listing(evaluation))

    @transaction.atomic
    def post(self, request):
        evaluation = _evaluation_of(request.data.get("evaluation"), request.user, write=True)
        if evaluation is None:
            return _bad("evaluation", _("Choose an evaluation."))
        closed_response = _closed(evaluation, request.user)
        if closed_response:
            return closed_response
        if evaluation.questions.exists():
            return _bad("evaluation", _("An evaluation with answers cannot be changed."))
        name = _clean(request.data.get("name"))
        raw = request.data.get("criteria")
        questions = [_clean(q) for q in raw] if isinstance(raw, list) else []
        questions = [q for q in questions if q]
        if not name:
            return _bad("name", _("Enter a name."))
        if not questions:
            return _bad("criteria", _("Add at least one question to the category."))

        category = Category.objects.create(
            evaluation=evaluation,
            name=name,
            code=_unique(Category, "code", name, 50),
            order=_next_order(Category, evaluation=evaluation),
        )
        for number, text in enumerate(questions, start=1):
            Criterion.objects.create(
                category=category, name=text, order=number, code=_unique(Criterion, "code", text, 50)
            )
        return Response(_listing(evaluation), status=status.HTTP_201_CREATED)


class CategoryDetailView(AuditLogMixin, APIView):
    """PATCH/DELETE /questions/categories/<id>/: actualiza, desactiva o elimina una categoría sin respuestas."""

    permission_classes = [IsBossOrSuperAdmin]

    def patch(self, request, pk):
        category = Category.objects.filter(pk=pk, **owned_by(request.user, "evaluation__created_by")).first()
        if category is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(category.evaluation, request.user)
        if closed_response:
            return closed_response
        if (
            request.data.get("is_active") is True
            and not category.is_active
            and Question.objects.filter(category=category.code).exists()
        ):
            return _bad("is_active", _("A category with answers cannot be reactivated."))
        return _apply_changes(category, request.data) or Response(_listing(category.evaluation))

    @transaction.atomic
    def delete(self, request, pk):
        category = Category.objects.filter(pk=pk, **owned_by(request.user, "evaluation__created_by")).first()
        if category is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(category.evaluation, request.user)
        if closed_response:
            return closed_response
        # Question links to categories/criteria by code text, hence this lookup instead of a reverse FK.
        if Question.objects.filter(category=category.code).exists():
            return Response(
                {"detail": _("This category has evaluations: deactivate it instead of deleting it.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        evaluation = category.evaluation
        category.criteria.all().delete()
        category.delete()
        return Response(_listing(evaluation))


class CategoryCriteriaView(AuditLogMixin, APIView):
    """POST /questions/categories/<id>/criteria/: agrega un criterio antes de que haya respuestas."""

    permission_classes = [IsBossOrSuperAdmin]

    def post(self, request, pk):
        category = Category.objects.filter(pk=pk, **owned_by(request.user, "evaluation__created_by")).first()
        if category is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(category.evaluation, request.user)
        if closed_response:
            return closed_response
        if category.evaluation.questions.exists():
            return _bad("evaluation", _("An evaluation with answers cannot be changed."))
        text = _clean(request.data.get("name"))
        if not text:
            return _bad("name", _("Enter a name."))
        Criterion.objects.create(
            category=category,
            name=text,
            code=_unique(Criterion, "code", text, 50),
            order=_next_order(Criterion, category=category),
        )
        return Response(_listing(category.evaluation), status=status.HTTP_201_CREATED)


class CriterionDetailView(AuditLogMixin, APIView):
    """PATCH/DELETE /questions/criteria/<id>/: actualiza, desactiva o elimina un criterio sin respuestas."""

    permission_classes = [IsBossOrSuperAdmin]

    def patch(self, request, pk):
        criterion = Criterion.objects.filter(pk=pk, **owned_by(request.user, "category__evaluation__created_by")).first()
        if criterion is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(criterion.category.evaluation, request.user)
        if closed_response:
            return closed_response
        if (
            request.data.get("is_active") is True
            and not criterion.is_active
            and Question.objects.filter(criterion=criterion.code).exists()
        ):
            return _bad("is_active", _("A question with answers cannot be reactivated."))
        return _apply_changes(criterion, request.data) or Response(_listing(criterion.category.evaluation))

    def delete(self, request, pk):
        criterion = Criterion.objects.filter(pk=pk, **owned_by(request.user, "category__evaluation__created_by")).first()
        if criterion is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        closed_response = _closed(criterion.category.evaluation, request.user)
        if closed_response:
            return closed_response
        if Question.objects.filter(criterion=criterion.code).exists():
            return Response(
                {"detail": _("This question has evaluations: deactivate it instead of deleting it.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        evaluation = criterion.category.evaluation
        criterion.delete()
        return Response(_listing(evaluation))


class EvaluationImportView(AuditLogMixin, APIView):
    """POST /questions/import/: jefe o superadmin importa formularios desde Excel o CSV.

    Cada fila indica evaluación, categoría y criterio; evaluaciones existentes se omiten.
    Los errores de lectura producen HTTP 400 y la operación de importación se ejecuta en una transacción.
    """

    permission_classes = [IsBossOrSuperAdmin]
    # Imported evaluations are owned by the requesting boss (created_by); the whole file is processed in one transaction.
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if file is None:
            return _bad("file", _("Attach an Excel (.xlsx) or CSV file."))
        try:
            table = read_table(file, file.name)
            with transaction.atomic():
                result = import_evaluations(table, created_by=request.user)
        except AnswersFileError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class AnswersImportView(AuditLogMixin, APIView):
    """POST /questions/answers/import/: jefe o superadmin carga entregas desde Excel o CSV."""

    permission_classes = [IsBossOrSuperAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if file is None:
            return _bad("file", _("Attach an Excel (.xlsx) or CSV file."))
        raw_evaluation = request.data.get("evaluation")
        default_evaluation = None
        if raw_evaluation not in (None, ""):
            default_evaluation = _evaluation_of(raw_evaluation, request.user)
            if default_evaluation is None:
                return _bad("evaluation", _("Choose an evaluation."))
        try:
            table = read_table(file, file.name)
            result = import_answers(table, default_evaluation)
        except AnswersFileError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
