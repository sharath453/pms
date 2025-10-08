from django.db import models

class PatientLog(models.Model):
    operation = models.CharField(max_length=50)
    patient_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.operation} - {self.status}"