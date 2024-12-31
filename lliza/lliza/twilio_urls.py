from django.urls import path
from lliza.twilio_views import webhook, health, message_status, schedule_webhook, handle_incoming_call

urlpatterns = [
    path('webhook', webhook, name='webhook'),
    path('health', health, name='health'),
    path('message-status', message_status, name='message-status'),
    path('schedule-webhook', schedule_webhook, name='schedule-webhook'),
    path('handle-incoming-call', handle_incoming_call, name='handle-incoming-call'),

]