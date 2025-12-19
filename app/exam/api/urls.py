from django.urls import path
from exam.api.views import ExamSubmissionAPIView, ExamFetchAPIView

urlpatterns = [
    path('submissions/', ExamSubmissionAPIView.as_view(), name='exam-submit'),
    path('exams/', ExamFetchAPIView.as_view(), name='exam-fetch'),
]