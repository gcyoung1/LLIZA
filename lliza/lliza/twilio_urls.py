from django.urls import path
from lliza.twilio_views import webhook, health

urlpatterns = [
    path('webhook', webhook, name='webhook'),
    path('health', health, name='health'),
]