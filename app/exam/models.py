from django.db import models

from question.models import Question
from student.models import Student
from question.utils import AlternativesChoices


class Exam(models.Model):
    name = models.CharField(max_length=100)
    questions = models.ManyToManyField(Question, through='ExamQuestion', related_name='questions')

    def __str__(self):
        return self.name


class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()

    class Meta:
        unique_together = ('exam', 'number')
        ordering = ['number']

    def __str__(self):
        return f'{self.question} - {self.exam}'

class ExamSubmission(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="exam_submissions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.email} - {self.exam.name} ({self.created_at:%Y-%m-%d %H:%M:%S})"


class ExamSubmissionAnswer(models.Model):
    submission = models.ForeignKey(
        ExamSubmission,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    exam_question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="submission_answers")
    answer = models.IntegerField(choices=AlternativesChoices)

    class Meta:
        unique_together = ("submission", "exam_question")
        indexes = [
            models.Index(fields=["submission", "exam_question"]),
            models.Index(fields=["exam_question"]),
        ]
