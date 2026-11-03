from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from users.models import User

from .limits import assigned_personal, find_evaluation, monthly_limit, scored_this_month
from .models import Criterion, Evaluation, Question


class QuestionSerializer(serializers.ModelSerializer):
    personal_name = serializers.CharField(source="personal.get_full_name", read_only=True)

    class Meta:
        model = Question
        fields = ["id", "personal", "personal_name", "area", "category", "criterion", "score", "created_at", "reviewed_at"]


# Loose 0-10 bound only; the real range for the rating type is enforced in QuestionCreateSerializer.validate.
class AnswerSerializer(serializers.Serializer):
    criterion = serializers.CharField()
    score = serializers.IntegerField(min_value=0, max_value=10)


class QuestionCreateSerializer(serializers.Serializer):
    """Full set of answers of one evaluation: one staff member + every criterion of that evaluation.

    Colleagues of the same area only. `evaluation` may be omitted when there is a single open evaluation.
    """

    evaluation = serializers.PrimaryKeyRelatedField(
        queryset=Evaluation.objects.all(), required=False, allow_null=True
    )
    personal = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL], is_active=True)
    )
    answers = AnswerSerializer(many=True)

    # Same-area rule: collaborators only evaluate active peers of their own area, never themselves.
    def validate_personal(self, personal):
        collaborator = self.context["request"].user
        if personal.pk == collaborator.pk:
            raise serializers.ValidationError(_("You cannot evaluate yourself."))
        if not collaborator.area or personal.area != collaborator.area:
            raise serializers.ValidationError(_("The collaborator does not belong to your area."))
        return personal

    def validate(self, attrs):
        # Availability depends on today's date, so it is checked here on every request (not when the module loads).
        chosen = attrs.get("evaluation")
        evaluation = find_evaluation(chosen.pk) if chosen else find_evaluation(None)
        if evaluation is None:
            raise serializers.ValidationError({"evaluation": _("Choose an open evaluation.")})
        collaborator = self.context["request"].user
        if not collaborator.area or (
            evaluation.areas is not None and collaborator.area not in evaluation.areas
        ):
            raise serializers.ValidationError({"evaluation": _("This evaluation is not available for your area.")})
        if evaluation.personal_ids and attrs["personal"].pk not in evaluation.personal_ids:
            raise serializers.ValidationError({"personal": _("This staff member is not included in the evaluation.")})
        if evaluation.evaluator_ids and collaborator.pk not in evaluation.evaluator_ids:
            raise serializers.ValidationError({"evaluation": _("This evaluation is not available for you.")})
        if evaluation.random_selection and attrs["personal"].pk not in assigned_personal(collaborator, evaluation):
            raise serializers.ValidationError({"personal": _("This staff member was not assigned to you.")})
        attrs["evaluation"] = evaluation

        # Allowed scores per rating scale: 1-5 for most, 1-10 for quantitative_10, and 0-3 for compliance.
        valid_scores = {
            Evaluation.RatingType.QUANTITATIVE: set(range(1, 6)),
            Evaluation.RatingType.QUANTITATIVE_10: set(range(1, 11)),
            Evaluation.RatingType.DESCRIPTIVE: set(range(1, 6)),
            Evaluation.RatingType.DESCRIPTIVE_PERFORMANCE: set(range(1, 6)),
            Evaluation.RatingType.DESCRIPTIVE_SERVICE: set(range(1, 6)),
            Evaluation.RatingType.DESCRIPTIVE_EQUIPMENT: set(range(1, 6)),
            Evaluation.RatingType.DESCRIPTIVE_RISK: set(range(1, 6)),
            Evaluation.RatingType.DESCRIPTIVE_COMPLIANCE: {0, 1, 2, 3},
        }[evaluation.rating_type]
        if any(answer["score"] not in valid_scores for answer in attrs["answers"]):
            raise serializers.ValidationError({"answers": _("The selected score is not valid for this rating scale.")})

        # The form is all-or-nothing: exactly the active criteria of the evaluation, each one once.
        expected = list(Criterion.active(evaluation).values_list("code", flat=True))
        criteria = [a["criterion"] for a in attrs["answers"]]
        if not expected or sorted(criteria) != sorted(expected):
            raise serializers.ValidationError(
                {"answers": _("You must score every criterion of the form, each one only once.")}
            )

        collaborator = self.context["request"].user
        # Quota rules: one submission per colleague per round, and at most monthly_limit colleagues (see limits.py).
        done = scored_this_month(collaborator, evaluation)
        if attrs["personal"].pk in done:
            raise serializers.ValidationError({"personal": _("You already scored this colleague this month.")})
        if len(done) >= monthly_limit(evaluation):
            raise serializers.ValidationError({"personal": _("You reached the monthly limit of colleagues to score.")})
        return attrs

    def create(self, validated_data):
        collaborator = self.context["request"].user
        personal = validated_data["personal"]
        evaluation = validated_data["evaluation"]
        category_of = dict(Criterion.active(evaluation).values_list("code", "category__code"))
        # One Question row per criterion. reviewed_at is set right away: there is no approval step, an answer counts once sent.
        now = timezone.now()
        return Question.objects.bulk_create(
            Question(
                evaluation=evaluation,
                collaborator=collaborator,
                personal=personal,
                area=personal.area,
                category=category_of[a["criterion"]],
                criterion=a["criterion"],
                score=a["score"],
                reviewed_at=now,
            )
            for a in validated_data["answers"]
        )
