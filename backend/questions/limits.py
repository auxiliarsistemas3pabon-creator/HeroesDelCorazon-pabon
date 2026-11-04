import random

from django.utils import timezone

from users.models import User

from .models import Evaluation, EvaluationSetting, Question


def monthly_limit(evaluation=None):
    """How many colleagues a collaborator can score per month in this evaluation."""
    if evaluation is not None:
        # A per-evaluation value wins; otherwise use the configurable global default.
        # Always clamped to 1..MAX so a bad stored value can never block everyone or allow unlimited answers.
        value = evaluation.monthly_limit if evaluation.monthly_limit is not None else EvaluationSetting.current().monthly_limit
        return max(1, min(value, EvaluationSetting.MAX_MONTHLY_LIMIT))
    return max(1, min(EvaluationSetting.current().monthly_limit, EvaluationSetting.MAX_MONTHLY_LIMIT))


def month_start():
    """First instant of the current month in local time; the monthly quota window starts here."""
    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def scored_this_month(collaborator, evaluation):
    """Ids of the colleagues this collaborator already scored in `evaluation` during the current month.

    Each evaluation has its own quota: a colleague can be scored once per month in every evaluation.
    Reprogramming the evaluation starts a new round, so earlier answers stop counting.
    """
    since = month_start()
    if evaluation.program_started_at and evaluation.program_started_at > since:
        since = evaluation.program_started_at
    return set(
        Question.objects.filter(collaborator=collaborator, evaluation=evaluation, created_at__gte=since)
        .values_list("personal_id", flat=True)
    )


def assigned_personal(collaborator, evaluation):
    """Ids of the people the system assigns to `collaborator` in a random-selection evaluation (monthly_limit of them).

    The draw is deterministic for (evaluation, collaborator, round): it never changes between requests, and already scored
    people stay in it, so the collaborator just works through a fixed list. A new month or reprogramming starts a new draw.
    """
    pool = User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True, area=collaborator.area).exclude(pk=collaborator.pk)
    if collaborator.area == "":
        return []
    if evaluation.personal_ids:
        pool = pool.filter(pk__in=evaluation.personal_ids)
    since = month_start()
    if evaluation.program_started_at and evaluation.program_started_at > since:
        since = evaluation.program_started_at
    ids = sorted(pool.values_list("pk", flat=True))
    random.Random(f"{evaluation.pk}:{collaborator.pk}:{since.isoformat()}").shuffle(ids)
    return ids[: monthly_limit(evaluation)]


def find_evaluation(raw, open_only=True):
    """The evaluation with that id, or (no id given) the only one there is. None if it cannot be decided."""
    evaluations = Evaluation.objects.available() if open_only else Evaluation.objects.all()
    if raw in (None, ""):
        found = list(evaluations[:2])
        return found[0] if len(found) == 1 else None
    return evaluations.filter(pk=raw).first() if str(raw).isdigit() else None
