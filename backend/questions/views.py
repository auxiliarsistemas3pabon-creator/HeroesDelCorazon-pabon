from django.db import transaction
from django.db.models import Avg, Count, Max
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import MANAGER_ROLES, IsBossOrSuperAdmin, owned_by, IsCollaborator
from users.models import User

from .limits import assigned_personal, find_evaluation, monthly_limit, scored_this_month
from .models import Category, Evaluation, EvaluationSetting, Question
from .notifications import notify_review
from .serializers import QuestionCreateSerializer, QuestionSerializer


# Averages are rounded to 1 decimal; None (no data) is kept so the UI can show "-" instead of 0.
def _avg(value):
    return round(value, 1) if value is not None else None


def _bad(field, message):
    return Response({field: [message]}, status=status.HTTP_400_BAD_REQUEST)


# "Approved" = reviewed_at set. New answers get it on creation, so every submitted answer counts;
# the filter stays so unreviewed legacy rows never count.
def _approved():
    return Question.objects.filter(reviewed_at__isnull=False)


def _boss_evaluations(user):
    return Evaluation.objects.all()


# Bosses and superadmins see the answers of every evaluation (no per-boss isolation).
def _boss_questions(user, qs=None):
    return qs if qs is not None else Question.objects.all()


def _date(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def _in_range(request, qs, field="created_at"):
    """Optional ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD filter (both days included) on `field`."""
    start = _date(request.query_params.get("date_from"))
    end = _date(request.query_params.get("date_to"))
    if start:
        qs = qs.filter(**{f"{field}__date__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__date__lte": end})
    return qs

class QuestionFormView(APIView):
    """Categories and criteria of ONE evaluation (?evaluation=<id>; optional when there is a single open one).

    Only the active ones, unless ?include_inactive=1. The read-only tables (review, results) ask for the
    inactive ones too (and for closed evaluations) to show old evaluations. A collaborator only gets the
    form of an open evaluation to answer it.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        everything = request.query_params.get("include_inactive") == "1"
        # Collaborators only get open evaluations; the boss (or include_inactive=1) can also read closed ones for history.
        # Access is narrowed below: a boss only sees their own evaluations, a collaborator only those available to their area.
        open_only = not (everything or request.user.role in MANAGER_ROLES)
        evaluation = find_evaluation(request.query_params.get("evaluation"), open_only=open_only)
        if (
            evaluation
            and request.user.role not in MANAGER_ROLES
            and (
                not request.user.area
                or (evaluation.areas is not None and request.user.area not in evaluation.areas)
            )
        ):
            evaluation = None
        if evaluation is None:
            return Response([])

        data = []
        for category in evaluation.categories.prefetch_related("criteria"):
            if not everything and not category.is_active:
                continue
            criteria = [c for c in category.criteria.all() if everything or c.is_active]
            if criteria:
                data.append({
                    "code": category.code,
                    "name": category.name,
                    "criteria": [{"code": c.code, "name": c.name} for c in criteria],
                })
        return Response(data)


class QuestionsView(APIView):
    """GET: the boss sees every score, a collaborator only the approved ones they received.
    POST: a collaborator scores a colleague of their area (12 criteria)."""

    # Only collaborators may submit scores; any authenticated user may read (the queryset is filtered by role in get()).
    def get_permissions(self):
        return [IsCollaborator()] if self.request.method == "POST" else [IsAuthenticated()]

    def get(self, request):
        qs = Question.objects.select_related("personal").order_by("-created_at", "id")
        if request.user.role in MANAGER_ROLES:
            qs = _boss_questions(request.user, qs)
        else:
            qs = qs.filter(personal=request.user, reviewed_at__isnull=False)
        return Response(QuestionSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = QuestionCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        # The evaluation counts as soon as it is sent: the boss only consults it.
        # average = overall score of the evaluated person (score 0 = not applicable, excluded). The email goes out after commit.
        average = _avg(_approved().filter(personal=created[0].personal).exclude(score=0).aggregate(a=Avg("score"))["a"])
        transaction.on_commit(lambda: notify_review(created[0].personal, average))
        return Response(QuestionSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


# Question rows are one-per-criterion; a "submission" is rebuilt by grouping on (evaluation, collaborator, personal, day).
# Trap: two submissions of the same pair on the same day would merge (the monthly quota normally prevents it).
def _grouped(qs):
    """Groups the scores into submissions (collaborator -> staff member, 12 scores), newest first."""
    groups = {}
    for q in qs.select_related("collaborator", "personal", "evaluation").order_by("-created_at", "id"):
        group = groups.setdefault((q.evaluation_id, q.collaborator_id, q.personal_id, q.created_at.date()), {
            "evaluation": q.evaluation_id,
            "evaluation_name": q.evaluation.name,
            "rating_type": q.evaluation.rating_type,
            "collaborator": q.collaborator_id,
            "collaborator_name": q.collaborator.get_full_name(),
            "personal": q.personal_id,
            "personal_name": q.personal.get_full_name(),
            "area": q.area,
            "created_at": q.created_at,
            "answers": [],
        })
        group["answers"].append({"category": q.category, "criterion": q.criterion, "score": q.score})

    for group in groups.values():
        # score 0 means "does not apply" and is excluded from the average.
        scores = [a["score"] for a in group["answers"] if a["score"] > 0]
        group["average"] = _avg(sum(scores) / len(scores)) if scores else None
    return list(groups.values())


class SubmissionsView(APIView):
    """Evaluations sent by the collaborators, newest first.

    Read-only for the boss: an evaluation counts as soon as it is sent.
    """

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        qs = _boss_questions(request.user)
        raw_evaluation = request.query_params.get("evaluation")
        if raw_evaluation and raw_evaluation != "all":
            if not raw_evaluation.isdigit():
                return _bad("evaluation", _("Choose an evaluation."))
            qs = qs.filter(evaluation_id=raw_evaluation)
        raw_personal = request.query_params.get("personal")
        if raw_personal:
            if not raw_personal.isdigit():
                return _bad("personal", _("Choose a person."))
            qs = qs.filter(personal_id=raw_personal)
        if request.user.area:
            qs = qs.filter(personal__area=request.user.area)
        return Response(_grouped(qs))


class SentView(APIView):
    """The evaluations the logged collaborator has sent, newest first."""

    permission_classes = [IsCollaborator]

    def get(self, request):
        return Response(_grouped(Question.objects.filter(collaborator=request.user)))


class ResultsView(APIView):
    """Final score (average of the scores) of the logged user: overall and, for each evaluation, by category."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _approved().filter(personal=request.user)
        scored_qs = qs.exclude(score=0)
        by_category = {
            (row["evaluation"], row["category"]): _avg(row["a"])
            for row in scored_qs.values("evaluation", "category").annotate(a=Avg("score"))
        }
        by_evaluation = {row["evaluation"]: _avg(row["a"]) for row in scored_qs.values("evaluation").annotate(a=Avg("score"))}

        evaluations = []
        for evaluation in Evaluation.objects.filter(pk__in=qs.values("evaluation").distinct()):
            evaluations.append({
                "id": evaluation.pk,
                "name": evaluation.name,
                "rating_type": evaluation.rating_type,
                "average": by_evaluation.get(evaluation.pk),
                "by_category": [
                    {"code": c.code, "name": c.name, "average": by_category[(evaluation.pk, c.code)]}
                    for c in evaluation.categories.all() if (evaluation.pk, c.code) in by_category
                ],
            })
        return Response({
            "average": _avg(scored_qs.aggregate(a=Avg("score"))["a"]),
            "evaluations": evaluations,
        })


class ResultsSummaryView(APIView):
    """Boss: scores for their own evaluations, by category and overall, for one or all (?evaluation=all).

    Without ?evaluation it uses the first evaluation that has answers. The boss of an area only sees people of it.
    """

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        evaluations = _boss_evaluations(request.user)
        raw = request.query_params.get("evaluation")
        all_evaluations = raw == "all"
        if all_evaluations:
            evaluation = None
        elif raw:
            evaluation = evaluations.filter(pk=raw).first() if raw.isdigit() else None
        else:
            evaluation = evaluations.filter(questions__isnull=False).distinct().first() or evaluations.first()
        if evaluation is None and not all_evaluations:
            return Response({"evaluation": None, "categories": [], "rows": []})

        qs = _boss_questions(request.user, _approved()) if all_evaluations else _boss_questions(request.user, _approved()).filter(evaluation=evaluation)
        if request.user.area:
            qs = qs.filter(personal__area=request.user.area)
        qs = _in_range(request, qs)

        scored_qs = qs.exclude(score=0)
        scores = {}
        for row in scored_qs.values("personal", "category").annotate(a=Avg("score")):
            scores.setdefault(row["personal"], {})[row["category"]] = _avg(row["a"])
        overall = {row["personal"]: _avg(row["a"]) for row in scored_qs.values("personal").annotate(a=Avg("score"))}

        # Fecha de realización: la evaluación más reciente de la persona dentro del filtro (día local).
        performed = {
            row["personal"]: timezone.localtime(row["last"]).date().isoformat()
            for row in qs.values("personal").annotate(last=Max("created_at"))
        }

        people = User.objects.filter(pk__in=qs.values("personal"), role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL]).order_by("first_name", "last_name")
        categories = (
            Category.objects.all()
            if all_evaluations else evaluation.categories.all()
        )
        return Response({
            "evaluation": None if all_evaluations else {"id": evaluation.pk, "name": evaluation.name},
            "categories": [{"code": c.code, "name": c.name} for c in categories],
            "rows": [
                {
                    "personal": p.pk,
                    "name": p.get_full_name(),
                    "area": p.area,
                    "position": p.position,
                    "by_category": scores.get(p.pk, {}),
                    "average": overall.get(p.pk),
                    "performed_at": performed.get(p.pk),
                }
                for p in people
            ],
        })


