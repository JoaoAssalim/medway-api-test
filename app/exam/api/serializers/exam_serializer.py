from django.db.models import Exists, OuterRef
from rest_framework import serializers

from exam.models import (
    Exam,
    ExamQuestion,
    ExamSubmission,
    ExamSubmissionAnswer,
)
from question.models import Alternative
from student.models import Student
from question.utils import AlternativesChoices


class ExamSubmissionAnswerCreateSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    answer = serializers.ChoiceField(choices=AlternativesChoices)


class ExamSubmissionAnswerSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source="exam_question.question_id", read_only=True)
    question_number = serializers.IntegerField(source="exam_question.number", read_only=True)
    is_correct = serializers.SerializerMethodField()

    class Meta:
        model = ExamSubmissionAnswer
        fields = ("exam_question", "question_id", "question_number", "answer", "is_correct")

    def get_is_correct(self, obj: ExamSubmissionAnswer) -> bool:
        annotated = getattr(obj, "is_correct", None)
        if annotated is not None:
            return bool(annotated)

        return Alternative.objects.filter(
            question=obj.exam_question.question,
            option=obj.answer,
            is_correct=True,
        ).exists()


class ExamSubmissionSerializer(serializers.ModelSerializer):
    answers = ExamSubmissionAnswerSerializer(many=True, read_only=True)
    total_questions = serializers.SerializerMethodField()
    correct_answers = serializers.SerializerMethodField()
    correct_percentage = serializers.SerializerMethodField()

    class Meta:
        model = ExamSubmission
        fields = ("id", "exam", "student", "created_at", "answers", "total_questions", "correct_answers", "correct_percentage")

    def get_total_questions(self, obj: ExamSubmission) -> int:
        return ExamQuestion.objects.filter(exam=obj.exam).count()

    def get_correct_answers(self, obj: ExamSubmission) -> int:
        answers_qs = ExamSubmissionAnswer.objects.filter(submission=obj).annotate(
            is_correct=Exists(
                Alternative.objects.filter(
                    question=OuterRef("exam_question__question"),
                    option=OuterRef("answer"),
                    is_correct=True,
                )
            )
        )
        return answers_qs.filter(is_correct=True).count()
    
    def get_correct_percentage(self, obj: ExamSubmission) -> float:
        total = self.get_total_questions(obj)
        if total == 0:
            return 0.0
        return (self.get_correct_answers(obj) / total) * 100



class ExamSubmissionCreateSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField(min_value=1)
    student_id = serializers.IntegerField(min_value=1)
    answers = ExamSubmissionAnswerCreateSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        exam_id = attrs["exam_id"]
        student_id = attrs["student_id"]
        raw_answers = attrs["answers"]

        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            raise serializers.ValidationError({"exam_id": "Exam not found."})

        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise serializers.ValidationError({"student_id": "Student not found."})

        exam_question_rows = list(
            ExamQuestion.objects.filter(exam=exam).values("id", "question_id")
        )
        if not exam_question_rows:
            raise serializers.ValidationError({"exam_id": "Exam has no questions."})

        question_id_to_exam_question_id = {row["question_id"]: row["id"] for row in exam_question_rows}
        exam_question_ids = {row["question_id"] for row in exam_question_rows}

        provided_question_ids = [a["question_id"] for a in raw_answers]
        if len(provided_question_ids) != len(set(provided_question_ids)):
            raise serializers.ValidationError({"answers": "Duplicate question_id in answers."})

        invalid_question_ids = sorted(set(provided_question_ids) - set(exam_question_ids))
        if invalid_question_ids:
            raise serializers.ValidationError(
                {"answers": f"Some question_id do not belong to exam {exam_id}: {invalid_question_ids}"}
            )

        missing_question_ids = sorted(set(exam_question_ids) - set(provided_question_ids))
        if missing_question_ids:
            raise serializers.ValidationError(
                {"answers": f"Missing answers for questions: {missing_question_ids}"}
            )

        attrs["exam"] = exam
        attrs["student"] = student
        attrs["question_id_to_exam_question_id"] = question_id_to_exam_question_id
        return attrs

    def create(self, validated_data):
        exam = validated_data["exam"]
        student = validated_data["student"]
        answers = validated_data["answers"]
        question_id_to_exam_question_id = validated_data["question_id_to_exam_question_id"]

        submission = ExamSubmission.objects.create(exam=exam, student=student)
        ExamSubmissionAnswer.objects.bulk_create(
            [
                ExamSubmissionAnswer(
                    submission=submission,
                    exam_question_id=question_id_to_exam_question_id[a["question_id"]],
                    answer=a["answer"],
                )
                for a in answers
            ]
        )
        return submission
