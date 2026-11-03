from django.contrib import admin

from .models import Category, Criterion, Evaluation, EvaluationSetting, Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("personal", "collaborator", "area", "category", "criterion", "score", "created_at", "reviewed_at")
    list_filter = ("area", "category")


admin.site.register(EvaluationSetting)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "evaluation", "code", "order", "is_active")
    list_filter = ("evaluation",)


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "order", "is_active")
    list_filter = ("category", "is_active")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_available", "closes_on", "created_at")
