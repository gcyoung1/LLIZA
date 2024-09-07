# urls.py
from django.urls import path
from lliza.views import webhook, health

urlpatterns = [
    # ...
    path('webhook/?', webhook, name='webhook'),
    path('health/?', health, name='health'),
    # ...
]