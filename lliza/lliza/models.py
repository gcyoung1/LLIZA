from django.db import models

class User(models.Model):
    """
    Represents a Pipeline model in the Django application.

    Fields:
    - sdgr_path: CharField - The path to the Schrodinger installation
    - settings: JSONField - General settings of the pipeline.
    """
    user_id = models.CharField(max_length=255)
    memory_dict = models.JSONField()