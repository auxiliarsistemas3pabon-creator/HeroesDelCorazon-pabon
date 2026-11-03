from django.urls import path

from .config_views import (
    CategoriesView,
    CategoryCriteriaView,
    CategoryDetailView,
    CriterionDetailView,
    EvaluationDetailView,
    EvaluationImportView,
    EvaluationProgramCreateView,
    EvaluationsView,
)
from .views import (
    CategoryAveragesView,
    DashboardView,
    QuestionFormView,
    QuestionsView,
    QuotaView,
    ResultsSummaryView,
    ResultsView,
    SentView,
    SettingsView,
    StatsView,
    SubmissionsView,
)

# Boss-only: import, evaluations, categories, criteria, settings, submissions, results-summary, category-averages, stats.
# Collaborator-only: sent, quota and POST questions/. Permissions live in each view, not here.
urlpatterns = [
    path("questions/import/", EvaluationImportView.as_view(), name="question-import"),
    path("questions/evaluations/", EvaluationsView.as_view(), name="question-evaluations"),
    path("questions/evaluations/<int:pk>/", EvaluationDetailView.as_view(), name="question-evaluation"),
    path("questions/evaluations/<int:pk>/programs/", EvaluationProgramCreateView.as_view(), name="question-evaluation-program-create"),
    path("questions/categories/", CategoriesView.as_view(), name="question-categories"),
    path("questions/categories/<int:pk>/", CategoryDetailView.as_view(), name="question-category"),
    path("questions/categories/<int:pk>/criteria/", CategoryCriteriaView.as_view(), name="question-category-criteria"),
    path("questions/criteria/<int:pk>/", CriterionDetailView.as_view(), name="question-criterion"),
    path("questions/form/", QuestionFormView.as_view(), name="question-form"),
    path("questions/", QuestionsView.as_view(), name="questions"),
    path("questions/settings/", SettingsView.as_view(), name="question-settings"),
    path("questions/sent/", SentView.as_view(), name="question-sent"),
    path("questions/submissions/", SubmissionsView.as_view(), name="question-submissions"),
    path("questions/results-summary/", ResultsSummaryView.as_view(), name="question-results-summary"),
    path("questions/results/", ResultsView.as_view(), name="question-results"),
    path("questions/quota/", QuotaView.as_view(), name="question-quota"),
    path("questions/dashboard/", DashboardView.as_view(), name="question-dashboard"),
    path("questions/category-averages/", CategoryAveragesView.as_view(), name="question-category-averages"),
    path("questions/stats/", StatsView.as_view(), name="question-stats"),
]
