import calendar

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def end_of_month(day=None):
    """Kept for the historical migration that first added the automatic closing date."""
    day = day or timezone.localdate()
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


# Date checks use the local day (timezone.localdate), so an evaluation stays answerable through its whole closing day.
class EvaluationQuerySet(models.QuerySet):
    def available(self):
        """The evaluations a collaborator can answer today: programmed, open and not past their closing day.
        A just-created evaluation has no closing date, monthly limit or program_started_at, so it stays hidden until
        the boss programs it (programming always sets closes_on and monthly_limit; reprogramming sets program_started_at)."""
        today = timezone.localdate()
        programmed = (
            models.Q(program_started_at__isnull=False)
            | models.Q(closes_on__isnull=False)
            | models.Q(monthly_limit__isnull=False)
        )
        return self.filter(programmed, is_available=True).filter(models.Q(closes_on__isnull=True) | models.Q(closes_on__gte=today))


class Evaluation(models.Model):
    """An independent evaluation (a named form). The boss can keep one or several open at once.

    Its categories and questions belong only to it: adding a category here never changes another evaluation.
    It can be answered until the end of its closing day (`closes_on`); after that it closes automatically.
    """

    class RatingType(models.TextChoices):
        QUANTITATIVE = "quantitative", _("Quantitative")
        QUANTITATIVE_10 = "quantitative_10", _("Quantitative 1 to 10")
        DESCRIPTIVE = "descriptive", _("Descriptive")
        DESCRIPTIVE_PERFORMANCE = "descriptive_performance", _("Performance or compliance")
        DESCRIPTIVE_SERVICE = "descriptive_service", _("Service quality")
        DESCRIPTIVE_EQUIPMENT = "descriptive_equipment", _("Biomedical equipment condition")
        DESCRIPTIVE_RISK = "descriptive_risk", _("Clinical or technical risk")
        DESCRIPTIVE_COMPLIANCE = "descriptive_compliance", _("Requirements compliance")

    name = models.CharField(_("Name"), max_length=150)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_evaluations",
        verbose_name=_("Created by"),
    )
    rating_type = models.CharField(_("Rating type"), max_length=24, choices=RatingType.choices, default=RatingType.QUANTITATIVE)
    is_available = models.BooleanField(_("Available"), default=True)
    closes_on = models.DateField(_("Closing date"), null=True, blank=True)
    # areas: None means every area. personal_ids: empty list means everyone in the allowed areas.
    areas = models.JSONField(_("Areas to evaluate"), null=True, blank=True, default=None)
    personal_ids = models.JSONField(_("Staff to evaluate"), default=list, blank=True)
    # Per-evaluation quota; None falls back to the global EvaluationSetting (see limits.monthly_limit).
    monthly_limit = models.PositiveSmallIntegerField(_("Monthly limit"), null=True, blank=True, default=None)
    # Collaborators (evaluators) enabled for this evaluation. Empty list means every collaborator of the allowed areas.
    # Independent from the selection mode below.
    evaluator_ids = models.JSONField(_("Evaluators"), default=list, blank=True)
    # How collaborators pick who they evaluate: False = they choose themselves, True = the system assigns them
    # monthly_limit random people of their area (see limits.assigned_personal).
    random_selection = models.BooleanField(_("Random selection"), default=False)
    # Set when the boss reprograms it (new closing date, areas, people or reopening): a new round starts
    # and the collaborators can score again, even in the same month.
    program_started_at = models.DateTimeField(_("Program started"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created"), auto_now_add=True)

    objects = EvaluationQuerySet.as_manager()

    @property
    def is_expired(self):
        return self.closes_on is not None and self.closes_on < timezone.localdate()

    @property
    def status(self):
        """Available for answers, or closed manually/by reaching its closing date."""
        return "available" if self.is_available and not self.is_expired else "closed"

    class Meta:
        verbose_name = _("Evaluation")
        verbose_name_plural = _("Evaluations")
        ordering = ["id"]

    def __str__(self):
        return self.name


class Category(models.Model):
    """A group of criteria of an evaluation. The boss creates them from the app."""

    # PROTECT: history must survive, so views deactivate (is_active) instead of deleting categories that have scores.
    evaluation = models.ForeignKey(Evaluation, on_delete=models.PROTECT, related_name="categories")
    # `code` is unique across ALL evaluations (not per evaluation); Question stores this code as plain text, not as an FK.
    code = models.SlugField(_("Code"), max_length=50, unique=True)
    name = models.CharField(_("Name"), max_length=100)
    order = models.PositiveIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Criterion(models.Model):
    """A question of the form, scored from 1 to 5 by default. Belongs to a category."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="criteria")
    code = models.CharField(_("Code"), max_length=50, unique=True)
    name = models.TextField(_("Question"))
    order = models.PositiveIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criteria")
        ordering = ["order", "id"]

    def __str__(self):
        return self.name[:60]

    @classmethod
    def active(cls, evaluation):
        """The criteria that make up the form of `evaluation` today (active, in an active category)."""
        return cls.objects.filter(
            is_active=True, category__is_active=True, category__evaluation=evaluation
        ).select_related("category")


class Question(models.Model):
    """One score (0-10) given by a collaborator to a staff member for a single criterion."""

    evaluation = models.ForeignKey(Evaluation, on_delete=models.PROTECT, related_name="questions")
    collaborator = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="questions_given",
        verbose_name=_("Collaborator"),
    )
    personal = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="questions_received",
        verbose_name=_("Staff member"),
    )
    # Denormalized: the area of the scored person when the answer was sent, so later area changes do not rewrite history.
    # `category` / `criterion` hold Category.code / Criterion.code strings (no FK), kept even if renamed or deactivated.
    area = models.CharField(_("Area"), max_length=100)
    category = models.CharField(_("Category"), null=True, blank=True, max_length=50)
    criterion = models.CharField(_("Criterion"), null=True, blank=True, max_length=50)
    # The valid range depends on Evaluation.rating_type (checked in serializers). 0 only exists in the compliance scale
    # and means "does not apply": averages exclude score=0.
    score = models.PositiveSmallIntegerField(
        _("Score"),
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    created_at = models.DateTimeField(_("Date"), auto_now_add=True)
    # Set when the evaluation is sent: it counts right away (the final score is the average of the
    # scores; the boss only consults them and never writes a score).
    reviewed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions_reviewed",
        verbose_name=_("Reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("Reviewed at"), null=True, blank=True)
    # NOTE: created_at is declared twice in this model (see "Date" above); this second declaration overrides the first.
    created_at = models.DateTimeField(_("Created at"),auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"),auto_now=True)

    class Meta:
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")

    def __str__(self):
        return f"{self.criterion}: {self.score}"


class EvaluationSetting(models.Model):
    """Single row: how many colleagues each collaborator can score per month (set by the boss)."""

    DEFAULT_MONTHLY_LIMIT = 3
    MAX_MONTHLY_LIMIT = 30

    monthly_limit = models.PositiveSmallIntegerField(_("Monthly limit"), default=DEFAULT_MONTHLY_LIMIT)

    class Meta:
        verbose_name = _("Evaluation setting")
        verbose_name_plural = _("Evaluation settings")

    @classmethod
    def current(cls):
        """Get-or-create the singleton row (pk=1); do not create other rows."""
        return cls.objects.get_or_create(pk=1)[0]