class CategoryAveragesView(APIView):
    """Boss: average of the scores by category, for one person (?personal=<id>) and/or one evaluation
    (?evaluation=<id>); without them, for everyone and every evaluation."""

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        qs = _boss_questions(request.user, _approved())
        categories = Category.objects.all()
        if request.query_params.get("mine") == "1":
            categories = categories.filter(evaluation__questions__isnull=False)
            if request.user.area:
                categories = categories.filter(
                    evaluation_id__in=_boss_evaluations(request.user)
                    .filter(questions__area=request.user.area)
                    .values("pk")
                ).distinct()
            categories = categories.distinct()
        if request.user.area:
            qs = qs.filter(personal__area=request.user.area)
        qs = _in_range(request, qs)
        personal = request.query_params.get("personal")
        if personal:
            qs = qs.filter(personal_id=personal) if personal.isdigit() else qs.none()
        area = request.query_params.get("area")
        if area:
            qs = qs.filter(personal__area=area)
        position = request.query_params.get("position")
        if position:
            qs = qs.filter(personal__position=position)
        evaluation = request.query_params.get("evaluation")
        if evaluation:
            valid = evaluation.isdigit()
            qs = qs.filter(evaluation_id=evaluation) if valid else qs.none()
            categories = categories.filter(evaluation_id=evaluation) if valid else categories.none()

        scored_qs = qs.exclude(score=0)
        by_category = {row["category"]: _avg(row["a"]) for row in scored_qs.values("category").annotate(a=Avg("score"))}
        return Response({
            "average": _avg(scored_qs.aggregate(a=Avg("score"))["a"]),
            "by_category": [
                {"code": c.code, "name": c.name, "average": by_category.get(c.code)}
                for c in categories
                if c.is_active or c.code in by_category
            ],
        })


