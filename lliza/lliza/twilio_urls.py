from django.urls import path
from lliza.twilio_views import webhook, health, message_status

urlpatterns = [
    path('webhook', webhook, name='webhook'),
    path('health', health, name='health'),
    path('message-status', message_status, name='message-status'),
]