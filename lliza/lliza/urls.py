# urls.py
from django.urls import path
from lliza.views import webhook, health_check

urlpatterns = [
    # ...
    path('webhook', webhook, name='webhook'),
    path('health_check', health_check, name='health_check'),
    # ...
]