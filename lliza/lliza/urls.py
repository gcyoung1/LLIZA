# urls.py
from django.urls import path
from lliza.views import webhook

urlpatterns = [
    # ...
    path('webhook', webhook, name='webhook'),
    # ...
]