from django.db import models


class CheckIn(models.Model):
    employee_id = models.IntegerField()       # from user-service (no FK)
    ngo_id = models.IntegerField()            # from ngo-service (no FK)
    checked_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee_id', 'ngo_id')  # can't check in twice

    def __str__(self):
        return f"Employee {self.employee_id} → NGO {self.ngo_id}"