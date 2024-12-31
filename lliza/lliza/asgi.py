"""
ASGI config for lliza project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# Consumers imports django models so we need to setup django first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lliza.settings")
import django
django.setup()

from lliza import consumers

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            [
                path("conversation-relay/", consumers.ConversationRelayConsumer.as_asgi()),
            ]
        )
    ),
})