# Scope: a boss with an area only sees people of that area; a boss without area only counts people already evaluated
# in their own evaluations (hence the pk__in filter on own_answers below).
class StatsView(APIView):
    """Count of evaluated (approved) vs pending collaborators, total and per area, for the dashboard."""

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        own_answers = _in_range(request, _boss_questions(request.user, _approved()))
        collaborators = User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True)
        if request.user.area:
            collaborators = collaborators.filter(area=request.user.area)
        else:
            collaborators = collaborators.filter(
                pk__in=own_answers.values("personal_id")
            )

        evaluated_ids = set(
            own_answers.filter(personal__in=collaborators).values_list("personal_id", flat=True)
        )
        by_area = {}
        for pk, area in collaborators.values_list("pk", "area"):
            name = area or "-"
            row = by_area.setdefault(name, {"area": name, "evaluated": 0, "pending": 0})
            row["evaluated" if pk in evaluated_ids else "pending"] += 1

        total = collaborators.count()
        return Response({
            "total": total,
            "evaluated": len(evaluated_ids),
            "pending": total - len(evaluated_ids),
            "by_area": sorted(by_area.values(), key=lambda r: r["area"]),
        })


class SettingsView(APIView):
    """Boss: reads and sets a monthly colleague limit globally or for one evaluation."""

    permission_classes = [IsBossOrSuperAdmin]

    def get(self, request):
        raw = request.query_params.get("evaluation")
        evaluation = Evaluation.objects.filter(pk=raw).first() if raw and raw.isdigit() else None
        if raw and evaluation is None:
            return _bad("evaluation", _("Choose an evaluation."))
        data = {"monthly_limit": monthly_limit(evaluation)}
        if evaluation:
            data["evaluation"] = evaluation.pk
        return Response(data)

    # Without `evaluation` this writes the global EvaluationSetting row, the default used by limits.monthly_limit.
    def put(self, request):
        raw = request.data.get("evaluation", request.query_params.get("evaluation"))
        evaluation = Evaluation.objects.filter(pk=raw, **owned_by(request.user)).first() if raw and str(raw).isdigit() else None
        if raw and evaluation is None:
            return _bad("evaluation", _("Choose an evaluation."))
        try:
            value = int(request.data.get("monthly_limit"))
        except (TypeError, ValueError):
            value = 0
        if not 1 <= value <= EvaluationSetting.MAX_MONTHLY_LIMIT:
            return Response(
                {"monthly_limit": [_("Enter a whole number between 1 and %(max)s.") % {"max": EvaluationSetting.MAX_MONTHLY_LIMIT}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if evaluation:
            evaluation.monthly_limit = value
            evaluation.save(update_fields=["monthly_limit"])
        else:
            setting = EvaluationSetting.current()
            setting.monthly_limit = value
            setting.save(update_fields=["monthly_limit"])
        data = {"monthly_limit": value}
        if evaluation:
            data["evaluation"] = evaluation.pk
        return Response(data)


class QuotaView(APIView):
    """How many colleagues the collaborator can still score this month in an evaluation (?evaluation=<id>),
    and who was already scored."""

    permission_classes = [IsCollaborator]

    def get(self, request):
        evaluation = find_evaluation(request.query_params.get("evaluation"))
        done = scored_this_month(request.user, evaluation) if evaluation else set()
        return Response({
            "evaluation": evaluation.pk if evaluation else None,
            "limit": monthly_limit(evaluation),
            "used": len(done),
            "personal": sorted(done),
            # Random-selection evaluations: the fixed people the system assigned to this collaborator.
            "assigned": assigned_personal(request.user, evaluation) if evaluation and evaluation.random_selection else None,
        })


# Scope trap: the boss branch counts only collaborators, while the collaborator branch counts every active user
# (bosses included) of their own area.
class DashboardView(APIView):
    """Staff and evaluated-people counts (per area and overall) for the dashboard of both roles.

    evaluated = distinct people who already have an evaluation (a score reviewed by the boss).
    Optional ?date_from / ?date_to (YYYY-MM-DD): the evaluations are the ones sent in that range and
    the staff are the users registered in that range.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff = {}
        own_answers = _in_range(request, _boss_questions(request.user, _approved()))
        if request.user.role in MANAGER_ROLES:
            users = _in_range(
                request,
                User.objects.filter(is_active=True, role=User.Role.COLLABORATOR),
                field="date_joined",
            )
            if request.user.area:
                users = users.filter(area=request.user.area)
        else:
            users = _in_range(request, User.objects.filter(is_active=True), field="date_joined")
            if request.user.area:
                users = users.filter(area=request.user.area)
        for row in users.values("area").annotate(n=Count("id")):
            staff[row["area"] or "-"] = row["n"]

        evaluated = {}
        for row in own_answers.filter(personal__in=users).values("area").annotate(n=Count("personal", distinct=True)):
            evaluated[row["area"] or "-"] = row["n"]

        areas = sorted(set(staff) | set(evaluated))
        by_area = [
            {"area": area, "staff": staff.get(area, 0), "evaluated": evaluated.get(area, 0)}
            for area in areas
        ]
        total_evaluated = own_answers.filter(personal__in=users).values("personal").distinct().count()
        people = list(users.values("id", "first_name", "last_name", "role", "area", "position").order_by("first_name", "last_name"))
        return Response({
            "staff": sum(staff.values()),
            "areas": len([a for a in areas if a != "-"]),
            "evaluated": total_evaluated,
            "by_area": by_area,
            "people": people,
        })
