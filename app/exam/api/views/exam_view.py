from django.db.models import Exists, OuterRef, Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from exam.api.serializers import (
    ExamSubmissionCreateSerializer,
    ExamSubmissionSerializer,
)
from exam.models import ExamSubmission, ExamSubmissionAnswer
from question.models import Alternative
from student.models import Student


class ExamSubmissionAPIView(APIView):
    @swagger_auto_schema(
        operation_summary="Submit an exam (all answers at once)",
        operation_description=(
            "Creates an `ExamSubmission` and all `ExamSubmissionAnswer` rows in a single request.\n\n"
            "Rules:\n"
            "- No authentication required\n"
            "- `student_id` is provided explicitly\n"
            "- You must send exactly one answer for each question in the exam\n"
            "- Answers are sent as a list of `{question_id, answer}`; `answer` must be one of AlternativesChoices (1-5)"
        ),
        tags=["Exam"],
        request_body=ExamSubmissionCreateSerializer,
        responses={
            201: ExamSubmissionSerializer,
            400: openapi.Response("Validation error"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ExamSubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        submission = serializer.save()

        # fazemos a queryset das respostas e usamos select_related por conta de FK e OuterRef para validar campos da query "primaria"
        answers_qs = (
            ExamSubmissionAnswer.objects.select_related("exam_question", "exam_question__question").annotate(
                is_correct=Exists(
                    Alternative.objects.filter(
                        question=OuterRef("exam_question__question"),
                        option=OuterRef("answer"),
                        is_correct=True,
                    )
                )
            )
        )

        # fazemos a montagem das submissões e usamos prefetch_related pois estamos trabalhando com M2M
        submission = (
            ExamSubmission.objects.select_related("exam", "student")
            .prefetch_related(Prefetch("answers", queryset=answers_qs))
            .get(id=submission.id)
        )
        return Response(ExamSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


class ExamFetchAPIView(APIView):
    @swagger_auto_schema(
        operation_summary="Fetch exam submissions (optional filters)",
        operation_description=(
            "Returns submissions. Filters are optional:\n"
            "- `exam_id`: filter submissions for a specific exam\n"
            "- `student_id`: filter submissions for a specific student"
        ),
        tags=["Exam"],
        manual_parameters=[
            openapi.Parameter(
                "exam_id",
                openapi.IN_QUERY,
                description="Optional exam id to filter submissions",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "student_id",
                openapi.IN_QUERY,
                description="Optional student id to filter submissions",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: ExamSubmissionSerializer(many=True), 400: openapi.Response("Validation error")},
    )
    def get(self, request, *args, **kwargs):
        exam_id = request.query_params.get("exam_id")
        student_id = request.query_params.get("student_id")

        answers_qs = (
            ExamSubmissionAnswer.objects.select_related("exam_question", "exam_question__question").annotate(
                is_correct=Exists(
                    Alternative.objects.filter(
                        question=OuterRef("exam_question__question"),
                        option=OuterRef("answer"),
                        is_correct=True,
                    )
                )
            )
        )

        submissions = (
            ExamSubmission.objects.select_related("exam", "student")
            .prefetch_related(Prefetch("answers", queryset=answers_qs))
            .all()
        )

        if exam_id is not None:
            try:
                exam_id_int = int(exam_id)
            except (TypeError, ValueError):
                return Response({"exam_id": "Must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
            submissions = submissions.filter(exam_id=exam_id_int)

        if student_id is not None:
            try:
                student_id_int = int(student_id)
            except (TypeError, ValueError):
                return Response({"student_id": "Must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

            if not Student.objects.filter(id=student_id_int).exists():
                return Response({"student_id": "Student not found."}, status=status.HTTP_400_BAD_REQUEST)

            submissions = submissions.filter(student_id=student_id_int)

        submissions = submissions.order_by("-created_at")
        print(submissions)
        return Response(ExamSubmissionSerializer(submissions, many=True).data, status=status.HTTP_200_OK)